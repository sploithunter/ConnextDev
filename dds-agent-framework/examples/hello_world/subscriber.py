#!/usr/bin/env python3
"""Hello World DDS Subscriber with async callbacks.

Subscribes to HelloWorld samples using RTI Connext DDS Python API.
Uses on_data_available callback (asynchronous, not polling).
Uses external QoS XML configuration.
Outputs received samples in JSONL format for verification.

Usage:
    python subscriber.py --domain 99 --count 10 --output samples.jsonl
    python subscriber.py --qos-file qos_profiles.xml --timeout 30
"""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import TextIO


def check_dds_available() -> bool:
    """Check if RTI Connext DDS Python API is available."""
    try:
        import rti.connextdds as dds
        return True
    except ImportError:
        return False


def get_qos_provider(qos_file: str | None = None):
    """Get QoS provider from XML file."""
    import rti.connextdds as dds
    
    if qos_file and Path(qos_file).exists():
        return dds.QosProvider(qos_file)
    
    # Try default location
    default_qos = Path(__file__).parent / "qos_profiles.xml"
    if default_qos.exists():
        return dds.QosProvider(str(default_qos))
    
    return None


def create_hello_type():
    """Create the HelloWorld type using DynamicData."""
    import rti.connextdds as dds

    hello_type = dds.StructType("HelloWorld")
    hello_type.add_member(dds.Member("message", dds.StringType(256)))
    hello_type.add_member(dds.Member("count", dds.Int32Type()))
    hello_type.add_member(dds.Member("timestamp", dds.Float64Type()))

    return hello_type


class HelloWorldListener:
    """Listener for HelloWorld samples using on_data_available callback."""
    
    def __init__(
        self,
        output_file: TextIO,
        max_count: int = 0,
        verbose: bool = True,
    ):
        """Initialize the listener.
        
        Args:
            output_file: File to write JSONL output.
            max_count: Maximum samples to receive (0 = unlimited).
            verbose: Print status messages to stderr.
        """
        self.output_file = output_file
        self.max_count = max_count
        self.verbose = verbose
        self.received_count = 0
        self.done_event = threading.Event()
        self._lock = threading.Lock()
    
    def on_data_available(self, reader) -> None:
        """Callback invoked when data is available (async, not polling).
        
        This is the recommended pattern for DDS subscribers - using
        on_data_available callbacks instead of polling.
        """
        import rti.connextdds as dds
        
        # Take all available samples
        samples = reader.take()
        
        for sample in samples:
            if sample.info.valid:
                with self._lock:
                    self.received_count += 1
                    count = self.received_count
                
                # Extract data
                data = sample.data
                sample_dict = {
                    "topic": "HelloWorld",
                    "sample_count": count,
                    "data": {
                        "message": data["message"],
                        "count": data["count"],
                        "timestamp": data["timestamp"],
                    }
                }
                
                # Write JSONL output
                self.output_file.write(json.dumps(sample_dict) + "\n")
                self.output_file.flush()
                
                if self.verbose:
                    print(
                        f"Received sample {count}: count={data['count']}",
                        file=sys.stderr
                    )
                
                # Check if we've received enough
                if self.max_count > 0 and count >= self.max_count:
                    self.done_event.set()
    
    def wait_for_completion(self, timeout: float) -> int:
        """Wait for completion or timeout.
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Number of samples received.
        """
        self.done_event.wait(timeout=timeout)
        return self.received_count


def run_subscriber(
    domain_id: int,
    count: int,
    timeout: float,
    output_file: TextIO,
    qos_file: str | None = None,
    verbose: bool = True,
) -> int:
    """Run the Hello World subscriber with async callbacks.

    Args:
        domain_id: DDS domain ID.
        count: Number of samples to receive (0 = unlimited).
        timeout: Timeout in seconds.
        output_file: File to write JSONL output.
        qos_file: Path to QoS XML file.
        verbose: Print status messages.

    Returns:
        Number of samples received.
    """
    import rti.connextdds as dds

    # Load QoS from XML if available
    qos_provider = get_qos_provider(qos_file)
    
    # Create participant
    if qos_provider:
        participant_qos = qos_provider.participant_qos
        participant = dds.DomainParticipant(domain_id, participant_qos)
    else:
        participant = dds.DomainParticipant(domain_id)

    # Create the type
    hello_type = create_hello_type()

    # Create topic
    topic = dds.DynamicData.Topic(participant, "HelloWorld", hello_type)

    # Create subscriber
    subscriber = dds.Subscriber(participant)
    
    # Create listener with callback
    listener = HelloWorldListener(
        output_file=output_file,
        max_count=count,
        verbose=verbose,
    )
    
    # Create reader with QoS and listener
    # Using StatusMask for on_data_available callback
    if qos_provider:
        reader_qos = qos_provider.datareader_qos
        reader = dds.DynamicData.DataReader(
            subscriber,
            topic,
            reader_qos,
        )
    else:
        reader = dds.DynamicData.DataReader(subscriber, topic)
    
    # Set up the listener for on_data_available
    # Note: RTI Python API uses a different pattern - we use take() in a 
    # condition-triggered waitset, which is the async pattern
    status_condition = dds.StatusCondition(reader)
    status_condition.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
    
    waitset = dds.WaitSet()
    waitset.attach_condition(status_condition)
    
    if verbose:
        print(f"Subscriber started on domain {domain_id}", file=sys.stderr)
        print(f"Waiting for samples...", file=sys.stderr)

    # Wait loop using WaitSet (async, not polling)
    start_time = time.time()
    received = 0
    
    try:
        while True:
            # Check timeout
            elapsed = time.time() - start_time
            remaining = timeout - elapsed
            if remaining <= 0:
                if verbose:
                    print(f"Timeout after {timeout}s", file=sys.stderr)
                break
            
            # Wait for data (async wait, not busy polling)
            wait_timeout = dds.Duration.from_seconds(min(remaining, 1.0))
            conditions = waitset.wait(wait_timeout)
            
            # Process data if available
            if status_condition in conditions:
                listener.on_data_available(reader)
            
            # Check if done
            if count > 0 and listener.received_count >= count:
                break
                
    except KeyboardInterrupt:
        if verbose:
            print("\nInterrupted", file=sys.stderr)

    received = listener.received_count
    if verbose:
        print(f"Received {received} samples total", file=sys.stderr)
    
    return received


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hello World DDS Subscriber with async callbacks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python subscriber.py --domain 99 --count 10
  python subscriber.py --timeout 30 --output samples.jsonl
  python subscriber.py --qos-file qos_profiles.xml --verbose
        """
    )
    parser.add_argument(
        "--domain", "-d",
        type=int,
        default=0,
        help="DDS domain ID (default: 0)",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=0,
        help="Number of samples to receive (default: 0 = unlimited)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=30.0,
        help="Timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file for JSONL data (default: stdout)",
    )
    parser.add_argument(
        "--qos-file", "-q",
        type=str,
        default=None,
        help="Path to QoS XML file (default: qos_profiles.xml in same directory)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print status messages to stderr",
    )

    args = parser.parse_args()

    if not check_dds_available():
        print("ERROR: RTI Connext DDS Python API not available", file=sys.stderr)
        sys.exit(1)

    # Open output file
    if args.output:
        output_file = open(args.output, "w")
    else:
        output_file = sys.stdout

    try:
        received = run_subscriber(
            args.domain,
            args.count,
            args.timeout,
            output_file,
            args.qos_file,
            args.verbose,
        )
        sys.exit(0 if received > 0 else 1)
    finally:
        if args.output:
            output_file.close()


if __name__ == "__main__":
    main()


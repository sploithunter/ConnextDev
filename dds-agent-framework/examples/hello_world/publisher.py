#!/usr/bin/env python3
"""Hello World DDS Publisher.

Publishes HelloWorld samples using RTI Connext DDS Python API.
Uses external QoS XML configuration.

Usage:
    python publisher.py --domain 99 --count 10 --rate 10
    python publisher.py --qos-file qos_profiles.xml --domain 0 --count 5
"""

import argparse
import os
import sys
import time
from pathlib import Path


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

    # Define the type structure
    hello_type = dds.StructType("HelloWorld")
    hello_type.add_member(dds.Member("message", dds.StringType(256)))
    hello_type.add_member(dds.Member("count", dds.Int32Type()))
    hello_type.add_member(dds.Member("timestamp", dds.Float64Type()))

    return hello_type


def run_publisher(
    domain_id: int,
    count: int,
    rate_hz: float,
    qos_file: str | None = None,
) -> int:
    """Run the Hello World publisher.

    Args:
        domain_id: DDS domain ID.
        count: Number of samples to publish (0 = infinite).
        rate_hz: Publishing rate in Hz.
        qos_file: Path to QoS XML file.

    Returns:
        Number of samples published.
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

    # Create publisher with QoS
    publisher = dds.Publisher(participant)
    
    # Create writer with QoS
    if qos_provider:
        writer_qos = qos_provider.datawriter_qos
        writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    else:
        writer = dds.DynamicData.DataWriter(publisher, topic)

    # Wait for discovery
    print(f"Publisher started on domain {domain_id}", file=sys.stderr)
    print(f"Waiting for subscribers...", file=sys.stderr)
    time.sleep(1.0)

    # Publish samples
    sample = dds.DynamicData(hello_type)
    period = 1.0 / rate_hz if rate_hz > 0 else 0

    published = 0
    try:
        while count == 0 or published < count:
            # Set sample values
            sample["message"] = f"Hello DDS World #{published + 1}"
            sample["count"] = published + 1
            sample["timestamp"] = time.time()

            # Write sample
            writer.write(sample)
            published += 1

            print(f"Published sample {published}: count={published}", file=sys.stderr)

            if period > 0 and (count == 0 or published < count):
                time.sleep(period)

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)

    print(f"Published {published} samples total", file=sys.stderr)
    return published


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hello World DDS Publisher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python publisher.py --domain 99 --count 10
  python publisher.py --qos-file qos_profiles.xml --count 5 --rate 50
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
        default=10,
        help="Number of samples to publish (default: 10, 0 = infinite)",
    )
    parser.add_argument(
        "--rate", "-r",
        type=float,
        default=10.0,
        help="Publishing rate in Hz (default: 10)",
    )
    parser.add_argument(
        "--qos-file", "-q",
        type=str,
        default=None,
        help="Path to QoS XML file (default: qos_profiles.xml in same directory)",
    )

    args = parser.parse_args()

    if not check_dds_available():
        print("ERROR: RTI Connext DDS Python API not available", file=sys.stderr)
        sys.exit(1)

    run_publisher(args.domain, args.count, args.rate, args.qos_file)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Full loop test for binary bridge.

Test flow:
1. Generate binary test data
2. Feed to inbound adapter (Binary → DDS)
3. Outbound adapter receives from DDS → Binary
4. Compare output to input
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add protocol to path
sys.path.insert(0, str(Path(__file__).parent))
from protocol import (
    encode_message, decode_message,
    Heartbeat, Position, Command, Status
)


def generate_test_data():
    """Generate test messages."""
    messages = [
        Heartbeat(),
        Position(37.7749, -122.4194, 100.0),
        Position(37.7750, -122.4190, 105.0),
        Command(1, 3.14159),
        Status(200, "OK"),
        Command(2, 2.71828),
        Position(37.7751, -122.4186, 110.0),
        Heartbeat(),
        Status(500, "Error"),
        Position(37.7752, -122.4182, 115.0),
    ]
    
    data = b""
    for msg in messages:
        data += encode_message(msg)
    
    return data, messages


def main():
    print("=== Binary Bridge Full Loop Test ===\n")
    
    # Generate test data
    input_data, expected_messages = generate_test_data()
    print(f"Generated {len(expected_messages)} test messages")
    print(f"Input size: {len(input_data)} bytes\n")
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(input_data)
        input_file = f.name
    
    output_file = input_file + ".out"
    
    script_dir = Path(__file__).parent
    
    try:
        # Start outbound adapter (DDS → Binary)
        print("Starting outbound adapter...")
        outbound = subprocess.Popen(
            [
                sys.executable, str(script_dir / "outbound_adapter.py"),
                "--timeout", "20",
                "--count", str(len(expected_messages)),
                "--output", output_file,
            ],
            stderr=subprocess.PIPE,
        )
        
        # Wait for outbound to initialize
        time.sleep(3.0)
        
        # Run inbound adapter (Binary → DDS)
        print("Running inbound adapter...")
        inbound = subprocess.run(
            [
                sys.executable, str(script_dir / "inbound_adapter.py"),
                "--input", input_file,
            ],
            capture_output=True,
            timeout=30,
        )
        
        print(f"Inbound: {inbound.stderr.decode().strip()}")
        
        # Wait for outbound to finish
        outbound.wait(timeout=15)
        print(f"Outbound: {outbound.stderr.read().decode().strip()}")
        
        # Read and verify output
        with open(output_file, "rb") as f:
            output_data = f.read()
        
        print(f"\nOutput size: {len(output_data)} bytes")
        
        # Decode output messages
        received_messages = []
        offset = 0
        while offset < len(output_data):
            msg, consumed = decode_message(output_data[offset:])
            if msg is None:
                break
            received_messages.append(msg)
            offset += consumed
        
        print(f"Received {len(received_messages)} messages")
        
        # Compare (order might differ due to multiple topics)
        def msg_key(m):
            if isinstance(m, Heartbeat):
                return (0, 0)
            elif isinstance(m, Position):
                return (1, m.latitude)
            elif isinstance(m, Command):
                return (2, m.command_id)
            elif isinstance(m, Status):
                return (3, m.status_code)
            return (99, 0)
        
        expected_sorted = sorted(expected_messages, key=msg_key)
        received_sorted = sorted(received_messages, key=msg_key)
        
        # Compare
        print("\n=== Comparison ===")
        all_match = True
        
        for i, (exp, rec) in enumerate(zip(expected_sorted, received_sorted)):
            match = exp == rec
            status = "✓" if match else "✗"
            print(f"  {status} {exp}")
            if not match:
                print(f"      Got: {rec}")
                all_match = False
        
        if len(expected_sorted) != len(received_sorted):
            print(f"\n  Count mismatch: expected {len(expected_sorted)}, got {len(received_sorted)}")
            all_match = False
        
        print()
        if all_match:
            print("✅ PASSED: All messages matched!")
            return 0
        else:
            print("❌ FAILED: Message mismatch")
            return 1
    
    finally:
        # Cleanup
        Path(input_file).unlink(missing_ok=True)
        Path(output_file).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())


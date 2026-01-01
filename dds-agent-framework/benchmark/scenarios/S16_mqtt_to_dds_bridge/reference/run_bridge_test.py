#!/usr/bin/env python3
"""
Test the MQTT to DDS Bridge.

Runs:
1. DDS Subscriber (captures bridged data)
2. MQTT-DDS Bridge (converts MQTT -> DDS)
3. Verifies data flows through correctly
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path


def main():
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    processes = []
    
    def cleanup(signum=None, frame=None):
        print("\n[Test] Cleaning up...")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except:
                proc.kill()
                
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    print("=" * 60)
    print("MQTT to DDS Bridge Test")
    print("=" * 60)
    
    # Start DDS subscriber first
    print("\n[1] Starting DDS Subscriber...")
    sub_proc = subprocess.Popen(
        [sys.executable, "dds_subscriber.py", "--timeout", "20", "--count", "50"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    processes.append(("Subscriber", sub_proc))
    time.sleep(2)  # Allow discovery
    
    # Start bridge (which also starts MQTT simulation)
    print("[2] Starting MQTT-DDS Bridge...")
    bridge_proc = subprocess.Popen(
        [sys.executable, "mqtt_dds_bridge.py", "--count", "10", "--interval", "200"],
        stderr=subprocess.PIPE,
    )
    processes.append(("Bridge", bridge_proc))
    
    # Wait for bridge to complete
    print("[3] Waiting for bridge to complete...")
    bridge_proc.wait(timeout=30)
    
    # Give subscriber time to receive all data
    time.sleep(2)
    sub_proc.terminate()
    
    # Capture output
    stdout, stderr = sub_proc.communicate(timeout=5)
    
    # Parse results
    lines = stdout.decode().strip().split('\n')
    valid_lines = [l for l in lines if l.strip()]
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    
    # Count by topic
    counts = {"SensorTemperature": 0, "SensorHumidity": 0, "DeviceStatus": 0}
    for line in valid_lines:
        try:
            import json
            data = json.loads(line)
            topic = data.get("topic", "unknown")
            if topic in counts:
                counts[topic] += 1
        except:
            pass
            
    print(f"  Temperature samples: {counts['SensorTemperature']}")
    print(f"  Humidity samples:    {counts['SensorHumidity']}")
    print(f"  Status samples:      {counts['DeviceStatus']}")
    print(f"  Total:               {sum(counts.values())}")
    
    # Show bridge output
    bridge_output = bridge_proc.stderr.read().decode()
    print(f"\nBridge output:\n{bridge_output}")
    
    # Verify success
    total = sum(counts.values())
    if total >= 50:
        print("\n✓ PASSED: Bridge successfully converted MQTT to DDS")
        cleanup()
        return 0
    else:
        print(f"\n✗ FAILED: Expected >=50 samples, got {total}")
        cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())


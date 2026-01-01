#!/usr/bin/env python3
"""
Run Full Industrial Sensor Network System.

Tests that all components work together.
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
        print("\n[Runner] Stopping all processes...")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except:
                proc.kill()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    print("=" * 60)
    print("Industrial Sensor Network - Full System Test")
    print("=" * 60)
    
    # Start data logger first (catches late-joining data)
    print("\n[1/4] Starting Data Logger...")
    p = subprocess.Popen(
        [sys.executable, "data_logger.py", "--output", "/tmp/sensor_logs"],
        stderr=subprocess.PIPE,
    )
    processes.append(("DataLogger", p))
    time.sleep(1)
    
    # Start aggregator
    print("[2/4] Starting Aggregator...")
    p = subprocess.Popen(
        [sys.executable, "aggregator.py", "--window", "5"],
        stderr=subprocess.PIPE,
    )
    processes.append(("Aggregator", p))
    time.sleep(1)
    
    # Start alert monitor
    print("[3/4] Starting Alert Monitor...")
    p = subprocess.Popen(
        [sys.executable, "alert_monitor.py"],
        stderr=subprocess.PIPE,
    )
    processes.append(("AlertMonitor", p))
    time.sleep(1)
    
    # Start sensor publisher (publishes 20 samples)
    print("[4/4] Starting Sensor Publisher (20 samples)...")
    p = subprocess.Popen(
        [sys.executable, "sensor_publisher.py", "--count", "20", "--rate", "200"],
        stderr=subprocess.PIPE,
    )
    processes.append(("SensorPublisher", p))
    
    # Wait for publisher to finish
    print("\n[Runner] Waiting for publisher to complete...")
    for name, proc in processes:
        if name == "SensorPublisher":
            proc.wait()
            break
            
    # Give other components time to process
    print("[Runner] Waiting for processing...")
    time.sleep(3)
    
    # Stop all processes
    cleanup()


if __name__ == "__main__":
    main()


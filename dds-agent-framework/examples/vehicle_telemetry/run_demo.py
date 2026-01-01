#!/usr/bin/env python3
"""Vehicle Telemetry Demo - Shows full pipeline verification workflow.

Demonstrates the "publisher-first" development pattern using the DDS tools:
1. Start publisher
2. Capture with dds-spy-wrapper (universal subscriber)
3. Verify output with dds-sample-compare
4. Run full publisher + subscriber pipeline
"""

import json
import os
import subprocess
import sys
import tempfile
import time


def run_cmd(cmd, timeout=30, capture=True):
    """Run a command with timeout."""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            timeout=timeout,
            capture_output=capture,
            text=True,
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"  ⚠ Command timed out after {timeout}s")
        return None


def demo_phase1_spy_verification():
    """Phase 1: Publisher + DDS Spy verification."""
    print("\n" + "=" * 60)
    print("PHASE 1: Publisher Verification with DDS Spy")
    print("=" * 60)
    print("\nDevelopment Pattern: Verify publisher works before writing subscriber")
    print("Tool: dds-spy-wrapper (wraps rtiddsspy universal subscriber)")
    print()
    
    domain = 83
    
    # Start publisher in background
    print("Step 1: Start publisher...")
    pub_proc = subprocess.Popen(
        ["python", "examples/vehicle_telemetry/publisher.py", 
         "--domain", str(domain), "--count", "5", "--rate", "5"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    # Run spy wrapper to capture samples
    print("\nStep 2: Capture with dds-spy-wrapper...")
    spy_output = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    spy_output.close()
    
    result = run_cmd([
        "dds-spy-wrapper",
        "--domain", str(domain),
        "--timeout", "8",
        "--output", spy_output.name,
    ], timeout=15)
    
    pub_proc.wait(timeout=5)
    
    # Display captured samples
    print("\nStep 3: Analyze captured samples...")
    if os.path.exists(spy_output.name):
        with open(spy_output.name) as f:
            samples = [json.loads(line) for line in f if line.strip()]
        
        topics = {}
        for s in samples:
            topic = s.get("topic", "unknown")
            topics[topic] = topics.get(topic, 0) + 1
        
        print(f"  Captured {len(samples)} samples across {len(topics)} topics:")
        for topic, count in sorted(topics.items()):
            print(f"    - {topic}: {count} samples")
            
        # Show sample data structure
        if samples:
            print(f"\n  Sample data structure (first Position sample):")
            for s in samples:
                if "Position" in s.get("topic", ""):
                    print(f"    {json.dumps(s, indent=4)[:300]}...")
                    break
    else:
        print("  No samples captured")
        
    os.unlink(spy_output.name)
    return True


def demo_phase2_pub_sub_pipeline():
    """Phase 2: Full publisher + subscriber pipeline."""
    print("\n" + "=" * 60)
    print("PHASE 2: Full Publisher → Subscriber Pipeline")
    print("=" * 60)
    print("\nDevelopment Pattern: After verifying publisher, test with real subscriber")
    print("Subscriber uses: Async WaitSet pattern (not polling)")
    print()
    
    domain = 84
    
    # Create output file for subscriber
    sub_output = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    sub_output.close()
    
    # Start subscriber first (it will wait for data)
    print("Step 1: Start subscriber (async wait)...")
    sub_proc = subprocess.Popen(
        ["python", "examples/vehicle_telemetry/subscriber.py",
         "--domain", str(domain), "--timeout", "10", "--output", sub_output.name, "-v"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    time.sleep(2)  # Let subscriber discover
    
    # Start publisher
    print("\nStep 2: Start publisher...")
    pub_proc = subprocess.Popen(
        ["python", "examples/vehicle_telemetry/publisher.py",
         "--domain", str(domain), "--count", "10", "--rate", "10"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    # Wait for completion
    print("\nStep 3: Wait for pipeline completion...")
    pub_proc.wait(timeout=15)
    sub_proc.wait(timeout=15)
    
    # Analyze results
    print("\nStep 4: Analyze received samples...")
    if os.path.exists(sub_output.name):
        with open(sub_output.name) as f:
            samples = [json.loads(line) for line in f if line.strip()]
        
        topics = {}
        for s in samples:
            topic = s.get("topic", "unknown")
            topics[topic] = topics.get(topic, 0) + 1
        
        print(f"  Subscriber received {len(samples)} samples:")
        for topic, count in sorted(topics.items()):
            print(f"    - {topic}: {count} samples")
            
        # Verify expected counts
        expected = {"Vehicle_Position": 10, "Vehicle_Velocity": 10, "Vehicle_Status": 2}
        all_match = True
        print("\n  Expected vs Actual:")
        for topic, exp in expected.items():
            actual = topics.get(topic, 0)
            match = "✓" if actual >= exp else "✗"
            all_match = all_match and (actual >= exp)
            print(f"    {topic}: expected {exp}, got {actual} {match}")
            
        if all_match:
            print("\n  ✓ Pipeline test PASSED")
        else:
            print("\n  ✗ Pipeline test FAILED (some samples missing)")
            
    else:
        print("  No samples received")
        
    os.unlink(sub_output.name)
    return True


def demo_phase3_sample_comparison():
    """Phase 3: Sample comparison demo."""
    print("\n" + "=" * 60)
    print("PHASE 3: Sample Comparison with dds-sample-compare")
    print("=" * 60)
    print("\nDevelopment Pattern: Compare captured samples against expected baseline")
    print()
    
    # Create expected and actual sample files
    expected_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    actual_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    
    # Expected samples (baseline)
    expected_samples = [
        {"topic": "Vehicle_Position", "data": {"vehicle_id": 1, "position": {"x": 1.0, "y": 0.0, "z": 100.0}}},
        {"topic": "Vehicle_Position", "data": {"vehicle_id": 1, "position": {"x": 2.0, "y": 0.1, "z": 99.9}}},
        {"topic": "Vehicle_Velocity", "data": {"vehicle_id": 1, "speed": 10.5}},
    ]
    
    # Actual samples (with slight float differences)
    actual_samples = [
        {"topic": "Vehicle_Position", "data": {"vehicle_id": 1, "position": {"x": 1.001, "y": 0.0, "z": 100.0}}},
        {"topic": "Vehicle_Position", "data": {"vehicle_id": 1, "position": {"x": 2.0, "y": 0.1, "z": 99.9}}},
        {"topic": "Vehicle_Velocity", "data": {"vehicle_id": 1, "speed": 10.51}},
    ]
    
    for s in expected_samples:
        expected_file.write(json.dumps(s) + "\n")
    expected_file.close()
    
    for s in actual_samples:
        actual_file.write(json.dumps(s) + "\n")
    actual_file.close()
    
    print("Step 1: Compare with default tolerance (strict)...")
    result = run_cmd([
        "dds-sample-compare",
        "--expected", expected_file.name,
        "--actual", actual_file.name,
    ], timeout=5)
    if result:
        print(f"  Exit code: {result.returncode} (non-zero = differences found)")
        if result.stdout:
            print(result.stdout[:500])
    
    print("\nStep 2: Compare with float tolerance (0.02)...")
    result = run_cmd([
        "dds-sample-compare",
        "--expected", expected_file.name,
        "--actual", actual_file.name,
        "--tolerance", "0.02",
    ], timeout=5)
    if result:
        print(f"  Exit code: {result.returncode} (0 = within tolerance)")
        if result.stdout:
            print(result.stdout[:500])
    
    os.unlink(expected_file.name)
    os.unlink(actual_file.name)
    return True


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    DDS Agent Development Framework - Pipeline Demo      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print("\nThis demo shows the 'publisher-first, then subscriber' development pattern")
    print("using the DDS development tools for verification and testing.")
    
    try:
        demo_phase1_spy_verification()
        demo_phase2_pub_sub_pipeline()
        demo_phase3_sample_comparison()
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print("\nKey takeaways:")
        print("1. Use dds-spy-wrapper to verify publishers without writing subscriber code")
        print("2. Use async WaitSet pattern in subscribers (never poll)")
        print("3. Use dds-sample-compare to validate output against baselines")
        print("4. Always use external QoS XML files")
        print("5. Test early, test often!")
        
    except Exception as e:
        print(f"\nError: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


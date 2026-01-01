#!/usr/bin/env python3
"""Test script for the Hello World Publisher.

Aider can run this to verify the publisher works before final verification.
Returns exit code 0 on success, non-zero on failure.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path


def test_publisher():
    """Test the publisher by running it with a reference subscriber."""
    publisher_file = Path("publisher.py")
    
    if not publisher_file.exists():
        print("❌ FAIL: publisher.py not found")
        return 1
    
    # Test 1: Check syntax
    print("Test 1: Checking syntax...")
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(publisher_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ FAIL: Syntax error")
        print(result.stderr)
        return 1
    print("  ✓ Syntax OK")
    
    # Test 2: Check imports
    print("\nTest 2: Checking imports...")
    result = subprocess.run(
        [sys.executable, "-c", "import publisher"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        print(f"❌ FAIL: Import error")
        print(result.stderr)
        return 1
    print("  ✓ Imports OK")
    
    # Test 3: Quick run test (just startup, not full publish)
    print("\nTest 3: Quick startup test...")
    try:
        result = subprocess.run(
            [sys.executable, str(publisher_file)],
            capture_output=True,
            text=True,
            timeout=8,  # Should start but timeout before finishing
        )
        # If it exits cleanly in <8s, that's fine (fast publish)
        if result.returncode == 0:
            print("  ✓ Publisher ran successfully")
        else:
            print(f"  ⚠ Publisher exited with code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        # Expected - means it started and is publishing
        print("  ✓ Publisher started (timeout expected)")
    
    # Test 4: Full run with sample capture
    print("\nTest 4: Full publish test with sample capture...")
    
    # Create temp file for output
    output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
    output_file.close()
    
    # Get reference subscriber path
    script_dir = Path(__file__).parent
    ref_subscriber = script_dir / "reference" / "subscriber.py"
    
    if not ref_subscriber.exists():
        print(f"  ⚠ Reference subscriber not found at {ref_subscriber}")
        print("  Skipping full verification (will be done by harness)")
        return 0
    
    try:
        # Start subscriber
        sub_proc = subprocess.Popen(
            [sys.executable, str(ref_subscriber), 
             "--domain", "85", "--count", "10", "--timeout", "20",
             "--output", output_file.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        time.sleep(2)  # Wait for subscriber to start
        
        # Run publisher
        pub_result = subprocess.run(
            [sys.executable, str(publisher_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # Wait for subscriber
        sub_stdout, sub_stderr = sub_proc.communicate(timeout=15)
        
        # Check results
        if pub_result.returncode != 0:
            print(f"❌ FAIL: Publisher failed")
            print(pub_result.stderr)
            return 1
        
        # Count samples
        with open(output_file.name) as f:
            samples = [line for line in f if line.strip()]
        
        if len(samples) >= 10:
            print(f"  ✓ Received {len(samples)} samples")
            print("\n✅ ALL TESTS PASSED")
            return 0
        else:
            print(f"  ❌ Only received {len(samples)}/10 samples")
            return 1
            
    except subprocess.TimeoutExpired:
        print("❌ FAIL: Timeout during test")
        return 1
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return 1
    finally:
        # Cleanup
        Path(output_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(test_publisher())


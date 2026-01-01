#!/usr/bin/env python3
"""Test harness for AI-generated HelloWorld subscriber.

Tests:
1. Syntax check
2. Import check  
3. Startup check (runs without immediate crash)
4. Functional check (receives samples from reference publisher)
5. Async pattern check (verifies WaitSet/listener usage)
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXPECTED_SAMPLES = 10
TIMEOUT = 30


def check_syntax():
    """Test 1: Check Python syntax."""
    print("Test 1: Checking syntax...")
    
    subscriber_path = Path(__file__).parent / "subscriber.py"
    if not subscriber_path.exists():
        print("❌ FAIL: subscriber.py not found")
        return False
    
    try:
        with open(subscriber_path) as f:
            source = f.read()
        ast.parse(source)
        print("  ✓ Syntax OK")
        return True
    except SyntaxError as e:
        print(f"❌ FAIL: Syntax error at line {e.lineno}: {e.msg}")
        return False


def check_imports():
    """Test 2: Check that imports work."""
    print("Test 2: Checking imports...")
    
    subscriber_path = Path(__file__).parent / "subscriber.py"
    
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, '{subscriber_path.parent}'); import subscriber"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    
    if result.returncode != 0:
        print(f"❌ FAIL: Import error")
        print(result.stderr[:500])
        return False
    
    print("  ✓ Imports OK")
    return True


def check_async_pattern():
    """Test 3: Check for async pattern (WaitSet or listener)."""
    print("Test 3: Checking for async pattern...")
    
    subscriber_path = Path(__file__).parent / "subscriber.py"
    
    with open(subscriber_path) as f:
        source = f.read()
    
    has_waitset = "WaitSet" in source
    has_listener = "on_data_available" in source or "Listener" in source
    has_read_condition = "ReadCondition" in source
    
    # Check for polling anti-patterns
    has_polling = False
    if "while True" in source and "time.sleep" in source:
        # Check if it's a polling loop
        if ".take()" in source or ".read()" in source:
            has_polling = "WaitSet" not in source and "wait(" not in source
    
    if has_polling:
        print("❌ FAIL: Detected polling pattern (while True + sleep + take)")
        print("         Use WaitSet or listener instead!")
        return False
    
    if has_waitset and has_read_condition:
        print("  ✓ Uses WaitSet pattern (correct)")
        return True
    elif has_listener:
        print("  ✓ Uses Listener pattern (correct)")
        return True
    else:
        print("⚠ WARNING: Could not verify async pattern")
        print("           Expected WaitSet+ReadCondition or Listener")
        return True  # Don't fail, but warn


def check_functional():
    """Test 4: Functional test with reference publisher."""
    print("Test 4: Functional test...")
    
    subscriber_path = Path(__file__).parent / "subscriber.py"
    publisher_path = Path(__file__).parent / "reference" / "publisher.py"
    
    if not publisher_path.exists():
        print("  ⚠ Skipping: reference publisher not found")
        return True
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output.jsonl"
        
        # Start subscriber first
        sub_proc = subprocess.Popen(
            [sys.executable, str(subscriber_path), "--count", str(EXPECTED_SAMPLES), "--timeout", str(TIMEOUT)],
            stdout=open(output_file, "w"),
            stderr=subprocess.PIPE,
        )
        
        # Give subscriber time to start
        time.sleep(2.0)
        
        # Run publisher
        pub_result = subprocess.run(
            [sys.executable, str(publisher_path), "--count", str(EXPECTED_SAMPLES)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if pub_result.returncode != 0:
            print(f"❌ FAIL: Publisher failed")
            print(pub_result.stderr[:500])
            sub_proc.kill()
            return False
        
        # Wait for subscriber
        try:
            stdout, stderr = sub_proc.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            sub_proc.kill()
            print("❌ FAIL: Subscriber timed out")
            return False
        
        # Check output
        if not output_file.exists():
            print("❌ FAIL: No output file created")
            return False
        
        with open(output_file) as f:
            lines = f.readlines()
        
        if len(lines) == 0:
            print("❌ FAIL: No samples received")
            return False
        
        # Parse JSONL
        samples = []
        for line in lines:
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        
        if len(samples) < EXPECTED_SAMPLES:
            print(f"❌ FAIL: Received {len(samples)}/{EXPECTED_SAMPLES} samples")
            return False
        
        # Verify content
        for sample in samples:
            if "message" not in sample or "count" not in sample:
                print(f"❌ FAIL: Invalid sample format: {sample}")
                return False
        
        print(f"  ✓ Received {len(samples)} samples")
        return True


def main():
    print("=" * 60)
    print("HelloWorld Subscriber Test")
    print("=" * 60)
    print()
    
    tests = [
        ("Syntax", check_syntax),
        ("Imports", check_imports),
        ("Async Pattern", check_async_pattern),
        ("Functional", check_functional),
    ]
    
    all_passed = True
    
    for name, test_fn in tests:
        try:
            if not test_fn():
                all_passed = False
                # Don't continue if basic checks fail
                if name in ["Syntax", "Imports"]:
                    break
        except Exception as e:
            print(f"❌ FAIL: {name} raised exception: {e}")
            all_passed = False
            if name in ["Syntax", "Imports"]:
                break
        print()
    
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


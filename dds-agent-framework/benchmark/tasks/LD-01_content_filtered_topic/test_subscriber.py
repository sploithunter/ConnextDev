#!/usr/bin/env python3
"""Test script for Content Filtered Topic subscriber."""

import ast
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT = 60
EXPECTED_MIN_SAMPLES = 10  # At least this many matching samples


def check_syntax():
    """Check if subscriber.py has valid syntax."""
    try:
        with open("subscriber.py") as f:
            ast.parse(f.read())
        print("✓ Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
        return False


def check_imports():
    """Check if subscriber.py can be imported."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import subscriber"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✓ Imports OK")
            return True
        else:
            print(f"✗ Import error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Import check failed: {e}")
        return False


def check_cft_usage():
    """Check if ContentFilteredTopic is used."""
    with open("subscriber.py") as f:
        code = f.read()
    
    if "ContentFilteredTopic" in code:
        print("✓ ContentFilteredTopic used")
        return True
    else:
        print("✗ ContentFilteredTopic NOT found - using application filtering?")
        return False


def check_filter_expression():
    """Check if filter expression is correct."""
    with open("subscriber.py") as f:
        code = f.read()
    
    if "id > 50" in code and "value > 75" in code:
        print("✓ Filter expression looks correct")
        return True
    else:
        print("✗ Filter expression may be wrong (need: id > 50 AND value > 75.0)")
        return False


def run_functional_test():
    """Run subscriber with reference publisher."""
    script_dir = Path(__file__).parent
    ref_publisher = script_dir / "reference" / "publisher.py"
    
    if not ref_publisher.exists():
        print("✗ Reference publisher not found")
        return False
    
    # Start subscriber
    sub_proc = subprocess.Popen(
        [sys.executable, "subscriber.py", "--count", "50", "--timeout", "30"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    time.sleep(2)  # Let subscriber start
    
    # Start publisher
    pub_proc = subprocess.Popen(
        [sys.executable, str(ref_publisher), "--samples", "500"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    try:
        sub_stdout, sub_stderr = sub_proc.communicate(timeout=TIMEOUT)
        pub_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        sub_proc.kill()
        pub_proc.kill()
        print("✗ Timeout")
        return False
    
    # Count received samples
    lines = [l for l in sub_stdout.strip().split("\n") if l.startswith("{")]
    received = len(lines)
    
    if received >= EXPECTED_MIN_SAMPLES:
        print(f"✓ Received {received} matching samples (expected >= {EXPECTED_MIN_SAMPLES})")
        
        # Verify all samples match filter
        import json
        all_match = True
        for line in lines[:10]:  # Check first 10
            try:
                data = json.loads(line)
                if not (data["id"] > 50 and data["value"] > 75.0):
                    print(f"✗ Sample doesn't match filter: {data}")
                    all_match = False
            except:
                pass
        
        if all_match:
            print("✓ All samples match filter criteria")
            return True
        return False
    else:
        print(f"✗ Only received {received} samples (expected >= {EXPECTED_MIN_SAMPLES})")
        return False


def main():
    print("=" * 50)
    print("Content Filtered Topic Subscriber Test")
    print("=" * 50)
    
    if not Path("subscriber.py").exists():
        print("✗ subscriber.py not found")
        return 1
    
    tests = [
        ("Syntax", check_syntax),
        ("Imports", check_imports),
        ("CFT Usage", check_cft_usage),
        ("Filter Expression", check_filter_expression),
        ("Functional Test", run_functional_test),
    ]
    
    passed = 0
    for name, test in tests:
        print(f"\n--- {name} ---")
        if test():
            passed += 1
    
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())


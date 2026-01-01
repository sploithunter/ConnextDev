#!/bin/bash
# Interoperability test: C++ Publisher → Python Subscriber
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
EXPECTED_SAMPLES=10
TIMEOUT=60

echo "=============================================="
echo "C++ → Python Interoperability Test"
echo "=============================================="

# Check if publisher was built
if [[ ! -x "${BUILD_DIR}/publisher" ]]; then
    echo "❌ FAIL: publisher not found in ${BUILD_DIR}"
    echo "   Run: mkdir build && cd build && cmake .. && make"
    exit 1
fi

echo "[1] Starting Python subscriber..."
TEMP_OUTPUT=$(mktemp)
python3 "${SCRIPT_DIR}/reference/subscriber.py" \
    --count ${EXPECTED_SAMPLES} \
    --timeout ${TIMEOUT} \
    > "${TEMP_OUTPUT}" 2>/dev/null &
SUB_PID=$!

# Give subscriber time to start
sleep 2

echo "[2] Running C++ publisher..."
timeout 30 "${BUILD_DIR}/publisher" --count ${EXPECTED_SAMPLES} 2>&1 | head -20

# Wait for subscriber
echo "[3] Waiting for subscriber..."
wait ${SUB_PID} || true

# Check results
RECEIVED=$(wc -l < "${TEMP_OUTPUT}" | tr -d ' ')
echo "[4] Checking results..."
echo "    Received: ${RECEIVED}/${EXPECTED_SAMPLES} samples"

if [[ ${RECEIVED} -ge ${EXPECTED_SAMPLES} ]]; then
    echo ""
    echo "=============================================="
    echo "✓ INTEROP TEST PASSED"
    echo "=============================================="
    rm -f "${TEMP_OUTPUT}"
    exit 0
else
    echo ""
    echo "=============================================="
    echo "❌ INTEROP TEST FAILED"
    echo "=============================================="
    echo "Output received:"
    cat "${TEMP_OUTPUT}"
    rm -f "${TEMP_OUTPUT}"
    exit 1
fi


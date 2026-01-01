#!/bin/bash
# Test script for Routing Service scenario
# 
# Prerequisites:
# - RTI Routing Service installed ($NDDSHOME/bin/rtiroutingservice)
# - Python with rti.connextdds

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"

echo "=== Routing Service Test ==="
echo "Config: $CONFIG_DIR/routing_config.xml"
echo ""

# Check if routing service exists
if [ -z "$NDDSHOME" ]; then
    echo "ERROR: NDDSHOME not set"
    exit 1
fi

ROUTING_SERVICE="$NDDSHOME/bin/rtiroutingservice"
if [ ! -f "$ROUTING_SERVICE" ]; then
    echo "ERROR: rtiroutingservice not found at $ROUTING_SERVICE"
    exit 1
fi

echo "Starting subscriber on Domain 1..."
python "$SCRIPT_DIR/subscriber_domain1.py" --count 10 --timeout 30 > /tmp/routing_output.jsonl 2>/tmp/routing_sub.log &
SUB_PID=$!

sleep 2

echo "Starting Routing Service..."
$ROUTING_SERVICE -cfgFile "$CONFIG_DIR/routing_config.xml" -cfgName SensorDataRouter &
RS_PID=$!

sleep 3

echo "Starting publisher on Domain 0..."
python "$SCRIPT_DIR/publisher_domain0.py" --count 10 2>&1

sleep 3

echo ""
echo "Stopping services..."
kill $RS_PID 2>/dev/null || true
kill $SUB_PID 2>/dev/null || true

wait $SUB_PID 2>/dev/null || true

echo ""
echo "=== Results ==="
echo "Subscriber output:"
cat /tmp/routing_output.jsonl

echo ""
echo "Subscriber log:"
cat /tmp/routing_sub.log


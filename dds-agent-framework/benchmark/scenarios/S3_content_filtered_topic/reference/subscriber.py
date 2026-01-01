#!/usr/bin/env python3
"""Content Filtered Topic - Subscriber.

Uses ContentFilteredTopic to only receive HIGH (3) and CRITICAL (4) alerts.
The filtering happens on the DDS layer, reducing network traffic.
"""

import argparse
import json
import signal
import sys
import time

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_alert_type():
    t = dds.StructType("SensorAlert")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_type", dds.StringType(32)))
    t.add_member(dds.Member("severity", dds.Int32Type()))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("message", dds.StringType(256)))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--min-severity", type=int, default=3,
                        help="Minimum severity to filter (3=HIGH, 4=CRITICAL)")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    alert_type = create_alert_type()
    topic = dds.DynamicData.Topic(participant, "SensorAlerts", alert_type)
    
    # Create ContentFilteredTopic with SQL-like filter
    # Filter expression: severity >= 3 (HIGH and CRITICAL only)
    filter_expression = f"severity >= %0"
    filter_params = [str(args.min_severity)]
    
    cft = dds.DynamicData.ContentFilteredTopic(
        topic,
        "HighSeverityAlerts",  # CFT name
        dds.Filter(filter_expression, filter_params)
    )
    
    print(f"Content filter: severity >= {args.min_severity}", file=sys.stderr)
    
    subscriber = dds.Subscriber(participant)
    
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    # Create reader on ContentFilteredTopic, NOT the base topic
    reader = dds.DynamicData.DataReader(subscriber, cft, reader_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    sample_count = 0
    start_time = time.time()
    
    while running:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in reader.take():
                if sample.info.valid:
                    severity = sample.data["severity"]
                    
                    # Verify the filter worked
                    assert severity >= args.min_severity, \
                        f"Filter failed! Got severity={severity}"
                    
                    output = {
                        "sensor_id": sample.data["sensor_id"],
                        "sensor_type": sample.data["sensor_type"],
                        "severity": severity,
                        "value": sample.data["value"],
                        "message": sample.data["message"],
                    }
                    print(json.dumps(output), flush=True)
                    sample_count += 1
    
    print(f"\nReceived {sample_count} filtered samples (severity >= {args.min_severity})", 
          file=sys.stderr)


if __name__ == "__main__":
    main()


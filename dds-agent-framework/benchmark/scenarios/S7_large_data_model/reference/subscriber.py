#!/usr/bin/env python3
"""Large Data Model Subscriber.

Subscribes to UAV telemetry with ~440 fields.
Outputs received data as JSONL.
"""

import argparse
import json
import signal
import sys
import time
from pathlib import Path

import rti.connextdds as dds

from schema_converter import load_schema, create_dds_type_from_schema, flatten_schema


running = True


def signal_handler(signum, frame):
    global running
    running = False


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--timeout", "-t", type=float, default=60.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--summary-only", action="store_true",
                        help="Only output summary, not full data")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load schema
    schema_path = Path(__file__).parent.parent / "input" / "uav_telemetry_schema.json"
    schema = load_schema(str(schema_path))
    
    # Create DDS type
    uav_type = create_dds_type_from_schema(schema, "UAVTelemetry")
    
    # Create DDS entities
    participant = dds.DomainParticipant(args.domain)
    topic = dds.DynamicData.Topic(participant, "UAVTelemetry", uav_type)
    
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    # WaitSet
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    # Get field list
    fields = flatten_schema(schema)
    field_names = [name for name, _ in fields]
    
    print(f"Listening for {args.count} samples ({len(field_names)} fields each)...", 
          file=sys.stderr)
    
    received = 0
    start_time = time.time()
    
    while running and received < args.count:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            print("Timeout reached", file=sys.stderr)
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in reader.take():
                if sample.info.valid:
                    # Extract all fields
                    data = {}
                    for field_name in field_names:
                        try:
                            data[field_name] = sample.data[field_name]
                        except Exception:
                            pass
                    
                    received += 1
                    
                    if args.summary_only:
                        # Just output key fields
                        summary = {
                            "message_id": data.get("message_id"),
                            "vehicle_id": data.get("vehicle_id"),
                            "timestamp_utc_ms": data.get("timestamp_utc_ms"),
                            "gps_lat": data.get("gps_gps_latitude_deg"),
                            "gps_lon": data.get("gps_gps_longitude_deg"),
                            "fields_received": len(data),
                        }
                        print(json.dumps(summary), flush=True)
                    else:
                        print(json.dumps(data), flush=True)
                    
                    if received >= args.count:
                        break
    
    print(f"\nReceived {received}/{args.count} samples", file=sys.stderr)


if __name__ == "__main__":
    main()


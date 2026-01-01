#!/usr/bin/env python3
"""V2 Subscriber - Extended type.

Can receive from BOTH V1 and V2 publishers:
- V1 publisher: gets base fields, new fields have defaults
- V2 publisher: gets all fields
"""

import argparse
import json
import signal
import sys
import time

import rti.connextdds as dds

from sensor_types import create_sensor_v2_type


running = True


def signal_handler(signum, frame):
    global running
    running = False


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_v2_type()
    topic = dds.DynamicData.Topic(participant, "SensorReading", sensor_type)
    
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    print(f"[V2 Subscriber] Waiting for SensorReading (8 fields)...", file=sys.stderr)
    
    received = 0
    start_time = time.time()
    
    while running and received < args.count:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in reader.take():
                if sample.info.valid:
                    # V2 knows about all 8 fields
                    data = {
                        "version": "v2",
                        # V1 fields
                        "sensor_id": sample.data["sensor_id"],
                        "value": sample.data["value"],
                        "timestamp": sample.data["timestamp"],
                        "unit": sample.data["unit"],
                        # V2 new fields
                        "quality": sample.data["quality"],
                        "location_lat": sample.data["location_lat"],
                        "location_lon": sample.data["location_lon"],
                        "metadata": sample.data["metadata"],
                    }
                    print(json.dumps(data), flush=True)
                    received += 1
    
    print(f"\n[V2 Subscriber] Received {received} samples", file=sys.stderr)


if __name__ == "__main__":
    main()


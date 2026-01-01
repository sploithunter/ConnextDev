#!/usr/bin/env python3
"""Subscriber on Domain 1 - receives routed data from routing service."""

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


def create_routed_sensor_type():
    """Type that routing service transforms to."""
    t = dds.StructType("RoutedSensorData")
    t.add_member(dds.Member("routed_sensor_id", dds.StringType(128)))
    t.add_member(dds.Member("original_value", dds.Float64Type()))
    t.add_member(dds.Member("processed_value", dds.Float64Type()))
    t.add_member(dds.Member("source_timestamp", dds.Int64Type()))
    t.add_member(dds.Member("routing_timestamp", dds.Int64Type()))
    t.add_member(dds.Member("quality", dds.Int32Type()))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=1)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    routed_type = create_routed_sensor_type()
    topic = dds.DynamicData.Topic(participant, "RoutedSensorData", routed_type)
    
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    print(f"Waiting for routed data on Domain {args.domain}...", file=sys.stderr)
    
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
                    data = {
                        "routed_sensor_id": sample.data["routed_sensor_id"],
                        "original_value": sample.data["original_value"],
                        "processed_value": sample.data["processed_value"],
                        "quality": sample.data["quality"],
                    }
                    print(json.dumps(data), flush=True)
                    received += 1
    
    print(f"\nReceived {received} routed samples", file=sys.stderr)


if __name__ == "__main__":
    main()


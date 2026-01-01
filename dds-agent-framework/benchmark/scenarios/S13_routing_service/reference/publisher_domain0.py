#!/usr/bin/env python3
"""Publisher on Domain 0 - source for routing service."""

import argparse
import sys
import time

import rti.connextdds as dds


def create_sensor_type():
    t = dds.StructType("SensorData")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Int64Type()))
    t.add_member(dds.Member("quality", dds.Int32Type()))
    return t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_type()
    topic = dds.DynamicData.Topic(participant, "SensorData", sensor_type)
    
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)
    
    print(f"Publishing {args.count} samples to Domain {args.domain}", file=sys.stderr)
    
    for i in range(args.count):
        sample = dds.DynamicData(sensor_type)
        sample["sensor_id"] = f"SENSOR_{i % 5:03d}"
        sample["value"] = 20.0 + i * 0.5
        sample["timestamp"] = int(time.time() * 1000)
        sample["quality"] = 2
        
        writer.write(sample)
        print(f"[{i+1}] Published: {sample['sensor_id']} = {sample['value']}", file=sys.stderr)
        time.sleep(0.5)
    
    time.sleep(2.0)
    print("Done", file=sys.stderr)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""V1 Publisher - Original type."""

import argparse
import sys
import time

import rti.connextdds as dds

from sensor_types import create_sensor_v1_type


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_v1_type()
    topic = dds.DynamicData.Topic(participant, "SensorReading", sensor_type)
    
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)
    
    print(f"[V1 Publisher] Sending {args.count} samples (4 fields)", file=sys.stderr)
    
    for i in range(args.count):
        sample = dds.DynamicData(sensor_type)
        sample["sensor_id"] = f"SENSOR_{i % 3:03d}"
        sample["value"] = 20.0 + i * 0.5
        sample["timestamp"] = int(time.time() * 1000)
        sample["unit"] = "celsius"
        
        writer.write(sample)
        print(f"  [{i+1}] V1: {sample['sensor_id']} = {sample['value']}", file=sys.stderr)
        time.sleep(0.3)
    
    time.sleep(2.0)
    print("[V1 Publisher] Done", file=sys.stderr)


if __name__ == "__main__":
    main()


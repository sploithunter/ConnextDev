#!/usr/bin/env python3
"""V2 Publisher - Extended type.

Publishes the extended type with additional fields.
V1 subscribers should still receive data (ignoring new fields).
V2 subscribers get all fields.
"""

import argparse
import random
import sys
import time

import rti.connextdds as dds

from sensor_types import create_sensor_v2_type


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_v2_type()
    topic = dds.DynamicData.Topic(participant, "SensorReading", sensor_type)
    
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)
    
    print(f"[V2 Publisher] Sending {args.count} samples (8 fields)", file=sys.stderr)
    
    for i in range(args.count):
        sample = dds.DynamicData(sensor_type)
        
        # V1 fields (same as before)
        sample["sensor_id"] = f"SENSOR_{i % 3:03d}"
        sample["value"] = 20.0 + i * 0.5
        sample["timestamp"] = int(time.time() * 1000)
        sample["unit"] = "celsius"
        
        # V2 NEW fields
        sample["quality"] = random.choice([0, 1, 2, 2, 2])  # Mostly good
        sample["location_lat"] = 37.7749 + random.uniform(-0.01, 0.01)
        sample["location_lon"] = -122.4194 + random.uniform(-0.01, 0.01)
        sample["metadata"] = f"Extended data sample {i+1}"
        
        writer.write(sample)
        print(f"  [{i+1}] V2: {sample['sensor_id']} = {sample['value']} "
              f"(quality={sample['quality']}, lat={sample['location_lat']:.4f})", 
              file=sys.stderr)
        time.sleep(0.3)
    
    time.sleep(2.0)
    print("[V2 Publisher] Done", file=sys.stderr)


if __name__ == "__main__":
    main()


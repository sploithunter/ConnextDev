#!/usr/bin/env python3
"""Reference publisher for Content Filtered Topic test.

Publishes sensor readings from 100 sensors with varying values.
The subscriber should use ContentFilteredTopic to receive only matching samples.
"""

import argparse
import random
import time
import sys

import rti.connextdds as dds


def create_sensor_type():
    sensor_type = dds.StructType("SensorReading")
    sensor_type.add_member(dds.Member("id", dds.Int32Type()))
    sensor_type.add_member(dds.Member("value", dds.Float64Type()))
    sensor_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    return sensor_type


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", "-s", type=int, default=1000, 
                        help="Total samples to publish")
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    
    sensor_type = create_sensor_type()
    topic = dds.DynamicData.Topic(participant, "SensorReadings", sensor_type)
    
    publisher = dds.Publisher(participant)
    
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    # Wait for subscriber discovery
    time.sleep(2.0)
    
    # Publish samples from 100 sensors with varying values
    random.seed(42)  # Deterministic for testing
    
    matching_count = 0
    
    for i in range(args.samples):
        sensor_id = (i % 100) + 1  # Sensors 1-100
        value = random.uniform(0.0, 100.0)  # Random value 0-100
        
        sample = dds.DynamicData(sensor_type)
        sample["id"] = sensor_id
        sample["value"] = value
        sample["timestamp"] = time.time()
        
        # Track how many match the filter: id > 50 AND value > 75.0
        if sensor_id > 50 and value > 75.0:
            matching_count += 1
        
        writer.write(sample)
        
        if (i + 1) % 100 == 0:
            print(f"Published {i + 1}/{args.samples}", file=sys.stderr)
        
        time.sleep(0.01)  # 10ms between samples
    
    # Allow time for delivery
    time.sleep(2.0)
    
    print(f"Published {args.samples} total samples", file=sys.stderr)
    print(f"Matching filter (id>50 AND value>75): {matching_count}", file=sys.stderr)


if __name__ == "__main__":
    main()


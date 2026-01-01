#!/usr/bin/env python3
"""Sensor data generator for testing the transformer."""

import argparse
import random
import sys
import time

import rti.connextdds as dds


def create_sensor_reading_type():
    t = dds.StructType("SensorReading")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_type", dds.StringType(32)))
    t.add_member(dds.Member("raw_value", dds.Float64Type()))
    t.add_member(dds.Member("unit", dds.StringType(16)))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    t.add_member(dds.Member("quality", dds.Int32Type()))
    return t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=50)
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--rate-hz", type=float, default=10)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_reading_type()
    topic = dds.DynamicData.Topic(participant, "SensorReadings", sensor_type)
    
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)
    
    sensors = [
        ("TEMP_001", "TEMPERATURE", 25.0, 5.0, "C"),
        ("TEMP_002", "TEMPERATURE", 30.0, 8.0, "C"),
        ("PRESS_001", "PRESSURE", 101325.0, 500.0, "Pa"),
        ("HUM_001", "HUMIDITY", 50.0, 15.0, "%"),
    ]
    
    delay = 1.0 / args.rate_hz
    
    print(f"Generating {args.count} readings at {args.rate_hz} Hz", file=sys.stderr)
    
    for i in range(args.count):
        sensor_id, sensor_type_name, base_value, variation, unit = random.choice(sensors)
        
        # Add some drift and noise
        value = base_value + random.gauss(0, variation) + (i * 0.1)
        
        # Occasional bad quality
        quality = 2 if random.random() > 0.05 else random.randint(0, 1)
        
        sample = dds.DynamicData(sensor_type)
        sample["sensor_id"] = sensor_id
        sample["sensor_type"] = sensor_type_name
        sample["raw_value"] = value
        sample["unit"] = unit
        sample["timestamp_ms"] = int(time.time() * 1000)
        sample["quality"] = quality
        
        writer.write(sample)
        
        if (i + 1) % 10 == 0:
            print(f"[{i+1}/{args.count}] Generated readings", file=sys.stderr)
        
        time.sleep(delay)
    
    time.sleep(2.0)
    print(f"Generated {args.count} readings", file=sys.stderr)


if __name__ == "__main__":
    main()


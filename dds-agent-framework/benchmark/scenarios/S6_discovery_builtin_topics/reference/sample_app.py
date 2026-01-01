#!/usr/bin/env python3
"""Simple DDS app to be discovered by the monitor."""

import argparse
import signal
import sys
import time

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_sensor_type():
    t = dds.StructType("SensorData")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--pub", action="store_true", help="Create publisher")
    parser.add_argument("--sub", action="store_true", help="Create subscriber")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    sensor_type = create_sensor_type()
    topic = dds.DynamicData.Topic(participant, "SensorData", sensor_type)
    
    writer = None
    reader = None
    
    if args.pub:
        publisher = dds.Publisher(participant)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
        print("Publisher created", file=sys.stderr)
    
    if args.sub:
        subscriber = dds.Subscriber(participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
        print("Subscriber created", file=sys.stderr)
    
    start = time.time()
    while running and (time.time() - start) < args.timeout:
        if writer:
            sample = dds.DynamicData(sensor_type)
            sample["sensor_id"] = "SENSOR_001"
            sample["value"] = 42.0
            sample["timestamp"] = time.time()
            writer.write(sample)
        time.sleep(1.0)
    
    print("Shutting down", file=sys.stderr)


if __name__ == "__main__":
    main()


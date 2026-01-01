#!/usr/bin/env python3
"""Sensor Data Subscriber - BROKEN: Uses VOLATILE durability.

BUG: When this subscriber starts after the publisher,
it misses samples that were already sent.

Your task: Fix the QoS configuration so this subscriber
receives ALL samples regardless of when it starts.
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


def create_sensor_type():
    sensor_type = dds.StructType("SensorData")
    sensor_type.add_member(dds.Member("sensor_id", dds.StringType(64)))
    sensor_type.add_member(dds.Member("value", dds.Float64Type()))
    sensor_type.add_member(dds.Member("sequence", dds.Int32Type()))
    return sensor_type


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
    
    sensor_type = create_sensor_type()
    topic = dds.DynamicData.Topic(participant, "SensorData", sensor_type)
    
    subscriber = dds.Subscriber(participant)
    
    # BUG: VOLATILE durability means we can't receive historical data
    # BUG: BEST_EFFORT means samples can be lost
    reader_qos = dds.DataReaderQos()
    reader_qos.durability.kind = dds.DurabilityKind.VOLATILE  # <-- PROBLEM
    reader_qos.reliability.kind = dds.ReliabilityKind.BEST_EFFORT  # <-- PROBLEM
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    # WaitSet pattern
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    received_count = 0
    start_time = time.time()
    
    while running and received_count < args.count:
        elapsed = time.time() - start_time
        remaining = args.timeout - elapsed
        
        if remaining <= 0:
            break
        
        wait_time = min(1.0, remaining)
        active = waitset.wait(dds.Duration.from_seconds(wait_time))
        
        if read_condition in active:
            for sample in reader.take():
                if sample.info.valid:
                    output = {
                        "sensor_id": sample.data["sensor_id"],
                        "value": sample.data["value"],
                        "sequence": sample.data["sequence"],
                    }
                    print(json.dumps(output), flush=True)
                    received_count += 1
                    
                    if received_count >= args.count:
                        break
    
    print(f"Received {received_count}/{args.count} samples", file=sys.stderr)
    return 0 if received_count >= args.count else 1


if __name__ == "__main__":
    sys.exit(main())


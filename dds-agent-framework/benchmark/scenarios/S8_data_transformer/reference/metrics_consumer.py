#!/usr/bin/env python3
"""Metrics consumer - receives ProcessedMetrics from transformer."""

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


def create_processed_metrics_type():
    t = dds.StructType("ProcessedMetrics")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_type", dds.StringType(32)))
    t.add_member(dds.Member("window_start_ms", dds.Int64Type()))
    t.add_member(dds.Member("window_end_ms", dds.Int64Type()))
    t.add_member(dds.Member("sample_count", dds.Int32Type()))
    t.add_member(dds.Member("value_min", dds.Float64Type()))
    t.add_member(dds.Member("value_max", dds.Float64Type()))
    t.add_member(dds.Member("value_mean", dds.Float64Type()))
    t.add_member(dds.Member("value_stddev", dds.Float64Type()))
    t.add_member(dds.Member("value_latest", dds.Float64Type()))
    t.add_member(dds.Member("converted_value", dds.Float64Type()))
    t.add_member(dds.Member("converted_unit", dds.StringType(16)))
    t.add_member(dds.Member("alert_level", dds.StringType(16)))
    t.add_member(dds.Member("good_samples_pct", dds.Float64Type()))
    return t


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
    metrics_type = create_processed_metrics_type()
    topic = dds.DynamicData.Topic(participant, "ProcessedMetrics", metrics_type)
    
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    received = 0
    start_time = time.time()
    
    print("Waiting for ProcessedMetrics...", file=sys.stderr)
    
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
                        "sensor_id": sample.data["sensor_id"],
                        "sensor_type": sample.data["sensor_type"],
                        "sample_count": sample.data["sample_count"],
                        "value_mean": sample.data["value_mean"],
                        "value_stddev": sample.data["value_stddev"],
                        "converted_value": sample.data["converted_value"],
                        "converted_unit": sample.data["converted_unit"],
                        "alert_level": sample.data["alert_level"],
                        "good_samples_pct": sample.data["good_samples_pct"],
                    }
                    
                    print(json.dumps(data), flush=True)
                    received += 1
                    
                    if received >= args.count:
                        break
    
    print(f"\nReceived {received} metrics", file=sys.stderr)


if __name__ == "__main__":
    main()


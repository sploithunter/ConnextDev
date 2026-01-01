#!/usr/bin/env python3
"""Data Transformer - Subscriber + Publisher in one application.

This is a common pattern for:
- Protocol gateways
- Data aggregators
- Unit converters
- Data filters/enrichers
- Rate limiters

Example: Raw sensor data → Processed analytics data
- Subscribes to "SensorReadings" (raw)
- Aggregates, filters, computes statistics
- Publishes to "ProcessedMetrics" (processed)
"""

import argparse
import json
import math
import signal
import statistics
import sys
import time
from collections import defaultdict
from typing import Dict, List

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_sensor_reading_type():
    """Raw sensor reading from field devices."""
    t = dds.StructType("SensorReading")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_type", dds.StringType(32)))  # TEMPERATURE, PRESSURE, HUMIDITY
    t.add_member(dds.Member("raw_value", dds.Float64Type()))
    t.add_member(dds.Member("unit", dds.StringType(16)))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    t.add_member(dds.Member("quality", dds.Int32Type()))  # 0=BAD, 1=UNCERTAIN, 2=GOOD
    return t


def create_processed_metrics_type():
    """Processed/aggregated metrics output."""
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
    t.add_member(dds.Member("converted_value", dds.Float64Type()))  # Unit converted
    t.add_member(dds.Member("converted_unit", dds.StringType(16)))
    t.add_member(dds.Member("alert_level", dds.StringType(16)))  # NORMAL, WARNING, CRITICAL
    t.add_member(dds.Member("good_samples_pct", dds.Float64Type()))
    return t


class SensorAggregator:
    """Aggregates sensor readings and computes statistics."""
    
    def __init__(self, window_size_ms: int = 5000):
        self.window_size_ms = window_size_ms
        self.readings: Dict[str, List[dict]] = defaultdict(list)
        self.last_output: Dict[str, int] = {}
    
    def add_reading(self, reading: dict):
        """Add a reading to the buffer."""
        sensor_id = reading["sensor_id"]
        self.readings[sensor_id].append(reading)
        
        # Prune old readings
        now = reading["timestamp_ms"]
        self.readings[sensor_id] = [
            r for r in self.readings[sensor_id]
            if now - r["timestamp_ms"] < self.window_size_ms * 2
        ]
    
    def should_output(self, sensor_id: str, current_time_ms: int) -> bool:
        """Check if we should output aggregated metrics."""
        last = self.last_output.get(sensor_id, 0)
        return current_time_ms - last >= self.window_size_ms
    
    def compute_metrics(self, sensor_id: str) -> dict:
        """Compute aggregated metrics for a sensor."""
        readings = self.readings.get(sensor_id, [])
        
        if not readings:
            return None
        
        # Filter to window
        now = readings[-1]["timestamp_ms"]
        window_readings = [
            r for r in readings
            if now - r["timestamp_ms"] < self.window_size_ms
        ]
        
        if not window_readings:
            return None
        
        values = [r["raw_value"] for r in window_readings]
        qualities = [r["quality"] for r in window_readings]
        
        # Compute statistics
        metrics = {
            "sensor_id": sensor_id,
            "sensor_type": window_readings[0]["sensor_type"],
            "window_start_ms": window_readings[0]["timestamp_ms"],
            "window_end_ms": window_readings[-1]["timestamp_ms"],
            "sample_count": len(values),
            "value_min": min(values),
            "value_max": max(values),
            "value_mean": statistics.mean(values),
            "value_stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "value_latest": values[-1],
            "good_samples_pct": (qualities.count(2) / len(qualities)) * 100,
        }
        
        # Unit conversion
        original_unit = window_readings[0]["unit"]
        converted_value, converted_unit = self._convert_unit(
            metrics["value_mean"], 
            window_readings[0]["sensor_type"],
            original_unit
        )
        metrics["converted_value"] = converted_value
        metrics["converted_unit"] = converted_unit
        
        # Alert level based on thresholds
        metrics["alert_level"] = self._compute_alert_level(
            window_readings[0]["sensor_type"],
            metrics["value_mean"]
        )
        
        self.last_output[sensor_id] = now
        return metrics
    
    def _convert_unit(self, value: float, sensor_type: str, unit: str):
        """Convert units (e.g., Celsius to Fahrenheit)."""
        if sensor_type == "TEMPERATURE" and unit == "C":
            return (value * 9/5) + 32, "F"
        elif sensor_type == "PRESSURE" and unit == "Pa":
            return value / 1000, "kPa"
        elif sensor_type == "HUMIDITY" and unit == "%":
            return value, "%"
        else:
            return value, unit
    
    def _compute_alert_level(self, sensor_type: str, value: float) -> str:
        """Compute alert level based on thresholds."""
        if sensor_type == "TEMPERATURE":
            if value > 80:
                return "CRITICAL"
            elif value > 60:
                return "WARNING"
        elif sensor_type == "PRESSURE":
            if value < 90000 or value > 110000:
                return "CRITICAL"
            elif value < 95000 or value > 105000:
                return "WARNING"
        elif sensor_type == "HUMIDITY":
            if value > 90 or value < 10:
                return "WARNING"
        
        return "NORMAL"


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=60.0)
    parser.add_argument("--window-ms", type=int, default=3000,
                        help="Aggregation window in milliseconds")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    # Create types and topics
    sensor_type = create_sensor_reading_type()
    metrics_type = create_processed_metrics_type()
    
    sensor_topic = dds.DynamicData.Topic(participant, "SensorReadings", sensor_type)
    metrics_topic = dds.DynamicData.Topic(participant, "ProcessedMetrics", metrics_type)
    
    # Subscriber for raw readings
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    reader = dds.DynamicData.DataReader(subscriber, sensor_topic, reader_qos)
    
    # Publisher for processed metrics
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, metrics_topic, writer_qos)
    
    # WaitSet
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    # Aggregator
    aggregator = SensorAggregator(window_size_ms=args.window_ms)
    
    readings_received = 0
    metrics_published = 0
    start_time = time.time()
    
    print("Transformer running...", file=sys.stderr)
    print(f"  Subscribing: SensorReadings", file=sys.stderr)
    print(f"  Publishing: ProcessedMetrics", file=sys.stderr)
    print(f"  Window: {args.window_ms}ms", file=sys.stderr)
    
    while running:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(0.5, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in reader.take():
                if sample.info.valid:
                    reading = {
                        "sensor_id": sample.data["sensor_id"],
                        "sensor_type": sample.data["sensor_type"],
                        "raw_value": sample.data["raw_value"],
                        "unit": sample.data["unit"],
                        "timestamp_ms": sample.data["timestamp_ms"],
                        "quality": sample.data["quality"],
                    }
                    
                    aggregator.add_reading(reading)
                    readings_received += 1
                    
                    # Check if we should output metrics
                    if aggregator.should_output(reading["sensor_id"], reading["timestamp_ms"]):
                        metrics = aggregator.compute_metrics(reading["sensor_id"])
                        
                        if metrics:
                            # Write to DDS
                            metrics_sample = dds.DynamicData(metrics_type)
                            for key, value in metrics.items():
                                metrics_sample[key] = value
                            
                            writer.write(metrics_sample)
                            metrics_published += 1
                            
                            # Also output to stdout as JSONL
                            print(json.dumps(metrics), flush=True)
    
    print(f"\nTransformer complete:", file=sys.stderr)
    print(f"  Readings received: {readings_received}", file=sys.stderr)
    print(f"  Metrics published: {metrics_published}", file=sys.stderr)


if __name__ == "__main__":
    main()


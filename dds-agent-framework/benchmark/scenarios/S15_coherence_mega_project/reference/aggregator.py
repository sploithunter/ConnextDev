#!/usr/bin/env python3
"""
Data Aggregator - Calculates rolling statistics from sensor readings.

Phase 2: Subscribes to temperature, publishes aggregated metrics.
Phase 4: Extended to also aggregate pressure readings.
"""

import argparse
import collections
import signal
import sys
import time

import rti.connextdds as dds

from types_v1 import (
    create_temperature_reading_v1,  # V1 subscriber (compatible with V2 publisher)
    create_pressure_reading,
    create_aggregated_metrics,
)


class DataAggregator:
    """Aggregates sensor readings into rolling statistics."""
    
    def __init__(self, domain_id: int = 0, window_size: int = 10):
        self.running = True
        self.domain_id = domain_id
        self.window_size = window_size
        
        # Rolling windows per sensor
        self.temp_windows: dict[str, collections.deque] = {}
        self.pressure_windows: dict[str, collections.deque] = {}
        
        self._setup_dds()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Subscribe to temperature (V1 type - compatible with V2 publisher)
        temp_type = create_temperature_reading_v1()
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "TemperatureReading", temp_type
        )
        
        # Subscribe to pressure
        pressure_type = create_pressure_reading()
        self.pressure_topic = dds.DynamicData.Topic(
            self.participant, "PressureReading", pressure_type
        )
        
        # Aggregated metrics topic
        metrics_type = create_aggregated_metrics()
        self.metrics_topic = dds.DynamicData.Topic(
            self.participant, "AggregatedMetrics", metrics_type
        )
        
        # Subscriber
        subscriber = dds.Subscriber(self.participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        
        self.temp_reader = dds.DynamicData.DataReader(
            subscriber, self.temp_topic, reader_qos
        )
        self.pressure_reader = dds.DynamicData.DataReader(
            subscriber, self.pressure_topic, reader_qos
        )
        
        # Publisher for metrics
        publisher = dds.Publisher(self.participant)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        
        self.metrics_writer = dds.DynamicData.DataWriter(
            publisher, self.metrics_topic, writer_qos
        )
        
        # WaitSet for async reading
        self.waitset = dds.WaitSet()
        self.temp_condition = dds.ReadCondition(
            self.temp_reader, dds.DataState.any_data
        )
        self.pressure_condition = dds.ReadCondition(
            self.pressure_reader, dds.DataState.any_data
        )
        self.waitset.attach_condition(self.temp_condition)
        self.waitset.attach_condition(self.pressure_condition)
        
        self.metrics_type = metrics_type
        
    def _process_temperature(self):
        """Process temperature readings and publish aggregates."""
        for sample in self.temp_reader.take():
            if sample.info.valid:
                sensor_id = sample.data["sensor_id"]
                value = sample.data["value_celsius"]
                timestamp = sample.data["timestamp_ms"]
                
                if sensor_id not in self.temp_windows:
                    self.temp_windows[sensor_id] = collections.deque(
                        maxlen=self.window_size
                    )
                    
                self.temp_windows[sensor_id].append((value, timestamp))
                
                # Publish aggregate if window is full
                if len(self.temp_windows[sensor_id]) >= self.window_size:
                    self._publish_aggregate(
                        sensor_id, "temperature", 
                        self.temp_windows[sensor_id]
                    )
                    
    def _process_pressure(self):
        """Process pressure readings and publish aggregates."""
        for sample in self.pressure_reader.take():
            if sample.info.valid:
                sensor_id = sample.data["sensor_id"]
                value = sample.data["value_kpa"]
                timestamp = sample.data["timestamp_ms"]
                
                if sensor_id not in self.pressure_windows:
                    self.pressure_windows[sensor_id] = collections.deque(
                        maxlen=self.window_size
                    )
                    
                self.pressure_windows[sensor_id].append((value, timestamp))
                
                if len(self.pressure_windows[sensor_id]) >= self.window_size:
                    self._publish_aggregate(
                        sensor_id, "pressure",
                        self.pressure_windows[sensor_id]
                    )
                    
    def _publish_aggregate(self, sensor_id: str, metric_type: str, 
                           window: collections.deque):
        """Publish aggregated metrics."""
        values = [v for v, _ in window]
        timestamps = [t for _, t in window]
        
        sample = dds.DynamicData(self.metrics_type)
        sample["sensor_id"] = sensor_id
        sample["metric_type"] = metric_type
        sample["avg_value"] = sum(values) / len(values)
        sample["min_value"] = min(values)
        sample["max_value"] = max(values)
        sample["sample_count"] = len(values)
        sample["window_start_ms"] = min(timestamps)
        sample["window_end_ms"] = max(timestamps)
        
        self.metrics_writer.write(sample)
        print(f"[Aggregator] {sensor_id} ({metric_type}): avg={sample['avg_value']:.2f}", 
              file=sys.stderr)
        
    def run(self):
        """Run the aggregator."""
        print(f"[Aggregator] Starting (window={self.window_size})", file=sys.stderr)
        
        while self.running:
            active = self.waitset.wait(dds.Duration.from_seconds(1.0))
            
            if self.temp_condition in active:
                self._process_temperature()
            if self.pressure_condition in active:
                self._process_pressure()
                
    def stop(self):
        """Stop the aggregator."""
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--window", "-w", type=int, default=10,
                        help="Rolling window size")
    args = parser.parse_args()
    
    aggregator = DataAggregator(args.domain, args.window)
    
    def signal_handler(signum, frame):
        aggregator.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    aggregator.run()


if __name__ == "__main__":
    main()


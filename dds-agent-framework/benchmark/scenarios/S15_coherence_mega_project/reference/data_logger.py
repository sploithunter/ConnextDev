#!/usr/bin/env python3
"""
Data Logger - Logs all DDS data to JSONL files.

Phase 6: Historical logging with TRANSIENT_LOCAL durability
to catch late-joining data.
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import rti.connextdds as dds

from types_v1 import (
    create_temperature_reading_v1,
    create_pressure_reading,
    create_aggregated_metrics,
    create_system_alert,
)


class DataLogger:
    """Logs all sensor data to JSONL files."""
    
    def __init__(self, domain_id: int = 0, output_dir: str = "./logs"):
        self.running = True
        self.domain_id = domain_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.sample_counts = {
            "temperature": 0,
            "pressure": 0,
            "metrics": 0,
            "alerts": 0,
        }
        
        self._setup_dds()
        self._open_log_files()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Create topics for all data types
        temp_type = create_temperature_reading_v1()
        pressure_type = create_pressure_reading()
        metrics_type = create_aggregated_metrics()
        alert_type = create_system_alert()
        
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "TemperatureReading", temp_type
        )
        self.pressure_topic = dds.DynamicData.Topic(
            self.participant, "PressureReading", pressure_type
        )
        self.metrics_topic = dds.DynamicData.Topic(
            self.participant, "AggregatedMetrics", metrics_type
        )
        self.alert_topic = dds.DynamicData.Topic(
            self.participant, "SystemAlert", alert_type
        )
        
        # Subscriber with TRANSIENT_LOCAL to get historical data
        subscriber = dds.Subscriber(self.participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        self.temp_reader = dds.DynamicData.DataReader(
            subscriber, self.temp_topic, reader_qos
        )
        self.pressure_reader = dds.DynamicData.DataReader(
            subscriber, self.pressure_topic, reader_qos
        )
        self.metrics_reader = dds.DynamicData.DataReader(
            subscriber, self.metrics_topic, reader_qos
        )
        self.alert_reader = dds.DynamicData.DataReader(
            subscriber, self.alert_topic, reader_qos
        )
        
        # WaitSet for all readers
        self.waitset = dds.WaitSet()
        self.conditions = {}
        
        for name, reader in [
            ("temperature", self.temp_reader),
            ("pressure", self.pressure_reader),
            ("metrics", self.metrics_reader),
            ("alerts", self.alert_reader),
        ]:
            condition = dds.ReadCondition(reader, dds.DataState.any_data)
            self.waitset.attach_condition(condition)
            self.conditions[name] = condition
            
    def _open_log_files(self):
        """Open log files for writing."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.log_files = {
            "temperature": open(self.output_dir / f"temperature_{timestamp}.jsonl", "w"),
            "pressure": open(self.output_dir / f"pressure_{timestamp}.jsonl", "w"),
            "metrics": open(self.output_dir / f"metrics_{timestamp}.jsonl", "w"),
            "alerts": open(self.output_dir / f"alerts_{timestamp}.jsonl", "w"),
        }
        
    def _log_sample(self, data_type: str, sample):
        """Log a sample to the appropriate file."""
        # Convert DynamicData to dict
        record = {"_logged_at": datetime.now().isoformat()}
        
        if data_type == "temperature":
            record["sensor_id"] = sample["sensor_id"]
            record["value_celsius"] = sample["value_celsius"]
            record["timestamp_ms"] = sample["timestamp_ms"]
        elif data_type == "pressure":
            record["sensor_id"] = sample["sensor_id"]
            record["value_kpa"] = sample["value_kpa"]
            record["timestamp_ms"] = sample["timestamp_ms"]
        elif data_type == "metrics":
            record["sensor_id"] = sample["sensor_id"]
            record["metric_type"] = sample["metric_type"]
            record["avg_value"] = sample["avg_value"]
            record["min_value"] = sample["min_value"]
            record["max_value"] = sample["max_value"]
            record["sample_count"] = sample["sample_count"]
        elif data_type == "alerts":
            record["alert_id"] = sample["alert_id"]
            record["sensor_id"] = sample["sensor_id"]
            record["severity"] = sample["severity"]
            record["message"] = sample["message"]
            record["value"] = sample["value"]
            record["threshold"] = sample["threshold"]
            
        self.log_files[data_type].write(json.dumps(record) + "\n")
        self.log_files[data_type].flush()
        self.sample_counts[data_type] += 1
        
    def _process_all(self):
        """Process data from all readers."""
        for sample in self.temp_reader.take():
            if sample.info.valid:
                self._log_sample("temperature", sample.data)
                
        for sample in self.pressure_reader.take():
            if sample.info.valid:
                self._log_sample("pressure", sample.data)
                
        for sample in self.metrics_reader.take():
            if sample.info.valid:
                self._log_sample("metrics", sample.data)
                
        for sample in self.alert_reader.take():
            if sample.info.valid:
                self._log_sample("alerts", sample.data)
                
    def run(self):
        """Run the data logger."""
        print(f"[DataLogger] Logging to {self.output_dir}", file=sys.stderr)
        
        while self.running:
            self.waitset.wait(dds.Duration.from_seconds(1.0))
            self._process_all()
            
        # Final flush
        self._process_all()
        
        # Close files
        for f in self.log_files.values():
            f.close()
            
        print(f"[DataLogger] Stopped. Logged: temp={self.sample_counts['temperature']}, "
              f"pressure={self.sample_counts['pressure']}, metrics={self.sample_counts['metrics']}, "
              f"alerts={self.sample_counts['alerts']}", file=sys.stderr)
        
    def stop(self):
        """Stop the logger."""
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--output", "-o", type=str, default="./logs",
                        help="Output directory")
    args = parser.parse_args()
    
    logger = DataLogger(args.domain, args.output)
    
    def signal_handler(signum, frame):
        logger.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.run()


if __name__ == "__main__":
    main()


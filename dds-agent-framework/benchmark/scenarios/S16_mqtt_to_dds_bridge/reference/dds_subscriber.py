#!/usr/bin/env python3
"""
DDS Subscriber for bridged MQTT data.

Receives data from all bridged topics and outputs JSONL.
"""

import argparse
import json
import signal
import sys
import time

import rti.connextdds as dds

from dds_types import (
    create_sensor_temperature_type,
    create_sensor_humidity_type,
    create_device_status_type,
)


class DDSSubscriber:
    """Subscribes to all bridged topics and outputs JSONL."""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.running = True
        self.counts = {"temperature": 0, "humidity": 0, "status": 0}
        self._setup_dds()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Create topics
        temp_type = create_sensor_temperature_type()
        humidity_type = create_sensor_humidity_type()
        status_type = create_device_status_type()
        
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "SensorTemperature", temp_type
        )
        self.humidity_topic = dds.DynamicData.Topic(
            self.participant, "SensorHumidity", humidity_type
        )
        self.status_topic = dds.DynamicData.Topic(
            self.participant, "DeviceStatus", status_type
        )
        
        # Subscriber
        subscriber = dds.Subscriber(self.participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        
        self.temp_reader = dds.DynamicData.DataReader(
            subscriber, self.temp_topic, reader_qos
        )
        self.humidity_reader = dds.DynamicData.DataReader(
            subscriber, self.humidity_topic, reader_qos
        )
        self.status_reader = dds.DynamicData.DataReader(
            subscriber, self.status_topic, reader_qos
        )
        
        # WaitSet
        self.waitset = dds.WaitSet()
        self.temp_condition = dds.ReadCondition(
            self.temp_reader, dds.DataState.any_data
        )
        self.humidity_condition = dds.ReadCondition(
            self.humidity_reader, dds.DataState.any_data
        )
        self.status_condition = dds.ReadCondition(
            self.status_reader, dds.DataState.any_data
        )
        self.waitset.attach_condition(self.temp_condition)
        self.waitset.attach_condition(self.humidity_condition)
        self.waitset.attach_condition(self.status_condition)
        
    def _process_temperature(self):
        """Process temperature samples."""
        for sample in self.temp_reader.take():
            if sample.info.valid:
                data = {
                    "topic": "SensorTemperature",
                    "device_id": sample.data["device_id"],
                    "value": sample.data["value"],
                    "unit": sample.data["unit"],
                    "timestamp_ms": sample.data["timestamp_ms"],
                }
                print(json.dumps(data), flush=True)
                self.counts["temperature"] += 1
                
    def _process_humidity(self):
        """Process humidity samples."""
        for sample in self.humidity_reader.take():
            if sample.info.valid:
                data = {
                    "topic": "SensorHumidity",
                    "device_id": sample.data["device_id"],
                    "value": sample.data["value"],
                    "unit": sample.data["unit"],
                    "timestamp_ms": sample.data["timestamp_ms"],
                }
                print(json.dumps(data), flush=True)
                self.counts["humidity"] += 1
                
    def _process_status(self):
        """Process status samples."""
        for sample in self.status_reader.take():
            if sample.info.valid:
                data = {
                    "topic": "DeviceStatus",
                    "device_id": sample.data["device_id"],
                    "online": sample.data["online"],
                    "battery": sample.data["battery"],
                    "timestamp_ms": sample.data["timestamp_ms"],
                }
                print(json.dumps(data), flush=True)
                self.counts["status"] += 1
                
    def run(self, timeout: float = 30.0, expected_count: int = 0):
        """Run the subscriber.
        
        Args:
            timeout: Max wait time in seconds
            expected_count: Stop after this many total samples (0 = use timeout)
        """
        print(f"[DDSSubscriber] Waiting for bridged data...", file=sys.stderr)
        
        start_time = time.time()
        while self.running:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                break
                
            total = sum(self.counts.values())
            if expected_count > 0 and total >= expected_count:
                break
                
            remaining = min(1.0, timeout - elapsed)
            active = self.waitset.wait(dds.Duration.from_seconds(remaining))
            
            if self.temp_condition in active:
                self._process_temperature()
            if self.humidity_condition in active:
                self._process_humidity()
            if self.status_condition in active:
                self._process_status()
                
        total = sum(self.counts.values())
        print(f"\n[DDSSubscriber] Received {total} samples: "
              f"temp={self.counts['temperature']}, "
              f"humidity={self.counts['humidity']}, "
              f"status={self.counts['status']}", file=sys.stderr)
        
    def stop(self):
        """Stop the subscriber."""
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--count", "-c", type=int, default=0,
                        help="Expected sample count")
    args = parser.parse_args()
    
    subscriber = DDSSubscriber(args.domain)
    
    def signal_handler(signum, frame):
        subscriber.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    subscriber.run(timeout=args.timeout, expected_count=args.count)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Sensor Publisher - Publishes temperature and pressure readings.

Phase 1: Basic temperature publisher
Phase 4: Added pressure sensor with keyed instances
Phase 5: Added configurable polling rate via request/reply
Phase 8: Uses V2 extended temperature type
"""

import argparse
import random
import signal
import sys
import time
import threading

import rti.connextdds as dds

# Phase 8: Use V2 types
from types_v2 import create_temperature_reading_v2
from types_v1 import create_pressure_reading, create_config_request, create_config_reply


class SensorPublisher:
    """Multi-sensor publisher with configurable polling rate."""
    
    def __init__(self, domain_id: int = 0):
        self.running = True
        self.polling_rate_ms = 1000  # Default 1 second
        self.domain_id = domain_id
        self._setup_dds()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Temperature topic (V2 extended type)
        temp_type = create_temperature_reading_v2()
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "TemperatureReading", temp_type
        )
        
        # Pressure topic
        pressure_type = create_pressure_reading()
        self.pressure_topic = dds.DynamicData.Topic(
            self.participant, "PressureReading", pressure_type
        )
        
        # Publisher with reliable QoS
        pub_qos = dds.PublisherQos()
        self.publisher = dds.Publisher(self.participant, pub_qos)
        
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 10
        
        self.temp_writer = dds.DynamicData.DataWriter(
            self.publisher, self.temp_topic, writer_qos
        )
        self.pressure_writer = dds.DynamicData.DataWriter(
            self.publisher, self.pressure_topic, writer_qos
        )
        
        # Config service (Phase 5)
        self._setup_config_service()
        
        # Store types for creating samples
        self.temp_type = temp_type
        self.pressure_type = pressure_type
        
        # Keyed instances (Phase 4)
        self.sensor_ids = ["TEMP_001", "TEMP_002", "PRESSURE_001", "PRESSURE_002"]
        
    def _setup_config_service(self):
        """Setup request/reply for configuration changes."""
        request_type = create_config_request()
        reply_type = create_config_reply()
        
        self.config_request_topic = dds.DynamicData.Topic(
            self.participant, "ConfigRequest", request_type
        )
        self.config_reply_topic = dds.DynamicData.Topic(
            self.participant, "ConfigReply", reply_type
        )
        
        subscriber = dds.Subscriber(self.participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        
        self.config_reader = dds.DynamicData.DataReader(
            subscriber, self.config_request_topic, reader_qos
        )
        
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        
        self.config_writer = dds.DynamicData.DataWriter(
            self.publisher, self.config_reply_topic, writer_qos
        )
        
        self.reply_type = reply_type
        
    def _handle_config_requests(self):
        """Process configuration requests (non-blocking)."""
        for sample in self.config_reader.take():
            if sample.info.valid:
                request = sample.data
                request_id = request["request_id"]
                parameter = request["parameter"]
                value = request["value"]
                
                reply = dds.DynamicData(self.reply_type)
                reply["request_id"] = request_id
                
                if parameter == "polling_rate_ms":
                    old_value = self.polling_rate_ms
                    if 100 <= value <= 10000:
                        self.polling_rate_ms = int(value)
                        reply["success"] = True
                        reply["message"] = f"Polling rate changed to {int(value)}ms"
                        reply["previous_value"] = float(old_value)
                        reply["new_value"] = float(value)
                        print(f"[Config] Polling rate: {old_value}ms -> {int(value)}ms", 
                              file=sys.stderr)
                    else:
                        reply["success"] = False
                        reply["message"] = "Value must be between 100 and 10000"
                        reply["previous_value"] = float(old_value)
                        reply["new_value"] = float(old_value)
                else:
                    reply["success"] = False
                    reply["message"] = f"Unknown parameter: {parameter}"
                    reply["previous_value"] = 0.0
                    reply["new_value"] = 0.0
                    
                self.config_writer.write(reply)
                
    def _publish_temperature(self, sensor_id: str, count: int):
        """Publish temperature reading (V2 with extended fields)."""
        sample = dds.DynamicData(self.temp_type)
        sample["sensor_id"] = sensor_id
        sample["value_celsius"] = 20.0 + random.uniform(-5, 15) + (count * 0.1)
        sample["timestamp_ms"] = int(time.time() * 1000)
        
        # V2 extended fields
        sample["location"] = f"Building A, Floor {1 + hash(sensor_id) % 3}"
        sample["sensor_model"] = "TempSensor-3000"
        sample["calibration_date"] = 1704067200000  # 2024-01-01
        
        self.temp_writer.write(sample)
        
    def _publish_pressure(self, sensor_id: str, count: int):
        """Publish pressure reading."""
        sample = dds.DynamicData(self.pressure_type)
        sample["sensor_id"] = sensor_id
        sample["value_kpa"] = 101.3 + random.uniform(-5, 5) + (count * 0.05)
        sample["timestamp_ms"] = int(time.time() * 1000)
        
        self.pressure_writer.write(sample)
        
    def run(self, count: int = 0):
        """Run the publisher.
        
        Args:
            count: Number of samples (0 = infinite)
        """
        print(f"[SensorPublisher] Starting (polling: {self.polling_rate_ms}ms)", 
              file=sys.stderr)
        
        time.sleep(2.0)  # Wait for discovery
        
        iteration = 0
        while self.running:
            if count > 0 and iteration >= count:
                break
                
            # Handle config requests
            self._handle_config_requests()
            
            # Publish all sensors
            for sensor_id in self.sensor_ids:
                if sensor_id.startswith("TEMP"):
                    self._publish_temperature(sensor_id, iteration)
                else:
                    self._publish_pressure(sensor_id, iteration)
                    
            iteration += 1
            time.sleep(self.polling_rate_ms / 1000.0)
            
        print(f"[SensorPublisher] Stopped after {iteration} iterations", file=sys.stderr)
        
    def stop(self):
        """Stop the publisher."""
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=0,
                        help="Number of iterations (0=infinite)")
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--rate", "-r", type=int, default=1000,
                        help="Polling rate in ms")
    args = parser.parse_args()
    
    publisher = SensorPublisher(args.domain)
    publisher.polling_rate_ms = args.rate
    
    def signal_handler(signum, frame):
        publisher.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    publisher.run(args.count)


if __name__ == "__main__":
    main()


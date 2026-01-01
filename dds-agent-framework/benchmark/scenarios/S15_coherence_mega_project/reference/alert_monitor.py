#!/usr/bin/env python3
"""
Alert Monitor - Detects anomalies and publishes alerts.

Phase 3: Temperature alerts when > 50°C
Phase 4: Extended to also monitor pressure
"""

import argparse
import signal
import sys
import time
import uuid

import rti.connextdds as dds

from types_v1 import (
    create_temperature_reading_v1,
    create_pressure_reading,
    create_system_alert,
)


class AlertMonitor:
    """Monitors sensors and generates alerts for anomalies."""
    
    # Thresholds
    TEMP_HIGH_THRESHOLD = 50.0  # Celsius
    TEMP_CRITICAL_THRESHOLD = 70.0
    PRESSURE_HIGH_THRESHOLD = 110.0  # kPa
    PRESSURE_LOW_THRESHOLD = 95.0
    
    def __init__(self, domain_id: int = 0):
        self.running = True
        self.domain_id = domain_id
        self.alert_count = 0
        self._setup_dds()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Subscribe to sensors
        temp_type = create_temperature_reading_v1()
        pressure_type = create_pressure_reading()
        alert_type = create_system_alert()
        
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "TemperatureReading", temp_type
        )
        self.pressure_topic = dds.DynamicData.Topic(
            self.participant, "PressureReading", pressure_type
        )
        self.alert_topic = dds.DynamicData.Topic(
            self.participant, "SystemAlert", alert_type
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
        
        # Alert publisher
        publisher = dds.Publisher(self.participant)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        
        self.alert_writer = dds.DynamicData.DataWriter(
            publisher, self.alert_topic, writer_qos
        )
        
        # WaitSet
        self.waitset = dds.WaitSet()
        self.temp_condition = dds.ReadCondition(
            self.temp_reader, dds.DataState.any_data
        )
        self.pressure_condition = dds.ReadCondition(
            self.pressure_reader, dds.DataState.any_data
        )
        self.waitset.attach_condition(self.temp_condition)
        self.waitset.attach_condition(self.pressure_condition)
        
        self.alert_type = alert_type
        
    def _publish_alert(self, sensor_id: str, severity: int, message: str,
                       value: float, threshold: float):
        """Publish a system alert."""
        self.alert_count += 1
        
        sample = dds.DynamicData(self.alert_type)
        sample["alert_id"] = f"ALERT_{uuid.uuid4().hex[:8]}"
        sample["sensor_id"] = sensor_id
        sample["severity"] = severity
        sample["message"] = message
        sample["value"] = value
        sample["threshold"] = threshold
        sample["timestamp_ms"] = int(time.time() * 1000)
        
        self.alert_writer.write(sample)
        
        severity_str = {1: "INFO", 2: "WARNING", 3: "CRITICAL"}[severity]
        print(f"[ALERT] [{severity_str}] {sensor_id}: {message}", file=sys.stderr)
        
    def _check_temperature(self):
        """Check temperature readings for anomalies."""
        for sample in self.temp_reader.take():
            if sample.info.valid:
                sensor_id = sample.data["sensor_id"]
                value = sample.data["value_celsius"]
                
                if value >= self.TEMP_CRITICAL_THRESHOLD:
                    self._publish_alert(
                        sensor_id, 3,
                        f"CRITICAL: Temperature {value:.1f}°C exceeds critical threshold",
                        value, self.TEMP_CRITICAL_THRESHOLD
                    )
                elif value >= self.TEMP_HIGH_THRESHOLD:
                    self._publish_alert(
                        sensor_id, 2,
                        f"WARNING: Temperature {value:.1f}°C exceeds high threshold",
                        value, self.TEMP_HIGH_THRESHOLD
                    )
                    
    def _check_pressure(self):
        """Check pressure readings for anomalies."""
        for sample in self.pressure_reader.take():
            if sample.info.valid:
                sensor_id = sample.data["sensor_id"]
                value = sample.data["value_kpa"]
                
                if value >= self.PRESSURE_HIGH_THRESHOLD:
                    self._publish_alert(
                        sensor_id, 2,
                        f"WARNING: Pressure {value:.1f} kPa exceeds high threshold",
                        value, self.PRESSURE_HIGH_THRESHOLD
                    )
                elif value <= self.PRESSURE_LOW_THRESHOLD:
                    self._publish_alert(
                        sensor_id, 2,
                        f"WARNING: Pressure {value:.1f} kPa below low threshold",
                        value, self.PRESSURE_LOW_THRESHOLD
                    )
                    
    def run(self):
        """Run the alert monitor."""
        print(f"[AlertMonitor] Starting (temp threshold: {self.TEMP_HIGH_THRESHOLD}°C)", 
              file=sys.stderr)
        
        while self.running:
            active = self.waitset.wait(dds.Duration.from_seconds(1.0))
            
            if self.temp_condition in active:
                self._check_temperature()
            if self.pressure_condition in active:
                self._check_pressure()
                
        print(f"[AlertMonitor] Stopped. Generated {self.alert_count} alerts.", 
              file=sys.stderr)
        
    def stop(self):
        """Stop the monitor."""
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    monitor = AlertMonitor(args.domain)
    
    def signal_handler(signum, frame):
        monitor.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    monitor.run()


if __name__ == "__main__":
    main()


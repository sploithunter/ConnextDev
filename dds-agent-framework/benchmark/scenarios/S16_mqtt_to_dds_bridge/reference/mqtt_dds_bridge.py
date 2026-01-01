#!/usr/bin/env python3
"""
MQTT to DDS Bridge.

Subscribes to MQTT topics and republishes data to DDS.
Handles topic mapping and schema conversion.
"""

import argparse
import json
import signal
import sys
import time
import threading

import rti.connextdds as dds

from dds_types import (
    create_sensor_temperature_type,
    create_sensor_humidity_type,
    create_device_status_type,
)
from mqtt_simulator import MQTTSimulator


class MQTTToDDSBridge:
    """Bridges MQTT messages to DDS topics."""
    
    # Topic mapping: MQTT topic -> DDS topic name
    TOPIC_MAPPING = {
        "sensors/temperature": "SensorTemperature",
        "sensors/humidity": "SensorHumidity",
        "sensors/status": "DeviceStatus",
    }
    
    def __init__(self, domain_id: int = 0, mqtt_broker: str = "localhost"):
        self.domain_id = domain_id
        self.mqtt_broker = mqtt_broker
        self.running = True
        self.message_count = 0
        self.error_count = 0
        
        self._setup_dds()
        self._setup_mqtt()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        # Create types
        temp_type = create_sensor_temperature_type()
        humidity_type = create_sensor_humidity_type()
        status_type = create_device_status_type()
        
        # Create topics
        self.temp_topic = dds.DynamicData.Topic(
            self.participant, "SensorTemperature", temp_type
        )
        self.humidity_topic = dds.DynamicData.Topic(
            self.participant, "SensorHumidity", humidity_type
        )
        self.status_topic = dds.DynamicData.Topic(
            self.participant, "DeviceStatus", status_type
        )
        
        # Publisher with reliable QoS
        publisher = dds.Publisher(self.participant)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 10
        
        self.temp_writer = dds.DynamicData.DataWriter(
            publisher, self.temp_topic, writer_qos
        )
        self.humidity_writer = dds.DynamicData.DataWriter(
            publisher, self.humidity_topic, writer_qos
        )
        self.status_writer = dds.DynamicData.DataWriter(
            publisher, self.status_topic, writer_qos
        )
        
        # Store types for creating samples
        self.temp_type = temp_type
        self.humidity_type = humidity_type
        self.status_type = status_type
        
        print(f"[Bridge] DDS initialized on domain {self.domain_id}", file=sys.stderr)
        
    def _setup_mqtt(self):
        """Initialize MQTT client (using simulator for testing)."""
        self.mqtt = MQTTSimulator()
        self.mqtt.on_message = self._on_mqtt_message
        self.mqtt.subscribe("sensors/#")
        
        print(f"[Bridge] MQTT subscribed to sensors/#", file=sys.stderr)
        
    def _on_mqtt_message(self, topic: str, payload: bytes):
        """Handle incoming MQTT message."""
        try:
            # Parse JSON payload
            data = json.loads(payload.decode('utf-8'))
            timestamp_ms = int(time.time() * 1000)
            
            # Route to appropriate DDS topic
            if topic == "sensors/temperature":
                self._publish_temperature(data, timestamp_ms)
            elif topic == "sensors/humidity":
                self._publish_humidity(data, timestamp_ms)
            elif topic == "sensors/status":
                self._publish_status(data, timestamp_ms)
            else:
                print(f"[Bridge] Unknown topic: {topic}", file=sys.stderr)
                return
                
            self.message_count += 1
            
        except json.JSONDecodeError as e:
            self.error_count += 1
            print(f"[Bridge] JSON parse error: {e}", file=sys.stderr)
        except Exception as e:
            self.error_count += 1
            print(f"[Bridge] Error processing message: {e}", file=sys.stderr)
            
    def _publish_temperature(self, data: dict, timestamp_ms: int):
        """Convert and publish temperature data to DDS."""
        sample = dds.DynamicData(self.temp_type)
        sample["device_id"] = data.get("device_id", "UNKNOWN")
        sample["value"] = float(data.get("value", 0.0))
        sample["unit"] = data.get("unit", "C")
        sample["timestamp_ms"] = timestamp_ms
        
        self.temp_writer.write(sample)
        
    def _publish_humidity(self, data: dict, timestamp_ms: int):
        """Convert and publish humidity data to DDS."""
        sample = dds.DynamicData(self.humidity_type)
        sample["device_id"] = data.get("device_id", "UNKNOWN")
        sample["value"] = float(data.get("value", 0.0))
        sample["unit"] = data.get("unit", "%")
        sample["timestamp_ms"] = timestamp_ms
        
        self.humidity_writer.write(sample)
        
    def _publish_status(self, data: dict, timestamp_ms: int):
        """Convert and publish device status to DDS."""
        sample = dds.DynamicData(self.status_type)
        sample["device_id"] = data.get("device_id", "UNKNOWN")
        sample["online"] = bool(data.get("online", False))
        sample["battery"] = int(data.get("battery", 0))
        sample["timestamp_ms"] = timestamp_ms
        
        self.status_writer.write(sample)
        
    def run(self, mqtt_count: int = 0, mqtt_interval_ms: int = 500):
        """Run the bridge.
        
        Args:
            mqtt_count: Number of MQTT message batches (0 = infinite)
            mqtt_interval_ms: Interval between MQTT batches
        """
        print(f"[Bridge] Starting...", file=sys.stderr)
        
        # Wait for DDS discovery
        time.sleep(2.0)
        
        # Start MQTT message simulation
        self.mqtt.start_publishing(count=mqtt_count, interval_ms=mqtt_interval_ms)
        
        # Wait for completion
        if mqtt_count > 0:
            self.mqtt.wait()
            time.sleep(1.0)  # Allow final DDS writes
        else:
            # Infinite mode - wait until stopped
            while self.running:
                time.sleep(0.5)
                
        print(f"[Bridge] Stopped. Bridged {self.message_count} messages, "
              f"{self.error_count} errors", file=sys.stderr)
        
    def stop(self):
        """Stop the bridge."""
        self.running = False
        self.mqtt.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--count", "-c", type=int, default=0,
                        help="MQTT batch count (0=infinite)")
    parser.add_argument("--interval", "-i", type=int, default=500,
                        help="MQTT interval in ms")
    args = parser.parse_args()
    
    bridge = MQTTToDDSBridge(args.domain)
    
    def signal_handler(signum, frame):
        bridge.stop()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    bridge.run(mqtt_count=args.count, mqtt_interval_ms=args.interval)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
MQTT Message Simulator.

Since we may not have an MQTT broker available, this simulates
MQTT messages for testing the bridge without network dependencies.

For real testing, this can be replaced with paho-mqtt publishing
to a real broker (mosquitto, etc.)
"""

import json
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional
import threading


@dataclass
class MQTTMessage:
    """Simulated MQTT message."""
    topic: str
    payload: bytes
    qos: int = 0
    retain: bool = False
    
    @property
    def payload_str(self) -> str:
        return self.payload.decode('utf-8')
    
    @property
    def payload_json(self) -> dict:
        return json.loads(self.payload)


class MQTTSimulator:
    """Simulates MQTT messages without a broker.
    
    Usage:
        sim = MQTTSimulator()
        sim.on_message = lambda topic, payload: print(f"{topic}: {payload}")
        sim.subscribe("sensors/#")
        sim.start_publishing()
    """
    
    def __init__(self):
        self.running = False
        self.on_message: Optional[Callable[[str, bytes], None]] = None
        self.subscriptions: list[str] = []
        self._thread: Optional[threading.Thread] = None
        
        # Simulated devices
        self.devices = ["DEVICE_001", "DEVICE_002", "DEVICE_003"]
        
    def subscribe(self, topic_pattern: str):
        """Subscribe to a topic pattern (supports # wildcard)."""
        self.subscriptions.append(topic_pattern)
        
    def _matches_subscription(self, topic: str) -> bool:
        """Check if topic matches any subscription."""
        for pattern in self.subscriptions:
            if pattern.endswith("#"):
                prefix = pattern[:-1]
                if topic.startswith(prefix):
                    return True
            elif pattern == topic:
                return True
        return False
        
    def _generate_temperature_message(self, device_id: str) -> MQTTMessage:
        """Generate a temperature sensor message."""
        payload = {
            "device_id": device_id,
            "value": round(20.0 + random.uniform(-5, 15), 2),
            "unit": "C",
        }
        return MQTTMessage(
            topic="sensors/temperature",
            payload=json.dumps(payload).encode('utf-8'),
            qos=1,
        )
        
    def _generate_humidity_message(self, device_id: str) -> MQTTMessage:
        """Generate a humidity sensor message."""
        payload = {
            "device_id": device_id,
            "value": round(40.0 + random.uniform(0, 40), 2),
            "unit": "%",
        }
        return MQTTMessage(
            topic="sensors/humidity",
            payload=json.dumps(payload).encode('utf-8'),
            qos=1,
        )
        
    def _generate_status_message(self, device_id: str) -> MQTTMessage:
        """Generate a device status message."""
        payload = {
            "device_id": device_id,
            "online": random.random() > 0.1,  # 90% online
            "battery": random.randint(20, 100),
        }
        return MQTTMessage(
            topic="sensors/status",
            payload=json.dumps(payload).encode('utf-8'),
            qos=0,
        )
        
    def _publish_loop(self, count: int, interval_ms: int):
        """Internal publishing loop."""
        iteration = 0
        while self.running and (count == 0 or iteration < count):
            for device_id in self.devices:
                # Generate different message types
                messages = [
                    self._generate_temperature_message(device_id),
                    self._generate_humidity_message(device_id),
                ]
                
                # Status less frequently
                if iteration % 5 == 0:
                    messages.append(self._generate_status_message(device_id))
                    
                for msg in messages:
                    if self._matches_subscription(msg.topic) and self.on_message:
                        self.on_message(msg.topic, msg.payload)
                        
            iteration += 1
            time.sleep(interval_ms / 1000.0)
            
    def start_publishing(self, count: int = 0, interval_ms: int = 500):
        """Start publishing simulated messages.
        
        Args:
            count: Number of iterations (0 = infinite)
            interval_ms: Interval between batches
        """
        self.running = True
        self._thread = threading.Thread(
            target=self._publish_loop, 
            args=(count, interval_ms),
            daemon=True,
        )
        self._thread.start()
        
    def stop(self):
        """Stop publishing."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            
    def wait(self):
        """Wait for publishing to complete."""
        if self._thread:
            self._thread.join()


# Example usage
if __name__ == "__main__":
    def on_message(topic: str, payload: bytes):
        data = json.loads(payload)
        print(f"[{topic}] {data}")
        
    sim = MQTTSimulator()
    sim.on_message = on_message
    sim.subscribe("sensors/#")
    
    print("Starting MQTT simulation (10 iterations)...")
    sim.start_publishing(count=10, interval_ms=200)
    sim.wait()
    print("Done!")


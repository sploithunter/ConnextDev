#!/usr/bin/env python3
"""
Configuration Client - Sends configuration requests to sensors.

Phase 5: Request/Reply for changing sensor polling rate.
"""

import argparse
import signal
import sys
import time
import uuid

import rti.connextdds as dds

from types_v1 import create_config_request, create_config_reply


class ConfigClient:
    """Client for sending configuration requests."""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self._setup_dds()
        
    def _setup_dds(self):
        """Initialize DDS entities."""
        self.participant = dds.DomainParticipant(self.domain_id)
        
        request_type = create_config_request()
        reply_type = create_config_reply()
        
        self.request_topic = dds.DynamicData.Topic(
            self.participant, "ConfigRequest", request_type
        )
        self.reply_topic = dds.DynamicData.Topic(
            self.participant, "ConfigReply", reply_type
        )
        
        # Publisher for requests
        publisher = dds.Publisher(self.participant)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        
        self.request_writer = dds.DynamicData.DataWriter(
            publisher, self.request_topic, writer_qos
        )
        
        # Subscriber for replies
        subscriber = dds.Subscriber(self.participant)
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        
        self.reply_reader = dds.DynamicData.DataReader(
            subscriber, self.reply_topic, reader_qos
        )
        
        self.request_type = request_type
        
    def set_polling_rate(self, sensor_id: str, rate_ms: int, 
                         timeout: float = 5.0) -> tuple[bool, str]:
        """Set the polling rate for a sensor.
        
        Returns:
            (success, message)
        """
        request_id = uuid.uuid4().hex[:8]
        
        request = dds.DynamicData(self.request_type)
        request["request_id"] = request_id
        request["sensor_id"] = sensor_id
        request["parameter"] = "polling_rate_ms"
        request["value"] = float(rate_ms)
        
        self.request_writer.write(request)
        print(f"[ConfigClient] Sent request {request_id}: set polling to {rate_ms}ms", 
              file=sys.stderr)
        
        # Wait for reply
        start = time.time()
        while time.time() - start < timeout:
            for sample in self.reply_reader.take():
                if sample.info.valid:
                    if sample.data["request_id"] == request_id:
                        success = sample.data["success"]
                        message = sample.data["message"]
                        return success, message
                        
            time.sleep(0.1)
            
        return False, "Timeout waiting for reply"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--sensor", "-s", type=str, default="*",
                        help="Sensor ID (default: all)")
    parser.add_argument("--rate", "-r", type=int, required=True,
                        help="Polling rate in ms")
    args = parser.parse_args()
    
    time.sleep(2.0)  # Discovery time
    
    client = ConfigClient(args.domain)
    success, message = client.set_polling_rate(args.sensor, args.rate)
    
    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()


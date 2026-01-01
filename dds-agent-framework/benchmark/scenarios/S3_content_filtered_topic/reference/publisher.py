#!/usr/bin/env python3
"""Content Filtered Topic - Publisher.

Sends sensor alerts with varying severity levels.
Subscriber will filter to only HIGH severity alerts.
"""

import argparse
import random
import time
import sys

import rti.connextdds as dds


def create_alert_type():
    t = dds.StructType("SensorAlert")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_type", dds.StringType(32)))  # TEMPERATURE, PRESSURE, HUMIDITY
    t.add_member(dds.Member("severity", dds.Int32Type()))  # 1=LOW, 2=MEDIUM, 3=HIGH, 4=CRITICAL
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("message", dds.StringType(256)))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=30)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    
    alert_type = create_alert_type()
    topic = dds.DynamicData.Topic(participant, "SensorAlerts", alert_type)
    
    publisher = dds.Publisher(participant)
    
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)  # Discovery
    
    sensor_types = ["TEMPERATURE", "PRESSURE", "HUMIDITY"]
    severities = [1, 1, 1, 2, 2, 3, 4]  # Weighted towards low severity
    
    high_critical_count = 0
    
    for i in range(args.count):
        sensor_type = random.choice(sensor_types)
        severity = random.choice(severities)
        
        if severity >= 3:
            high_critical_count += 1
        
        sample = dds.DynamicData(alert_type)
        sample["sensor_id"] = f"SENSOR_{i % 10:03d}"
        sample["sensor_type"] = sensor_type
        sample["severity"] = severity
        sample["value"] = random.uniform(0, 100)
        
        severity_names = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
        sample["message"] = f"{sensor_type} {severity_names[severity]} alert"
        sample["timestamp"] = time.time()
        
        writer.write(sample)
        
        print(f"[{i+1}] {sensor_type} severity={severity} ({severity_names[severity]})", 
              file=sys.stderr)
        
        time.sleep(0.1)
    
    time.sleep(2.0)
    print(f"\nPublished {args.count} alerts ({high_critical_count} HIGH/CRITICAL)", 
          file=sys.stderr)


if __name__ == "__main__":
    main()


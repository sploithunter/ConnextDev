#!/usr/bin/env python3
"""Multi-Topic Vehicle Telemetry Publisher.

Publishes to 3 related topics:
- VehiclePosition: x, y, z coordinates + heading
- VehicleVelocity: speed, acceleration
- VehicleStatus: fuel, battery, operational mode

All topics share a vehicle_id for correlation.
"""

import argparse
import math
import time
import sys

import rti.connextdds as dds


def create_position_type():
    t = dds.StructType("VehiclePosition")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("x", dds.Float64Type()))
    t.add_member(dds.Member("y", dds.Float64Type()))
    t.add_member(dds.Member("z", dds.Float64Type()))
    t.add_member(dds.Member("heading", dds.Float64Type()))  # degrees
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_velocity_type():
    t = dds.StructType("VehicleVelocity")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("speed", dds.Float64Type()))  # m/s
    t.add_member(dds.Member("acceleration", dds.Float64Type()))  # m/s^2
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_status_type():
    t = dds.StructType("VehicleStatus")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("fuel_percent", dds.Float64Type()))
    t.add_member(dds.Member("battery_percent", dds.Float64Type()))
    t.add_member(dds.Member("mode", dds.StringType(32)))  # "IDLE", "MOVING", "CHARGING"
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicle-id", "-v", default="VEHICLE_001")
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    
    # Create types
    pos_type = create_position_type()
    vel_type = create_velocity_type()
    status_type = create_status_type()
    
    # Create topics
    pos_topic = dds.DynamicData.Topic(participant, "VehiclePosition", pos_type)
    vel_topic = dds.DynamicData.Topic(participant, "VehicleVelocity", vel_type)
    status_topic = dds.DynamicData.Topic(participant, "VehicleStatus", status_type)
    
    # Create publisher with RELIABLE + TRANSIENT_LOCAL
    publisher = dds.Publisher(participant)
    
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    pos_writer = dds.DynamicData.DataWriter(publisher, pos_topic, writer_qos)
    vel_writer = dds.DynamicData.DataWriter(publisher, vel_topic, writer_qos)
    status_writer = dds.DynamicData.DataWriter(publisher, status_topic, writer_qos)
    
    # Wait for discovery
    time.sleep(2.0)
    
    # Simulate vehicle movement
    x, y, z = 0.0, 0.0, 0.0
    speed = 10.0  # m/s
    heading = 45.0  # degrees
    fuel = 100.0
    battery = 100.0
    
    for i in range(args.count):
        ts = time.time()
        
        # Update position based on heading and speed
        heading_rad = math.radians(heading)
        x += speed * 0.1 * math.cos(heading_rad)
        y += speed * 0.1 * math.sin(heading_rad)
        z = 100.0 + 5.0 * math.sin(i * 0.5)  # Slight altitude variation
        
        # Publish position
        pos_sample = dds.DynamicData(pos_type)
        pos_sample["vehicle_id"] = args.vehicle_id
        pos_sample["x"] = x
        pos_sample["y"] = y
        pos_sample["z"] = z
        pos_sample["heading"] = heading
        pos_sample["timestamp"] = ts
        pos_writer.write(pos_sample)
        
        # Publish velocity
        vel_sample = dds.DynamicData(vel_type)
        vel_sample["vehicle_id"] = args.vehicle_id
        vel_sample["speed"] = speed + (i % 3) * 0.5  # Slight variation
        vel_sample["acceleration"] = 0.1 * (i % 5 - 2)
        vel_sample["timestamp"] = ts
        vel_writer.write(vel_sample)
        
        # Publish status every 3rd sample
        if i % 3 == 0:
            fuel -= 1.0
            battery -= 0.5
            status_sample = dds.DynamicData(status_type)
            status_sample["vehicle_id"] = args.vehicle_id
            status_sample["fuel_percent"] = max(0, fuel)
            status_sample["battery_percent"] = max(0, battery)
            status_sample["mode"] = "MOVING" if speed > 0 else "IDLE"
            status_sample["timestamp"] = ts
            status_writer.write(status_sample)
        
        print(f"[{i+1}] Published position, velocity" + 
              (", status" if i % 3 == 0 else ""), file=sys.stderr)
        
        time.sleep(0.2)
    
    time.sleep(2.0)  # Allow delivery
    print(f"Published {args.count} position/velocity updates", file=sys.stderr)


if __name__ == "__main__":
    main()


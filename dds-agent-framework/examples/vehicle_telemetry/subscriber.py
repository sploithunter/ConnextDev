#!/usr/bin/env python3
"""Vehicle Telemetry Subscriber - Multi-topic async subscriber.

Subscribes to three vehicle telemetry topics using async WaitSet pattern:
- Vehicle_Position
- Vehicle_Velocity  
- Vehicle_Status

Outputs received samples in JSONL format for verification.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import TextIO


def create_position_type():
    """Create Vehicle_Position type with nested Point3D."""
    import rti.connextdds as dds
    
    point3d = dds.StructType("Point3D")
    point3d.add_member(dds.Member("x", dds.Float64Type()))
    point3d.add_member(dds.Member("y", dds.Float64Type()))
    point3d.add_member(dds.Member("z", dds.Float64Type()))
    
    position_type = dds.StructType("Vehicle_Position")
    position_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    position_type.add_member(dds.Member("position", point3d))
    position_type.add_member(dds.Member("heading", dds.Float64Type()))
    position_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return position_type


def create_velocity_type():
    """Create Vehicle_Velocity type."""
    import rti.connextdds as dds
    
    vector3d = dds.StructType("Vector3D")
    vector3d.add_member(dds.Member("vx", dds.Float64Type()))
    vector3d.add_member(dds.Member("vy", dds.Float64Type()))
    vector3d.add_member(dds.Member("vz", dds.Float64Type()))
    
    velocity_type = dds.StructType("Vehicle_Velocity")
    velocity_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    velocity_type.add_member(dds.Member("velocity", vector3d))
    velocity_type.add_member(dds.Member("speed", dds.Float64Type()))
    velocity_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return velocity_type


def create_status_type():
    """Create Vehicle_Status type."""
    import rti.connextdds as dds
    
    sensor_health = dds.StructType("SensorHealth")
    sensor_health.add_member(dds.Member("gps_ok", dds.BoolType()))
    sensor_health.add_member(dds.Member("imu_ok", dds.BoolType()))
    sensor_health.add_member(dds.Member("battery_percent", dds.Int32Type()))
    
    status_type = dds.StructType("Vehicle_Status")
    status_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    status_type.add_member(dds.Member("operational", dds.BoolType()))
    status_type.add_member(dds.Member("mode", dds.StringType(32)))
    status_type.add_member(dds.Member("sensors", sensor_health))
    status_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return status_type


def sample_to_dict(topic_name: str, sample) -> dict:
    """Convert a DynamicData sample to a dictionary."""
    data = sample.data
    
    if topic_name == "Vehicle_Position":
        return {
            "topic": topic_name,
            "data": {
                "vehicle_id": data["vehicle_id"],
                "position": {
                    "x": data["position.x"],
                    "y": data["position.y"],
                    "z": data["position.z"],
                },
                "heading": data["heading"],
                "timestamp": data["timestamp"],
            }
        }
    elif topic_name == "Vehicle_Velocity":
        return {
            "topic": topic_name,
            "data": {
                "vehicle_id": data["vehicle_id"],
                "velocity": {
                    "vx": data["velocity.vx"],
                    "vy": data["velocity.vy"],
                    "vz": data["velocity.vz"],
                },
                "speed": data["speed"],
                "timestamp": data["timestamp"],
            }
        }
    elif topic_name == "Vehicle_Status":
        return {
            "topic": topic_name,
            "data": {
                "vehicle_id": data["vehicle_id"],
                "operational": data["operational"],
                "mode": data["mode"],
                "sensors": {
                    "gps_ok": data["sensors.gps_ok"],
                    "imu_ok": data["sensors.imu_ok"],
                    "battery_percent": data["sensors.battery_percent"],
                },
                "timestamp": data["timestamp"],
            }
        }
    else:
        return {"topic": topic_name, "data": {}}


def run_subscriber(
    domain_id: int,
    timeout: float,
    output_file: TextIO,
    verbose: bool = False,
) -> dict:
    """Run the multi-topic subscriber with async WaitSet.
    
    Returns dict with counts per topic.
    """
    import rti.connextdds as dds
    
    # Create participant
    participant = dds.DomainParticipant(domain_id)
    
    # Create types
    position_type = create_position_type()
    velocity_type = create_velocity_type()
    status_type = create_status_type()
    
    # Create topics
    position_topic = dds.DynamicData.Topic(participant, "Vehicle_Position", position_type)
    velocity_topic = dds.DynamicData.Topic(participant, "Vehicle_Velocity", velocity_type)
    status_topic = dds.DynamicData.Topic(participant, "Vehicle_Status", status_type)
    
    # Create subscriber
    subscriber = dds.Subscriber(participant)
    
    # Create readers
    position_reader = dds.DynamicData.DataReader(subscriber, position_topic)
    velocity_reader = dds.DynamicData.DataReader(subscriber, velocity_topic)
    status_reader = dds.DynamicData.DataReader(subscriber, status_topic)
    
    # Set up async WaitSet with conditions for all readers
    waitset = dds.WaitSet()
    
    position_condition = dds.StatusCondition(position_reader)
    position_condition.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
    waitset.attach_condition(position_condition)
    
    velocity_condition = dds.StatusCondition(velocity_reader)
    velocity_condition.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
    waitset.attach_condition(velocity_condition)
    
    status_condition = dds.StatusCondition(status_reader)
    status_condition.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
    waitset.attach_condition(status_condition)
    
    if verbose:
        print(f"Subscriber started on domain {domain_id}", file=sys.stderr)
        print("Waiting for samples (async WaitSet pattern)...", file=sys.stderr)
    
    counts = {"Vehicle_Position": 0, "Vehicle_Velocity": 0, "Vehicle_Status": 0}
    start_time = time.time()
    
    try:
        while time.time() - start_time < timeout:
            # Async wait - NOT polling
            remaining = timeout - (time.time() - start_time)
            wait_time = min(remaining, 1.0)
            
            if wait_time <= 0:
                break
                
            conditions = waitset.wait(dds.Duration.from_seconds(wait_time))
            
            # Process position data
            if position_condition in conditions:
                for sample in position_reader.take():
                    if sample.info.valid:
                        counts["Vehicle_Position"] += 1
                        sample_dict = sample_to_dict("Vehicle_Position", sample)
                        sample_dict["sample_count"] = counts["Vehicle_Position"]
                        output_file.write(json.dumps(sample_dict) + "\n")
                        output_file.flush()
                        if verbose:
                            print(f"  Position: x={sample.data['position.x']:.1f}", file=sys.stderr)
            
            # Process velocity data
            if velocity_condition in conditions:
                for sample in velocity_reader.take():
                    if sample.info.valid:
                        counts["Vehicle_Velocity"] += 1
                        sample_dict = sample_to_dict("Vehicle_Velocity", sample)
                        sample_dict["sample_count"] = counts["Vehicle_Velocity"]
                        output_file.write(json.dumps(sample_dict) + "\n")
                        output_file.flush()
                        if verbose:
                            print(f"  Velocity: speed={sample.data['speed']:.1f}", file=sys.stderr)
            
            # Process status data
            if status_condition in conditions:
                for sample in status_reader.take():
                    if sample.info.valid:
                        counts["Vehicle_Status"] += 1
                        sample_dict = sample_to_dict("Vehicle_Status", sample)
                        sample_dict["sample_count"] = counts["Vehicle_Status"]
                        output_file.write(json.dumps(sample_dict) + "\n")
                        output_file.flush()
                        if verbose:
                            print(f"  Status: battery={sample.data['sensors.battery_percent']}%", file=sys.stderr)
                            
    except KeyboardInterrupt:
        if verbose:
            print("\nInterrupted", file=sys.stderr)
    
    total = sum(counts.values())
    if verbose:
        print(f"Received {total} total samples: {counts}", file=sys.stderr)
    
    return counts


def main():
    parser = argparse.ArgumentParser(description="Vehicle Telemetry Subscriber")
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    
    try:
        import rti.connextdds as dds
    except ImportError:
        print("ERROR: RTI Connext DDS Python API not available", file=sys.stderr)
        sys.exit(1)
    
    output_file = open(args.output, "w") if args.output else sys.stdout
    
    try:
        counts = run_subscriber(args.domain, args.timeout, output_file, args.verbose)
        total = sum(counts.values())
        sys.exit(0 if total > 0 else 1)
    finally:
        if args.output:
            output_file.close()


if __name__ == "__main__":
    main()


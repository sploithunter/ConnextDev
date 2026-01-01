#!/usr/bin/env python3
"""Vehicle Telemetry Publisher - Multi-topic DDS example.

Publishes to three topics with nested data structures:
- Vehicle_Position: 3D position with timestamp
- Vehicle_Velocity: 3D velocity vector
- Vehicle_Status: Operational status with nested sensor health

Demonstrates:
- Multiple topics from single publisher
- Nested data structures
- External QoS configuration
- Realistic telemetry simulation
"""

import argparse
import math
import random
import sys
import time
from pathlib import Path


def create_position_type():
    """Create Vehicle_Position type with nested Point3D."""
    import rti.connextdds as dds
    
    # Nested Point3D structure
    point3d = dds.StructType("Point3D")
    point3d.add_member(dds.Member("x", dds.Float64Type()))
    point3d.add_member(dds.Member("y", dds.Float64Type()))
    point3d.add_member(dds.Member("z", dds.Float64Type()))
    
    # Position type with nested Point3D
    position_type = dds.StructType("Vehicle_Position")
    position_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    position_type.add_member(dds.Member("position", point3d))
    position_type.add_member(dds.Member("heading", dds.Float64Type()))
    position_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return position_type


def create_velocity_type():
    """Create Vehicle_Velocity type with nested Vector3D."""
    import rti.connextdds as dds
    
    # Nested Vector3D structure
    vector3d = dds.StructType("Vector3D")
    vector3d.add_member(dds.Member("vx", dds.Float64Type()))
    vector3d.add_member(dds.Member("vy", dds.Float64Type()))
    vector3d.add_member(dds.Member("vz", dds.Float64Type()))
    
    # Velocity type
    velocity_type = dds.StructType("Vehicle_Velocity")
    velocity_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    velocity_type.add_member(dds.Member("velocity", vector3d))
    velocity_type.add_member(dds.Member("speed", dds.Float64Type()))
    velocity_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return velocity_type


def create_status_type():
    """Create Vehicle_Status type with nested SensorHealth."""
    import rti.connextdds as dds
    
    # Nested SensorHealth structure
    sensor_health = dds.StructType("SensorHealth")
    sensor_health.add_member(dds.Member("gps_ok", dds.BoolType()))
    sensor_health.add_member(dds.Member("imu_ok", dds.BoolType()))
    sensor_health.add_member(dds.Member("battery_percent", dds.Int32Type()))
    
    # Status type
    status_type = dds.StructType("Vehicle_Status")
    status_type.add_member(dds.Member("vehicle_id", dds.Int32Type()))
    status_type.add_member(dds.Member("operational", dds.BoolType()))
    status_type.add_member(dds.Member("mode", dds.StringType(32)))
    status_type.add_member(dds.Member("sensors", sensor_health))
    status_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    return status_type


def get_qos_provider(qos_file: str | None = None):
    """Load QoS from external XML file."""
    import rti.connextdds as dds
    
    if qos_file and Path(qos_file).exists():
        return dds.QosProvider(qos_file)
    
    default_qos = Path(__file__).parent / "qos_profiles.xml"
    if default_qos.exists():
        return dds.QosProvider(str(default_qos))
    
    return None


def run_publisher(
    domain_id: int,
    vehicle_id: int,
    count: int,
    rate_hz: float,
    qos_file: str | None = None,
) -> dict:
    """Run the vehicle telemetry publisher.
    
    Returns dict with counts per topic.
    """
    import rti.connextdds as dds
    
    qos_provider = get_qos_provider(qos_file)
    
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
    
    # Create publisher
    publisher = dds.Publisher(participant)
    
    # Create writers (could use different QoS per topic)
    position_writer = dds.DynamicData.DataWriter(publisher, position_topic)
    velocity_writer = dds.DynamicData.DataWriter(publisher, velocity_topic)
    status_writer = dds.DynamicData.DataWriter(publisher, status_topic)
    
    print(f"Publisher started on domain {domain_id}, vehicle_id={vehicle_id}", file=sys.stderr)
    time.sleep(1.0)  # Wait for discovery
    
    # Initialize samples
    position_sample = dds.DynamicData(position_type)
    velocity_sample = dds.DynamicData(velocity_type)
    status_sample = dds.DynamicData(status_type)
    
    # Simulation state
    x, y, z = 0.0, 0.0, 0.0
    heading = 0.0
    speed = 10.0  # m/s
    
    period = 1.0 / rate_hz if rate_hz > 0 else 0.1
    counts = {"position": 0, "velocity": 0, "status": 0}
    
    try:
        for i in range(count):
            now = time.time()
            
            # Simulate movement
            heading += random.uniform(-0.1, 0.1)
            speed = max(5.0, min(20.0, speed + random.uniform(-0.5, 0.5)))
            x += speed * math.cos(heading) * period
            y += speed * math.sin(heading) * period
            z = 100.0 + random.uniform(-1.0, 1.0)  # Altitude with noise
            
            # Publish position
            position_sample["vehicle_id"] = vehicle_id
            position_sample["position.x"] = x
            position_sample["position.y"] = y
            position_sample["position.z"] = z
            position_sample["heading"] = heading
            position_sample["timestamp"] = now
            position_writer.write(position_sample)
            counts["position"] += 1
            
            # Publish velocity
            velocity_sample["vehicle_id"] = vehicle_id
            velocity_sample["velocity.vx"] = speed * math.cos(heading)
            velocity_sample["velocity.vy"] = speed * math.sin(heading)
            velocity_sample["velocity.vz"] = 0.0
            velocity_sample["speed"] = speed
            velocity_sample["timestamp"] = now
            velocity_writer.write(velocity_sample)
            counts["velocity"] += 1
            
            # Publish status (every 5th sample)
            if i % 5 == 0:
                status_sample["vehicle_id"] = vehicle_id
                status_sample["operational"] = True
                status_sample["mode"] = "AUTONOMOUS"
                status_sample["sensors.gps_ok"] = True
                status_sample["sensors.imu_ok"] = True
                status_sample["sensors.battery_percent"] = max(0, 100 - i // 10)
                status_sample["timestamp"] = now
                status_writer.write(status_sample)
                counts["status"] += 1
            
            print(f"Published: pos={counts['position']}, vel={counts['velocity']}, status={counts['status']}", file=sys.stderr)
            
            if i < count - 1:
                time.sleep(period)
                
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
    
    total = sum(counts.values())
    print(f"Published {total} total samples: {counts}", file=sys.stderr)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Vehicle Telemetry Publisher")
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--vehicle-id", "-v", type=int, default=1)
    parser.add_argument("--count", "-n", type=int, default=20)
    parser.add_argument("--rate", "-r", type=float, default=10.0)
    parser.add_argument("--qos-file", "-q", type=str, default=None)
    
    args = parser.parse_args()
    
    try:
        import rti.connextdds as dds
    except ImportError:
        print("ERROR: RTI Connext DDS Python API not available", file=sys.stderr)
        sys.exit(1)
    
    run_publisher(args.domain, args.vehicle_id, args.count, args.rate, args.qos_file)


if __name__ == "__main__":
    main()


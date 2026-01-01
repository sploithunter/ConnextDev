#!/usr/bin/env python3
"""Multi-Topic Vehicle Telemetry Subscriber.

Subscribes to 3 topics and correlates by vehicle_id and timestamp.
Outputs combined JSONL with all vehicle data.
"""

import argparse
import json
import signal
import sys
import time

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_position_type():
    t = dds.StructType("VehiclePosition")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("x", dds.Float64Type()))
    t.add_member(dds.Member("y", dds.Float64Type()))
    t.add_member(dds.Member("z", dds.Float64Type()))
    t.add_member(dds.Member("heading", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_velocity_type():
    t = dds.StructType("VehicleVelocity")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("speed", dds.Float64Type()))
    t.add_member(dds.Member("acceleration", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_status_type():
    t = dds.StructType("VehicleStatus")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("fuel_percent", dds.Float64Type()))
    t.add_member(dds.Member("battery_percent", dds.Float64Type()))
    t.add_member(dds.Member("mode", dds.StringType(32)))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10,
                        help="Number of position updates to receive")
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    # Create types
    pos_type = create_position_type()
    vel_type = create_velocity_type()
    status_type = create_status_type()
    
    # Create topics
    pos_topic = dds.DynamicData.Topic(participant, "VehiclePosition", pos_type)
    vel_topic = dds.DynamicData.Topic(participant, "VehicleVelocity", vel_type)
    status_topic = dds.DynamicData.Topic(participant, "VehicleStatus", status_type)
    
    # Create subscriber with matching QoS
    subscriber = dds.Subscriber(participant)
    
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    pos_reader = dds.DynamicData.DataReader(subscriber, pos_topic, reader_qos)
    vel_reader = dds.DynamicData.DataReader(subscriber, vel_topic, reader_qos)
    status_reader = dds.DynamicData.DataReader(subscriber, status_topic, reader_qos)
    
    # WaitSet with conditions for all readers
    waitset = dds.WaitSet()
    
    pos_condition = dds.ReadCondition(pos_reader, dds.DataState.any_data)
    vel_condition = dds.ReadCondition(vel_reader, dds.DataState.any_data)
    status_condition = dds.ReadCondition(status_reader, dds.DataState.any_data)
    
    waitset.attach_condition(pos_condition)
    waitset.attach_condition(vel_condition)
    waitset.attach_condition(status_condition)
    
    # Track latest state per vehicle
    vehicle_state = {}  # vehicle_id -> {position, velocity, status}
    position_count = 0
    start_time = time.time()
    
    while running and position_count < args.count:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        # Process position updates
        if pos_condition in active:
            for sample in pos_reader.take():
                if sample.info.valid:
                    vid = sample.data["vehicle_id"]
                    if vid not in vehicle_state:
                        vehicle_state[vid] = {}
                    
                    vehicle_state[vid]["position"] = {
                        "x": sample.data["x"],
                        "y": sample.data["y"],
                        "z": sample.data["z"],
                        "heading": sample.data["heading"],
                    }
                    vehicle_state[vid]["timestamp"] = sample.data["timestamp"]
                    position_count += 1
                    
                    # Output combined state
                    output = {
                        "vehicle_id": vid,
                        "timestamp": sample.data["timestamp"],
                        "position": vehicle_state[vid].get("position"),
                        "velocity": vehicle_state[vid].get("velocity"),
                        "status": vehicle_state[vid].get("status"),
                    }
                    print(json.dumps(output), flush=True)
        
        # Process velocity updates
        if vel_condition in active:
            for sample in vel_reader.take():
                if sample.info.valid:
                    vid = sample.data["vehicle_id"]
                    if vid not in vehicle_state:
                        vehicle_state[vid] = {}
                    
                    vehicle_state[vid]["velocity"] = {
                        "speed": sample.data["speed"],
                        "acceleration": sample.data["acceleration"],
                    }
        
        # Process status updates
        if status_condition in active:
            for sample in status_reader.take():
                if sample.info.valid:
                    vid = sample.data["vehicle_id"]
                    if vid not in vehicle_state:
                        vehicle_state[vid] = {}
                    
                    vehicle_state[vid]["status"] = {
                        "fuel_percent": sample.data["fuel_percent"],
                        "battery_percent": sample.data["battery_percent"],
                        "mode": sample.data["mode"],
                    }
    
    print(f"Received {position_count} position updates", file=sys.stderr)


if __name__ == "__main__":
    main()


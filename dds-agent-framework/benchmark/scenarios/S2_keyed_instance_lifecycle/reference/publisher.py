#!/usr/bin/env python3
"""Keyed Instance Lifecycle Publisher.

Demonstrates DDS instance management:
- register_instance: Explicitly register before writing
- write: Update instance data
- dispose: Mark instance as no longer active
- unregister_instance: Remove instance from system

Simulates a fleet of vehicles that come online, send data, and go offline.
"""

import argparse
import time
import sys

import rti.connextdds as dds


def create_vehicle_type():
    """Create keyed type - vehicle_id is the key field."""
    t = dds.StructType("Vehicle")
    # Key field - identifies the instance
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("x", dds.Float64Type()))
    t.add_member(dds.Member("y", dds.Float64Type()))
    t.add_member(dds.Member("status", dds.StringType(32)))
    t.add_member(dds.Member("sequence", dds.Int32Type()))
    return t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    participant = dds.DomainParticipant(args.domain)
    
    vehicle_type = create_vehicle_type()
    topic = dds.DynamicData.Topic(participant, "VehicleTracker", vehicle_type)
    
    publisher = dds.Publisher(participant)
    
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    # Writer data lifecycle - auto dispose on unregister
    writer_qos.writer_data_lifecycle.autodispose_unregistered_instances = True
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)  # Discovery
    
    vehicles = ["VEH_001", "VEH_002", "VEH_003"]
    instance_handles = {}
    
    # Phase 1: Register all vehicles
    print("Phase 1: Registering vehicles...", file=sys.stderr)
    for vid in vehicles:
        sample = dds.DynamicData(vehicle_type)
        sample["vehicle_id"] = vid
        handle = writer.register_instance(sample)
        instance_handles[vid] = handle
        print(f"  Registered: {vid}", file=sys.stderr)
    
    time.sleep(0.5)
    
    # Phase 2: Send updates for all vehicles
    print("\nPhase 2: Sending updates...", file=sys.stderr)
    for seq in range(1, 6):
        for i, vid in enumerate(vehicles):
            sample = dds.DynamicData(vehicle_type)
            sample["vehicle_id"] = vid
            sample["x"] = float(seq * 10 + i)
            sample["y"] = float(seq * 5 + i)
            sample["status"] = "ACTIVE"
            sample["sequence"] = seq
            
            writer.write(sample, instance_handles[vid])
            print(f"  [{seq}] Updated: {vid}", file=sys.stderr)
        
        time.sleep(0.2)
    
    # Phase 3: Dispose VEH_002 (temporarily inactive)
    print("\nPhase 3: Disposing VEH_002...", file=sys.stderr)
    writer.dispose_instance(instance_handles["VEH_002"])
    print("  Disposed: VEH_002", file=sys.stderr)
    
    time.sleep(0.5)
    
    # Phase 4: Continue updates for remaining vehicles
    print("\nPhase 4: Continuing with VEH_001 and VEH_003...", file=sys.stderr)
    for seq in range(6, 9):
        for vid in ["VEH_001", "VEH_003"]:
            sample = dds.DynamicData(vehicle_type)
            sample["vehicle_id"] = vid
            sample["x"] = float(seq * 10)
            sample["y"] = float(seq * 5)
            sample["status"] = "ACTIVE"
            sample["sequence"] = seq
            
            writer.write(sample, instance_handles[vid])
            print(f"  [{seq}] Updated: {vid}", file=sys.stderr)
        
        time.sleep(0.2)
    
    # Phase 5: Unregister VEH_003 (completely remove)
    print("\nPhase 5: Unregistering VEH_003...", file=sys.stderr)
    writer.unregister_instance(instance_handles["VEH_003"])
    print("  Unregistered: VEH_003", file=sys.stderr)
    
    time.sleep(0.5)
    
    # Phase 6: Final update for VEH_001 only
    print("\nPhase 6: Final update for VEH_001...", file=sys.stderr)
    sample = dds.DynamicData(vehicle_type)
    sample["vehicle_id"] = "VEH_001"
    sample["x"] = 100.0
    sample["y"] = 50.0
    sample["status"] = "FINAL"
    sample["sequence"] = 10
    writer.write(sample, instance_handles["VEH_001"])
    print("  [10] Updated: VEH_001", file=sys.stderr)
    
    time.sleep(2.0)  # Allow delivery
    print("\nComplete!", file=sys.stderr)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Keyed Instance Lifecycle Subscriber.

Tracks instance state changes:
- ALIVE: Instance is active
- NOT_ALIVE_DISPOSED: Instance was disposed
- NOT_ALIVE_NO_WRITERS: Instance was unregistered or writer left

Outputs JSONL with instance state information.
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


def create_vehicle_type():
    t = dds.StructType("Vehicle")
    t.add_member(dds.Member("vehicle_id", dds.StringType(64)))
    t.add_member(dds.Member("x", dds.Float64Type()))
    t.add_member(dds.Member("y", dds.Float64Type()))
    t.add_member(dds.Member("status", dds.StringType(32)))
    t.add_member(dds.Member("sequence", dds.Int32Type()))
    return t


def instance_state_to_string(state):
    """Convert instance state enum to readable string."""
    if state == dds.InstanceState.ALIVE:
        return "ALIVE"
    elif state == dds.InstanceState.NOT_ALIVE_DISPOSED:
        return "DISPOSED"
    elif state == dds.InstanceState.NOT_ALIVE_NO_WRITERS:
        return "NO_WRITERS"
    else:
        return f"UNKNOWN({state})"


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    vehicle_type = create_vehicle_type()
    topic = dds.DynamicData.Topic(participant, "VehicleTracker", vehicle_type)
    
    subscriber = dds.Subscriber(participant)
    
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    reader = dds.DynamicData.DataReader(subscriber, topic, reader_qos)
    
    # WaitSet with read condition for ANY state (including not-alive)
    waitset = dds.WaitSet()
    
    # Use DataState to capture all instance states
    any_state = dds.DataState(
        dds.SampleState.ANY,
        dds.ViewState.ANY,
        dds.InstanceState.ANY  # Important: Captures ALIVE, DISPOSED, NO_WRITERS
    )
    read_condition = dds.ReadCondition(reader, any_state)
    waitset.attach_condition(read_condition)
    
    # Track instance states
    instance_states = {}
    sample_count = 0
    start_time = time.time()
    
    print("Listening for vehicle instances...", file=sys.stderr)
    
    while running:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            # Use take() to get all samples including disposed/unregistered
            for sample in reader.take():
                vid = None
                
                # Check instance state
                inst_state = sample.info.state.instance_state
                state_str = instance_state_to_string(inst_state)
                
                if sample.info.valid:
                    # Valid sample with data
                    vid = sample.data["vehicle_id"]
                    
                    output = {
                        "vehicle_id": vid,
                        "x": sample.data["x"],
                        "y": sample.data["y"],
                        "status": sample.data["status"],
                        "sequence": sample.data["sequence"],
                        "instance_state": state_str,
                    }
                    print(json.dumps(output), flush=True)
                    sample_count += 1
                    
                else:
                    # Invalid sample (dispose/unregister notification)
                    # We can get the instance handle but not the key directly
                    # For disposed/unregistered, info.valid is False
                    
                    output = {
                        "vehicle_id": None,  # Can't access key on invalid sample
                        "instance_state": state_str,
                        "event": "lifecycle_change",
                    }
                    print(json.dumps(output), flush=True)
                
                # Track state changes
                if vid:
                    prev_state = instance_states.get(vid)
                    if prev_state != state_str:
                        print(f"  State change: {vid} {prev_state} -> {state_str}", 
                              file=sys.stderr)
                        instance_states[vid] = state_str
    
    print(f"\nReceived {sample_count} valid samples", file=sys.stderr)
    print(f"Final instance states: {instance_states}", file=sys.stderr)


if __name__ == "__main__":
    main()


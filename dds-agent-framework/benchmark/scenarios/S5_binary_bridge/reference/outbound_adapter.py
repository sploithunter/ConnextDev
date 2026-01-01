#!/usr/bin/env python3
"""DDS → Binary Outbound Adapter.

Subscribes to DDS topics and outputs binary messages to stdout.
Each DDS topic maps back to a binary message type.
"""

import argparse
import signal
import sys
import time

import rti.connextdds as dds

from protocol import encode_message, Heartbeat, Position, Command, Status


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_heartbeat_type():
    t = dds.StructType("Heartbeat")
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_position_type():
    t = dds.StructType("Position")
    t.add_member(dds.Member("latitude", dds.Float64Type()))
    t.add_member(dds.Member("longitude", dds.Float64Type()))
    t.add_member(dds.Member("altitude", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_command_type():
    t = dds.StructType("Command")
    t.add_member(dds.Member("command_id", dds.Int32Type()))
    t.add_member(dds.Member("parameter", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def create_status_type():
    t = dds.StructType("Status")
    t.add_member(dds.Member("status_code", dds.Int32Type()))
    t.add_member(dds.Member("message", dds.StringType(256)))
    t.add_member(dds.Member("timestamp", dds.Float64Type()))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--count", "-c", type=int, default=0,
                        help="Exit after receiving N messages (0=unlimited)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output file (default: stdout)")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    # Create types and topics
    hb_type = create_heartbeat_type()
    pos_type = create_position_type()
    cmd_type = create_command_type()
    status_type = create_status_type()
    
    hb_topic = dds.DynamicData.Topic(participant, "Heartbeat", hb_type)
    pos_topic = dds.DynamicData.Topic(participant, "Position", pos_type)
    cmd_topic = dds.DynamicData.Topic(participant, "Command", cmd_type)
    status_topic = dds.DynamicData.Topic(participant, "Status", status_type)
    
    # Create subscriber with matching QoS
    subscriber = dds.Subscriber(participant)
    
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    hb_reader = dds.DynamicData.DataReader(subscriber, hb_topic, reader_qos)
    pos_reader = dds.DynamicData.DataReader(subscriber, pos_topic, reader_qos)
    cmd_reader = dds.DynamicData.DataReader(subscriber, cmd_topic, reader_qos)
    status_reader = dds.DynamicData.DataReader(subscriber, status_topic, reader_qos)
    
    # WaitSet with conditions for all readers
    waitset = dds.WaitSet()
    
    hb_cond = dds.ReadCondition(hb_reader, dds.DataState.any_data)
    pos_cond = dds.ReadCondition(pos_reader, dds.DataState.any_data)
    cmd_cond = dds.ReadCondition(cmd_reader, dds.DataState.any_data)
    status_cond = dds.ReadCondition(status_reader, dds.DataState.any_data)
    
    waitset.attach_condition(hb_cond)
    waitset.attach_condition(pos_cond)
    waitset.attach_condition(cmd_cond)
    waitset.attach_condition(status_cond)
    
    # Output
    if args.output:
        output = open(args.output, "wb")
    else:
        output = sys.stdout.buffer
    
    counts = {"heartbeat": 0, "position": 0, "command": 0, "status": 0}
    total = 0
    start_time = time.time()
    
    print("Outbound adapter ready...", file=sys.stderr)
    
    try:
        while running:
            if args.count > 0 and total >= args.count:
                break
            
            elapsed = time.time() - start_time
            if elapsed > args.timeout:
                break
            
            remaining = min(1.0, args.timeout - elapsed)
            active = waitset.wait(dds.Duration.from_seconds(remaining))
            
            # Process heartbeats
            if hb_cond in active:
                for sample in hb_reader.take():
                    if sample.info.valid:
                        msg = Heartbeat()
                        output.write(encode_message(msg))
                        output.flush()
                        counts["heartbeat"] += 1
                        total += 1
            
            # Process positions
            if pos_cond in active:
                for sample in pos_reader.take():
                    if sample.info.valid:
                        msg = Position(
                            latitude=sample.data["latitude"],
                            longitude=sample.data["longitude"],
                            altitude=sample.data["altitude"],
                        )
                        output.write(encode_message(msg))
                        output.flush()
                        counts["position"] += 1
                        total += 1
            
            # Process commands
            if cmd_cond in active:
                for sample in cmd_reader.take():
                    if sample.info.valid:
                        msg = Command(
                            command_id=sample.data["command_id"],
                            parameter=sample.data["parameter"],
                        )
                        output.write(encode_message(msg))
                        output.flush()
                        counts["command"] += 1
                        total += 1
            
            # Process status
            if status_cond in active:
                for sample in status_reader.take():
                    if sample.info.valid:
                        msg = Status(
                            status_code=sample.data["status_code"],
                            message=sample.data["message"],
                        )
                        output.write(encode_message(msg))
                        output.flush()
                        counts["status"] += 1
                        total += 1
    
    finally:
        if args.output:
            output.close()
    
    print(f"Received: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()


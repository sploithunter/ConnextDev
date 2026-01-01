#!/usr/bin/env python3
"""Binary → DDS Inbound Adapter.

Reads binary messages from stdin and publishes to DDS topics.
Each message type maps to a separate DDS topic.
"""

import argparse
import signal
import sys
import time

import rti.connextdds as dds

from protocol import decode_message, Heartbeat, Position, Command, Status


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
    parser.add_argument("--input", "-i", type=str, default=None,
                        help="Input file (default: stdin)")
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
    
    # Create publisher with RELIABLE + TRANSIENT_LOCAL
    publisher = dds.Publisher(participant)
    
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    hb_writer = dds.DynamicData.DataWriter(publisher, hb_topic, writer_qos)
    pos_writer = dds.DynamicData.DataWriter(publisher, pos_topic, writer_qos)
    cmd_writer = dds.DynamicData.DataWriter(publisher, cmd_topic, writer_qos)
    status_writer = dds.DynamicData.DataWriter(publisher, status_topic, writer_qos)
    
    # Wait for discovery
    time.sleep(2.0)
    
    # Read binary input
    if args.input:
        with open(args.input, "rb") as f:
            data = f.read()
    else:
        data = sys.stdin.buffer.read()
    
    # Process messages
    offset = 0
    counts = {"heartbeat": 0, "position": 0, "command": 0, "status": 0}
    
    while offset < len(data):
        msg, consumed = decode_message(data[offset:])
        
        if msg is None:
            print(f"Warning: Incomplete message at offset {offset}", file=sys.stderr)
            break
        
        ts = time.time()
        
        if isinstance(msg, Heartbeat):
            sample = dds.DynamicData(hb_type)
            sample["timestamp"] = ts
            hb_writer.write(sample)
            counts["heartbeat"] += 1
            
        elif isinstance(msg, Position):
            sample = dds.DynamicData(pos_type)
            sample["latitude"] = msg.latitude
            sample["longitude"] = msg.longitude
            sample["altitude"] = msg.altitude
            sample["timestamp"] = ts
            pos_writer.write(sample)
            counts["position"] += 1
            
        elif isinstance(msg, Command):
            sample = dds.DynamicData(cmd_type)
            sample["command_id"] = msg.command_id
            sample["parameter"] = msg.parameter
            sample["timestamp"] = ts
            cmd_writer.write(sample)
            counts["command"] += 1
            
        elif isinstance(msg, Status):
            sample = dds.DynamicData(status_type)
            sample["status_code"] = msg.status_code
            sample["message"] = msg.message
            sample["timestamp"] = ts
            status_writer.write(sample)
            counts["status"] += 1
        
        offset += consumed
    
    # Wait for delivery
    time.sleep(2.0)
    
    print(f"Published: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()


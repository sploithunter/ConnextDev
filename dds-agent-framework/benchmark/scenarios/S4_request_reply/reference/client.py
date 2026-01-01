#!/usr/bin/env python3
"""Request/Reply Pattern - Client.

Sends calculator requests and correlates replies.
Outputs JSONL with request/reply pairs.
"""

import argparse
import json
import signal
import sys
import time
import uuid

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def create_request_type():
    t = dds.StructType("CalculatorRequest")
    t.add_member(dds.Member("correlation_id", dds.StringType(64)))
    t.add_member(dds.Member("client_id", dds.StringType(64)))
    t.add_member(dds.Member("operation", dds.StringType(16)))
    t.add_member(dds.Member("operand_a", dds.Float64Type()))
    t.add_member(dds.Member("operand_b", dds.Float64Type()))
    return t


def create_reply_type():
    t = dds.StructType("CalculatorReply")
    t.add_member(dds.Member("correlation_id", dds.StringType(64)))
    t.add_member(dds.Member("client_id", dds.StringType(64)))
    t.add_member(dds.Member("success", dds.BoolType()))
    t.add_member(dds.Member("result", dds.Float64Type()))
    t.add_member(dds.Member("error_message", dds.StringType(256)))
    return t


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    client_id = f"CLIENT_{uuid.uuid4().hex[:8]}"
    
    participant = dds.DomainParticipant(args.domain)
    
    request_type = create_request_type()
    reply_type = create_reply_type()
    
    request_topic = dds.DynamicData.Topic(participant, "CalculatorRequest", request_type)
    reply_topic = dds.DynamicData.Topic(participant, "CalculatorReply", reply_type)
    
    # Publisher for requests
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    request_writer = dds.DynamicData.DataWriter(publisher, request_topic, writer_qos)
    
    # Subscriber for replies
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    # Read all replies and filter in application (simpler for debugging)
    reply_reader = dds.DynamicData.DataReader(subscriber, reply_topic, reader_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(reply_reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    # Wait for bidirectional discovery
    print("Waiting for service discovery...", file=sys.stderr)
    
    # Wait for request writer to discover service's reader
    # AND wait for reply reader to discover service's writer
    matched = False
    for _ in range(30):  # 3 second max wait
        pub_match = request_writer.publication_matched_status
        sub_match = reply_reader.subscription_matched_status
        
        if pub_match.current_count > 0 and sub_match.current_count > 0:
            matched = True
            print(f"Matched! Request readers: {pub_match.current_count}, "
                  f"Reply writers: {sub_match.current_count}", file=sys.stderr)
            break
        
        time.sleep(0.1)
    
    if not matched:
        print("Warning: Full discovery not achieved", file=sys.stderr)
    
    time.sleep(0.5)  # Extra settle time
    
    # Test operations
    operations = [
        ("ADD", 10.0, 5.0),    # = 15
        ("SUB", 20.0, 8.0),    # = 12
        ("MUL", 3.0, 7.0),     # = 21
        ("DIV", 100.0, 4.0),   # = 25
        ("DIV", 1.0, 0.0),     # = error
        ("MOD", 10.0, 3.0),    # = error (unknown op)
    ]
    
    pending_requests = {}  # correlation_id -> request_info
    completed = []
    
    # Send all requests with small delay for reliability
    for op, a, b in operations:
        correlation_id = str(uuid.uuid4())
        
        request = dds.DynamicData(request_type)
        request["correlation_id"] = correlation_id
        request["client_id"] = client_id
        request["operation"] = op
        request["operand_a"] = a
        request["operand_b"] = b
        
        request_writer.write(request)
        pending_requests[correlation_id] = {
            "operation": op,
            "operand_a": a,
            "operand_b": b,
            "sent_at": time.time(),
        }
        
        print(f"Sent: {op}({a}, {b})", file=sys.stderr)
        time.sleep(0.1)  # Brief delay between requests
    
    # Wait for replies
    start_time = time.time()
    
    while running and len(pending_requests) > 0:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in reply_reader.take():
                if sample.info.valid:
                    # Filter for our client (since we're not using CFT)
                    if sample.data["client_id"] != client_id:
                        continue
                    
                    correlation_id = sample.data["correlation_id"]
                    
                    if correlation_id in pending_requests:
                        req = pending_requests.pop(correlation_id)
                        
                        output = {
                            "operation": req["operation"],
                            "operand_a": req["operand_a"],
                            "operand_b": req["operand_b"],
                            "success": sample.data["success"],
                            "result": sample.data["result"],
                            "error": sample.data["error_message"],
                            "round_trip_ms": (time.time() - req["sent_at"]) * 1000,
                        }
                        print(json.dumps(output), flush=True)
                        completed.append(output)
    
    print(f"\nCompleted {len(completed)}/{len(operations)} requests", file=sys.stderr)
    
    if pending_requests:
        print(f"Pending (timeout): {list(pending_requests.keys())}", file=sys.stderr)


if __name__ == "__main__":
    main()


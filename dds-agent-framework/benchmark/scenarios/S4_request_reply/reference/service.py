#!/usr/bin/env python3
"""Request/Reply Pattern - Service (Server).

Implements a simple calculator service that:
1. Listens for CalculatorRequest
2. Processes the operation
3. Sends CalculatorReply with same correlation_id
"""

import argparse
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
    t.add_member(dds.Member("operation", dds.StringType(16)))  # ADD, SUB, MUL, DIV
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


def process_request(operation: str, a: float, b: float) -> tuple:
    """Process calculator operation. Returns (success, result, error)."""
    try:
        if operation == "ADD":
            return True, a + b, ""
        elif operation == "SUB":
            return True, a - b, ""
        elif operation == "MUL":
            return True, a * b, ""
        elif operation == "DIV":
            if b == 0:
                return False, 0.0, "Division by zero"
            return True, a / b, ""
        else:
            return False, 0.0, f"Unknown operation: {operation}"
    except Exception as e:
        return False, 0.0, str(e)


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    request_type = create_request_type()
    reply_type = create_reply_type()
    
    request_topic = dds.DynamicData.Topic(participant, "CalculatorRequest", request_type)
    reply_topic = dds.DynamicData.Topic(participant, "CalculatorReply", reply_type)
    
    # Subscriber for requests
    subscriber = dds.Subscriber(participant)
    reader_qos = dds.DataReaderQos()
    reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    request_reader = dds.DynamicData.DataReader(subscriber, request_topic, reader_qos)
    
    # Publisher for replies
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    
    reply_writer = dds.DynamicData.DataWriter(publisher, reply_topic, writer_qos)
    
    waitset = dds.WaitSet()
    read_condition = dds.ReadCondition(request_reader, dds.DataState.any_data)
    waitset.attach_condition(read_condition)
    
    request_count = 0
    start_time = time.time()
    
    print("Calculator service ready...", file=sys.stderr)
    
    while running:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        remaining = min(1.0, args.timeout - elapsed)
        active = waitset.wait(dds.Duration.from_seconds(remaining))
        
        if read_condition in active:
            for sample in request_reader.take():
                if sample.info.valid:
                    correlation_id = sample.data["correlation_id"]
                    client_id = sample.data["client_id"]
                    operation = sample.data["operation"]
                    a = sample.data["operand_a"]
                    b = sample.data["operand_b"]
                    
                    print(f"Request: {operation}({a}, {b}) from {client_id}", 
                          file=sys.stderr)
                    
                    # Process
                    success, result, error = process_request(operation, a, b)
                    
                    # Send reply
                    reply = dds.DynamicData(reply_type)
                    reply["correlation_id"] = correlation_id
                    reply["client_id"] = client_id
                    reply["success"] = success
                    reply["result"] = result
                    reply["error_message"] = error
                    
                    reply_writer.write(reply)
                    request_count += 1
                    
                    print(f"  Reply: {result if success else error}", file=sys.stderr)
    
    print(f"\nProcessed {request_count} requests", file=sys.stderr)


if __name__ == "__main__":
    main()


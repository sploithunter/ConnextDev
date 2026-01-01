#!/usr/bin/env python3
"""Simple Binary Protocol Definition.

Message format (TLV-like):
  [2 bytes] Message type (uint16, big-endian)
  [2 bytes] Payload length (uint16, big-endian)
  [N bytes] Payload

Message types:
  0x0001 = Heartbeat (no payload)
  0x0002 = Position (lat: float64, lon: float64, alt: float64)
  0x0003 = Command (command_id: uint32, param: float64)
  0x0004 = Status (status_code: uint32, message: string)
"""

import struct
from dataclasses import dataclass
from typing import Optional, Tuple, Union


MSG_HEARTBEAT = 0x0001
MSG_POSITION = 0x0002
MSG_COMMAND = 0x0003
MSG_STATUS = 0x0004


@dataclass
class Heartbeat:
    pass


@dataclass
class Position:
    latitude: float
    longitude: float
    altitude: float


@dataclass
class Command:
    command_id: int
    parameter: float


@dataclass
class Status:
    status_code: int
    message: str


Message = Union[Heartbeat, Position, Command, Status]


def encode_message(msg: Message) -> bytes:
    """Encode a message to binary format."""
    if isinstance(msg, Heartbeat):
        msg_type = MSG_HEARTBEAT
        payload = b""
    elif isinstance(msg, Position):
        msg_type = MSG_POSITION
        payload = struct.pack(">ddd", msg.latitude, msg.longitude, msg.altitude)
    elif isinstance(msg, Command):
        msg_type = MSG_COMMAND
        payload = struct.pack(">Id", msg.command_id, msg.parameter)
    elif isinstance(msg, Status):
        msg_type = MSG_STATUS
        msg_bytes = msg.message.encode("utf-8")[:255]
        payload = struct.pack(">I", msg.status_code) + bytes([len(msg_bytes)]) + msg_bytes
    else:
        raise ValueError(f"Unknown message type: {type(msg)}")
    
    header = struct.pack(">HH", msg_type, len(payload))
    return header + payload


def decode_message(data: bytes) -> Tuple[Optional[Message], int]:
    """Decode a message from binary format.
    
    Returns (message, bytes_consumed) or (None, 0) if incomplete.
    """
    if len(data) < 4:
        return None, 0
    
    msg_type, payload_len = struct.unpack(">HH", data[:4])
    
    if len(data) < 4 + payload_len:
        return None, 0
    
    payload = data[4:4 + payload_len]
    
    if msg_type == MSG_HEARTBEAT:
        return Heartbeat(), 4 + payload_len
    elif msg_type == MSG_POSITION:
        lat, lon, alt = struct.unpack(">ddd", payload)
        return Position(lat, lon, alt), 4 + payload_len
    elif msg_type == MSG_COMMAND:
        cmd_id, param = struct.unpack(">Id", payload)
        return Command(cmd_id, param), 4 + payload_len
    elif msg_type == MSG_STATUS:
        status_code = struct.unpack(">I", payload[:4])[0]
        msg_len = payload[4]
        message = payload[5:5 + msg_len].decode("utf-8")
        return Status(status_code, message), 4 + payload_len
    else:
        raise ValueError(f"Unknown message type: 0x{msg_type:04x}")


if __name__ == "__main__":
    # Test encoding/decoding
    messages = [
        Heartbeat(),
        Position(37.7749, -122.4194, 100.0),
        Command(42, 3.14159),
        Status(200, "OK"),
    ]
    
    for msg in messages:
        encoded = encode_message(msg)
        decoded, consumed = decode_message(encoded)
        print(f"{msg} -> {encoded.hex()} -> {decoded}")
        assert decoded == msg, f"Round-trip failed: {msg} != {decoded}"
    
    print("\nAll tests passed!")


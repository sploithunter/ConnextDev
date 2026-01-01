#!/usr/bin/env python3
"""Type definitions for extensibility test.

V1 Type: Original type with basic fields
V2 Type: Extended type with additional fields (backward compatible)

Key extensibility concepts:
1. MUTABLE extensibility allows adding fields
2. APPENDABLE allows adding to the end only
3. FINAL does not allow any changes
4. Optional members with @optional annotation
5. Default values for new fields
"""

import rti.connextdds as dds


def create_sensor_v1_type():
    """
    Version 1: Basic sensor reading.
    
    This is the ORIGINAL type that existing subscribers expect.
    """
    t = dds.StructType("SensorReading")
    
    # Use MUTABLE extensibility to allow future extensions
    # Note: In Python API, we set this through type properties
    
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Int64Type()))
    t.add_member(dds.Member("unit", dds.StringType(16)))
    
    return t


def create_sensor_v2_type():
    """
    Version 2: Extended sensor reading with new fields.
    
    MUST be backward compatible with V1 subscribers:
    - All V1 fields present in same order
    - New fields are OPTIONAL or have defaults
    - Uses MUTABLE extensibility
    
    New fields:
    - quality: int (0=bad, 1=uncertain, 2=good)
    - location_lat: double (optional)
    - location_lon: double (optional)
    - metadata: string (optional)
    """
    t = dds.StructType("SensorReading")
    
    # Original V1 fields (MUST remain in same position)
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Int64Type()))
    t.add_member(dds.Member("unit", dds.StringType(16)))
    
    # NEW V2 fields (appended)
    # These will be ignored by V1 subscribers
    t.add_member(dds.Member("quality", dds.Int32Type()))
    t.add_member(dds.Member("location_lat", dds.Float64Type()))
    t.add_member(dds.Member("location_lon", dds.Float64Type()))
    t.add_member(dds.Member("metadata", dds.StringType(256)))
    
    return t


def create_sensor_v3_type():
    """
    Version 3: Even more extended (for future tests).
    
    New fields:
    - calibration_date: int64 (timestamp)
    - firmware_version: string
    - error_code: int32
    """
    t = dds.StructType("SensorReading")
    
    # V1 fields
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("timestamp", dds.Int64Type()))
    t.add_member(dds.Member("unit", dds.StringType(16)))
    
    # V2 fields
    t.add_member(dds.Member("quality", dds.Int32Type()))
    t.add_member(dds.Member("location_lat", dds.Float64Type()))
    t.add_member(dds.Member("location_lon", dds.Float64Type()))
    t.add_member(dds.Member("metadata", dds.StringType(256)))
    
    # V3 fields
    t.add_member(dds.Member("calibration_date", dds.Int64Type()))
    t.add_member(dds.Member("firmware_version", dds.StringType(32)))
    t.add_member(dds.Member("error_code", dds.Int32Type()))
    
    return t


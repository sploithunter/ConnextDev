#!/usr/bin/env python3
"""DDS Type definitions for Industrial Sensor Network - V2 (Extended)."""

import rti.connextdds as dds

# Import V1 types for non-extended types
from types_v1 import (
    create_pressure_reading,
    create_aggregated_metrics,
    create_system_alert,
    create_config_request,
    create_config_reply,
)


def create_temperature_reading_v2():
    """Temperature sensor reading (V2 - extended with location and model).
    
    Backward compatible with V1:
    - V1 subscribers will ignore new fields
    - V2 subscribers get all fields
    """
    t = dds.StructType("TemperatureReading")
    
    # V1 fields (same order)
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("value_celsius", dds.Float64Type()))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    
    # V2 new fields (appended)
    t.add_member(dds.Member("location", dds.StringType(128)))  # e.g., "Building A, Floor 2"
    t.add_member(dds.Member("sensor_model", dds.StringType(64)))  # e.g., "TempSensor-3000"
    t.add_member(dds.Member("calibration_date", dds.Int64Type()))  # Unix timestamp
    
    return t


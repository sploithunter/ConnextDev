#!/usr/bin/env python3
"""DDS Type definitions for bridged MQTT data."""

import rti.connextdds as dds


def create_sensor_temperature_type():
    """Temperature sensor data (from sensors/temperature)."""
    t = dds.StructType("SensorTemperature")
    t.add_member(dds.Member("device_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("unit", dds.StringType(8)))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


def create_sensor_humidity_type():
    """Humidity sensor data (from sensors/humidity)."""
    t = dds.StructType("SensorHumidity")
    t.add_member(dds.Member("device_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("unit", dds.StringType(8)))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


def create_device_status_type():
    """Device status data (from sensors/status)."""
    t = dds.StructType("DeviceStatus")
    t.add_member(dds.Member("device_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("online", dds.BoolType()))
    t.add_member(dds.Member("battery", dds.Int32Type()))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


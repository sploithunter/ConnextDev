#!/usr/bin/env python3
"""DDS Type definitions for Industrial Sensor Network - V1."""

import rti.connextdds as dds


def create_temperature_reading_v1():
    """Temperature sensor reading (V1 - basic)."""
    t = dds.StructType("TemperatureReading")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("value_celsius", dds.Float64Type()))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


def create_pressure_reading():
    """Pressure sensor reading."""
    t = dds.StructType("PressureReading")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("value_kpa", dds.Float64Type()))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


def create_aggregated_metrics():
    """Aggregated metrics from multiple readings."""
    t = dds.StructType("AggregatedMetrics")
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("metric_type", dds.StringType(32)))  # "temperature" or "pressure"
    t.add_member(dds.Member("avg_value", dds.Float64Type()))
    t.add_member(dds.Member("min_value", dds.Float64Type()))
    t.add_member(dds.Member("max_value", dds.Float64Type()))
    t.add_member(dds.Member("sample_count", dds.Int32Type()))
    t.add_member(dds.Member("window_start_ms", dds.Int64Type()))
    t.add_member(dds.Member("window_end_ms", dds.Int64Type()))
    return t


def create_system_alert():
    """System alert for anomalies."""
    t = dds.StructType("SystemAlert")
    t.add_member(dds.Member("alert_id", dds.StringType(64)))  # Key
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("severity", dds.Int32Type()))  # 1=info, 2=warning, 3=critical
    t.add_member(dds.Member("message", dds.StringType(256)))
    t.add_member(dds.Member("value", dds.Float64Type()))
    t.add_member(dds.Member("threshold", dds.Float64Type()))
    t.add_member(dds.Member("timestamp_ms", dds.Int64Type()))
    return t


def create_config_request():
    """Configuration request."""
    t = dds.StructType("ConfigRequest")
    t.add_member(dds.Member("request_id", dds.StringType(64)))
    t.add_member(dds.Member("sensor_id", dds.StringType(64)))
    t.add_member(dds.Member("parameter", dds.StringType(64)))  # e.g., "polling_rate_ms"
    t.add_member(dds.Member("value", dds.Float64Type()))
    return t


def create_config_reply():
    """Configuration reply."""
    t = dds.StructType("ConfigReply")
    t.add_member(dds.Member("request_id", dds.StringType(64)))
    t.add_member(dds.Member("success", dds.BoolType()))
    t.add_member(dds.Member("message", dds.StringType(256)))
    t.add_member(dds.Member("previous_value", dds.Float64Type()))
    t.add_member(dds.Member("new_value", dds.Float64Type()))
    return t


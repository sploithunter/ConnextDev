#!/usr/bin/env python3
"""Generate a large, realistic aerospace telemetry data model.

Creates ~500 fields across multiple nested structures representing
a complete UAV (Unmanned Aerial Vehicle) telemetry system.

Output: JSON Schema format (not directly usable by DDS)
The challenge is to convert this to DynamicData types.
"""

import json
import random


def generate_field(prefix: str, name: str, field_type: str, description: str = None):
    """Generate a field definition."""
    field = {
        "type": field_type,
    }
    if description:
        field["description"] = description
    return field


def generate_vector3(prefix: str) -> dict:
    """3D vector with x, y, z."""
    return {
        "type": "object",
        "properties": {
            f"{prefix}_x": {"type": "number", "description": f"{prefix} X component"},
            f"{prefix}_y": {"type": "number", "description": f"{prefix} Y component"},
            f"{prefix}_z": {"type": "number", "description": f"{prefix} Z component"},
        },
        "required": [f"{prefix}_x", f"{prefix}_y", f"{prefix}_z"],
    }


def generate_quaternion(prefix: str) -> dict:
    """Quaternion with w, x, y, z."""
    return {
        "type": "object",
        "properties": {
            f"{prefix}_w": {"type": "number", "description": f"{prefix} W component"},
            f"{prefix}_x": {"type": "number", "description": f"{prefix} X component"},
            f"{prefix}_y": {"type": "number", "description": f"{prefix} Y component"},
            f"{prefix}_z": {"type": "number", "description": f"{prefix} Z component"},
        },
    }


def generate_gps_data() -> dict:
    """GPS subsystem data."""
    return {
        "type": "object",
        "properties": {
            "gps_latitude_deg": {"type": "number", "minimum": -90, "maximum": 90},
            "gps_longitude_deg": {"type": "number", "minimum": -180, "maximum": 180},
            "gps_altitude_msl_m": {"type": "number", "description": "Altitude above mean sea level"},
            "gps_altitude_agl_m": {"type": "number", "description": "Altitude above ground level"},
            "gps_ground_speed_mps": {"type": "number", "minimum": 0},
            "gps_vertical_speed_mps": {"type": "number"},
            "gps_track_deg": {"type": "number", "minimum": 0, "maximum": 360},
            "gps_hdop": {"type": "number", "description": "Horizontal dilution of precision"},
            "gps_vdop": {"type": "number", "description": "Vertical dilution of precision"},
            "gps_pdop": {"type": "number", "description": "Position dilution of precision"},
            "gps_satellites_visible": {"type": "integer", "minimum": 0},
            "gps_satellites_used": {"type": "integer", "minimum": 0},
            "gps_fix_type": {"type": "integer", "enum": [0, 1, 2, 3, 4, 5], "description": "0=None,1=2D,2=3D,3=DGPS,4=RTK,5=Float"},
            "gps_utc_time_ms": {"type": "integer"},
            "gps_accuracy_horizontal_m": {"type": "number"},
            "gps_accuracy_vertical_m": {"type": "number"},
            "gps_geoid_separation_m": {"type": "number"},
        },
    }


def generate_imu_data() -> dict:
    """Inertial Measurement Unit data."""
    props = {}
    
    # Accelerometers (3 redundant units)
    for unit in range(1, 4):
        for axis in ["x", "y", "z"]:
            props[f"accel_{unit}_{axis}_mps2"] = {"type": "number", "description": f"Accelerometer {unit} {axis.upper()} m/s²"}
        props[f"accel_{unit}_temperature_c"] = {"type": "number"}
        props[f"accel_{unit}_status"] = {"type": "integer"}
    
    # Gyroscopes (3 redundant units)
    for unit in range(1, 4):
        for axis in ["x", "y", "z"]:
            props[f"gyro_{unit}_{axis}_radps"] = {"type": "number", "description": f"Gyroscope {unit} {axis.upper()} rad/s"}
        props[f"gyro_{unit}_temperature_c"] = {"type": "number"}
        props[f"gyro_{unit}_status"] = {"type": "integer"}
    
    # Magnetometers (2 redundant units)
    for unit in range(1, 3):
        for axis in ["x", "y", "z"]:
            props[f"mag_{unit}_{axis}_gauss"] = {"type": "number"}
        props[f"mag_{unit}_temperature_c"] = {"type": "number"}
        props[f"mag_{unit}_calibration_status"] = {"type": "integer"}
    
    return {"type": "object", "properties": props}


def generate_attitude_data() -> dict:
    """Attitude and orientation data."""
    return {
        "type": "object",
        "properties": {
            "roll_rad": {"type": "number"},
            "pitch_rad": {"type": "number"},
            "yaw_rad": {"type": "number"},
            "roll_rate_radps": {"type": "number"},
            "pitch_rate_radps": {"type": "number"},
            "yaw_rate_radps": {"type": "number"},
            "roll_deg": {"type": "number"},
            "pitch_deg": {"type": "number"},
            "yaw_deg": {"type": "number"},
            "heading_true_deg": {"type": "number"},
            "heading_magnetic_deg": {"type": "number"},
            "quaternion_w": {"type": "number"},
            "quaternion_x": {"type": "number"},
            "quaternion_y": {"type": "number"},
            "quaternion_z": {"type": "number"},
            "attitude_source": {"type": "string", "enum": ["INS", "AHRS", "GPS", "ESTIMATED"]},
            "attitude_valid": {"type": "boolean"},
        },
    }


def generate_engine_data(engine_num: int) -> dict:
    """Single engine telemetry."""
    prefix = f"engine_{engine_num}"
    return {
        "type": "object",
        "properties": {
            f"{prefix}_rpm": {"type": "number", "minimum": 0},
            f"{prefix}_throttle_pct": {"type": "number", "minimum": 0, "maximum": 100},
            f"{prefix}_manifold_pressure_kpa": {"type": "number"},
            f"{prefix}_fuel_flow_lph": {"type": "number", "minimum": 0},
            f"{prefix}_oil_pressure_kpa": {"type": "number"},
            f"{prefix}_oil_temperature_c": {"type": "number"},
            f"{prefix}_cylinder_head_temp_c": {"type": "number"},
            f"{prefix}_exhaust_gas_temp_c": {"type": "number"},
            f"{prefix}_turbo_boost_kpa": {"type": "number"},
            f"{prefix}_vibration_level": {"type": "number"},
            f"{prefix}_status": {"type": "integer"},
            f"{prefix}_hours_total": {"type": "number"},
            f"{prefix}_hours_since_overhaul": {"type": "number"},
        },
    }


def generate_battery_data(battery_num: int) -> dict:
    """Battery pack telemetry."""
    prefix = f"battery_{battery_num}"
    props = {
        f"{prefix}_voltage_v": {"type": "number"},
        f"{prefix}_current_a": {"type": "number"},
        f"{prefix}_temperature_c": {"type": "number"},
        f"{prefix}_state_of_charge_pct": {"type": "number", "minimum": 0, "maximum": 100},
        f"{prefix}_state_of_health_pct": {"type": "number", "minimum": 0, "maximum": 100},
        f"{prefix}_capacity_remaining_ah": {"type": "number"},
        f"{prefix}_capacity_full_ah": {"type": "number"},
        f"{prefix}_cycles": {"type": "integer"},
        f"{prefix}_status": {"type": "integer"},
        f"{prefix}_fault_code": {"type": "integer"},
    }
    # Individual cell voltages (12 cells per pack)
    for cell in range(1, 13):
        props[f"{prefix}_cell_{cell}_voltage_v"] = {"type": "number"}
        props[f"{prefix}_cell_{cell}_temperature_c"] = {"type": "number"}
    
    return {"type": "object", "properties": props}


def generate_servo_data() -> dict:
    """Control surface servo data."""
    surfaces = [
        "aileron_left", "aileron_right", 
        "elevator_left", "elevator_right",
        "rudder", "flap_left", "flap_right",
        "spoiler_left", "spoiler_right",
        "trim_aileron", "trim_elevator", "trim_rudder"
    ]
    props = {}
    for surface in surfaces:
        props[f"{surface}_position_deg"] = {"type": "number"}
        props[f"{surface}_command_deg"] = {"type": "number"}
        props[f"{surface}_current_a"] = {"type": "number"}
        props[f"{surface}_temperature_c"] = {"type": "number"}
        props[f"{surface}_status"] = {"type": "integer"}
    
    return {"type": "object", "properties": props}


def generate_environmental_data() -> dict:
    """Environmental sensor data."""
    return {
        "type": "object",
        "properties": {
            "static_pressure_pa": {"type": "number"},
            "dynamic_pressure_pa": {"type": "number"},
            "total_pressure_pa": {"type": "number"},
            "barometric_altitude_m": {"type": "number"},
            "density_altitude_m": {"type": "number"},
            "indicated_airspeed_mps": {"type": "number"},
            "true_airspeed_mps": {"type": "number"},
            "calibrated_airspeed_mps": {"type": "number"},
            "mach_number": {"type": "number"},
            "outside_air_temperature_c": {"type": "number"},
            "total_air_temperature_c": {"type": "number"},
            "humidity_pct": {"type": "number"},
            "wind_speed_mps": {"type": "number"},
            "wind_direction_deg": {"type": "number"},
            "angle_of_attack_deg": {"type": "number"},
            "sideslip_angle_deg": {"type": "number"},
            "icing_detected": {"type": "boolean"},
            "pitot_heat_status": {"type": "integer"},
        },
    }


def generate_payload_data() -> dict:
    """Payload and camera gimbal data."""
    props = {
        "payload_weight_kg": {"type": "number"},
        "payload_status": {"type": "integer"},
        "gimbal_roll_deg": {"type": "number"},
        "gimbal_pitch_deg": {"type": "number"},
        "gimbal_yaw_deg": {"type": "number"},
        "gimbal_roll_rate_dps": {"type": "number"},
        "gimbal_pitch_rate_dps": {"type": "number"},
        "gimbal_yaw_rate_dps": {"type": "number"},
        "camera_mode": {"type": "string", "enum": ["OFF", "VIDEO", "PHOTO", "IR", "EO_IR"]},
        "camera_zoom_level": {"type": "number"},
        "camera_focus_distance_m": {"type": "number"},
        "camera_recording": {"type": "boolean"},
        "camera_storage_used_pct": {"type": "number"},
        "target_latitude_deg": {"type": "number"},
        "target_longitude_deg": {"type": "number"},
        "target_altitude_m": {"type": "number"},
        "target_distance_m": {"type": "number"},
        "target_bearing_deg": {"type": "number"},
        "laser_designator_active": {"type": "boolean"},
        "laser_range_m": {"type": "number"},
        "laser_code": {"type": "integer"},
    }
    return {"type": "object", "properties": props}


def generate_navigation_data() -> dict:
    """Navigation and flight planning data."""
    props = {
        "nav_mode": {"type": "string", "enum": ["MANUAL", "STABILIZED", "ALTITUDE_HOLD", "POSITION_HOLD", "MISSION", "RTL", "LOITER", "LAND"]},
        "current_waypoint_index": {"type": "integer"},
        "total_waypoints": {"type": "integer"},
        "waypoint_latitude_deg": {"type": "number"},
        "waypoint_longitude_deg": {"type": "number"},
        "waypoint_altitude_m": {"type": "number"},
        "distance_to_waypoint_m": {"type": "number"},
        "bearing_to_waypoint_deg": {"type": "number"},
        "cross_track_error_m": {"type": "number"},
        "home_latitude_deg": {"type": "number"},
        "home_longitude_deg": {"type": "number"},
        "home_altitude_m": {"type": "number"},
        "distance_to_home_m": {"type": "number"},
        "bearing_to_home_deg": {"type": "number"},
        "mission_elapsed_time_s": {"type": "number"},
        "mission_remaining_time_s": {"type": "number"},
        "estimated_endurance_s": {"type": "number"},
        "geofence_status": {"type": "string", "enum": ["INSIDE", "WARNING", "BREACH"]},
        "terrain_altitude_m": {"type": "number"},
        "terrain_clearance_m": {"type": "number"},
    }
    
    # Flight plan waypoints preview (next 5)
    for i in range(1, 6):
        props[f"preview_wp_{i}_lat_deg"] = {"type": "number"}
        props[f"preview_wp_{i}_lon_deg"] = {"type": "number"}
        props[f"preview_wp_{i}_alt_m"] = {"type": "number"}
        props[f"preview_wp_{i}_type"] = {"type": "string"}
    
    return {"type": "object", "properties": props}


def generate_comms_data() -> dict:
    """Communications and datalink data."""
    links = ["satcom", "radio_1", "radio_2", "lte", "wifi"]
    props = {}
    
    for link in links:
        props[f"{link}_connected"] = {"type": "boolean"}
        props[f"{link}_signal_strength_dbm"] = {"type": "number"}
        props[f"{link}_latency_ms"] = {"type": "number"}
        props[f"{link}_bandwidth_kbps"] = {"type": "number"}
        props[f"{link}_packet_loss_pct"] = {"type": "number"}
        props[f"{link}_bytes_sent"] = {"type": "integer"}
        props[f"{link}_bytes_received"] = {"type": "integer"}
        props[f"{link}_status"] = {"type": "integer"}
    
    props["active_link"] = {"type": "string", "enum": links}
    props["encryption_enabled"] = {"type": "boolean"}
    props["encryption_algorithm"] = {"type": "string"}
    
    return {"type": "object", "properties": props}


def generate_system_status() -> dict:
    """System health and status."""
    subsystems = [
        "flight_computer_1", "flight_computer_2", "flight_computer_3",
        "imu_unit", "gps_unit", "radar_altimeter", "transponder",
        "ads_b", "tcas", "weather_radar", "terrain_avoidance",
        "autopilot", "mission_computer", "video_encoder",
        "data_recorder", "emergency_beacon"
    ]
    props = {}
    
    for sys in subsystems:
        props[f"{sys}_status"] = {"type": "string", "enum": ["OK", "WARNING", "FAULT", "OFFLINE"]}
        props[f"{sys}_temperature_c"] = {"type": "number"}
        props[f"{sys}_uptime_s"] = {"type": "integer"}
        props[f"{sys}_error_count"] = {"type": "integer"}
        props[f"{sys}_last_error_code"] = {"type": "integer"}
    
    props["master_warning"] = {"type": "boolean"}
    props["master_caution"] = {"type": "boolean"}
    props["emergency_status"] = {"type": "string", "enum": ["NONE", "PAN", "MAYDAY"]}
    
    return {"type": "object", "properties": props}


def generate_full_schema():
    """Generate the complete UAV telemetry schema."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "UAVTelemetry",
        "description": "Complete UAV telemetry data model with ~500 fields",
        "type": "object",
        "properties": {
            # Metadata
            "message_id": {"type": "integer"},
            "timestamp_utc_ms": {"type": "integer"},
            "vehicle_id": {"type": "string", "maxLength": 32},
            "vehicle_type": {"type": "string", "enum": ["FIXED_WING", "ROTORCRAFT", "VTOL", "MULTIROTOR"]},
            "flight_id": {"type": "string", "maxLength": 64},
            "operator_id": {"type": "string", "maxLength": 64},
            
            # Core subsystems
            "gps": generate_gps_data(),
            "imu": generate_imu_data(),
            "attitude": generate_attitude_data(),
            "environment": generate_environmental_data(),
            "navigation": generate_navigation_data(),
            "payload": generate_payload_data(),
            "servos": generate_servo_data(),
            "communications": generate_comms_data(),
            "system_status": generate_system_status(),
            
            # Power systems
            "battery_1": generate_battery_data(1),
            "battery_2": generate_battery_data(2),
            
            # Propulsion (2 engines for fixed-wing)
            "engine_1": generate_engine_data(1),
            "engine_2": generate_engine_data(2),
        },
        "required": ["message_id", "timestamp_utc_ms", "vehicle_id"],
    }
    
    return schema


def count_fields(schema, prefix=""):
    """Count total fields in schema."""
    count = 0
    if schema.get("type") == "object" and "properties" in schema:
        for name, prop in schema["properties"].items():
            if prop.get("type") == "object":
                count += count_fields(prop, f"{prefix}{name}.")
            else:
                count += 1
    return count


if __name__ == "__main__":
    schema = generate_full_schema()
    
    # Count fields
    total = count_fields(schema)
    print(f"Total fields: {total}", file=__import__("sys").stderr)
    
    # Save schema
    with open("uav_telemetry_schema.json", "w") as f:
        json.dump(schema, f, indent=2)
    
    print("Schema written to uav_telemetry_schema.json")


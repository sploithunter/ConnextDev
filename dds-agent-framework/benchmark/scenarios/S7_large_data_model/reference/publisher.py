#!/usr/bin/env python3
"""Large Data Model Publisher.

Publishes UAV telemetry with ~440 fields.
Demonstrates handling of very large DDS types.
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import rti.connextdds as dds

from schema_converter import load_schema, create_dds_type_from_schema, flatten_schema


def generate_sample_data(schema: dict, message_id: int) -> dict:
    """Generate realistic sample data for all fields."""
    data = {}
    
    # Metadata
    data["message_id"] = message_id
    data["timestamp_utc_ms"] = int(time.time() * 1000)
    data["vehicle_id"] = "UAV_001"
    data["vehicle_type"] = "FIXED_WING"
    data["flight_id"] = f"FLIGHT_{int(time.time())}"
    data["operator_id"] = "OPERATOR_001"
    
    # GPS data
    base_lat = 37.7749 + (message_id * 0.0001)
    base_lon = -122.4194 + (message_id * 0.0001)
    data["gps_gps_latitude_deg"] = base_lat
    data["gps_gps_longitude_deg"] = base_lon
    data["gps_gps_altitude_msl_m"] = 1000.0 + message_id * 10
    data["gps_gps_altitude_agl_m"] = 500.0 + message_id * 5
    data["gps_gps_ground_speed_mps"] = 50.0 + random.uniform(-5, 5)
    data["gps_gps_vertical_speed_mps"] = random.uniform(-2, 2)
    data["gps_gps_track_deg"] = (90.0 + message_id) % 360
    data["gps_gps_hdop"] = random.uniform(0.8, 1.5)
    data["gps_gps_vdop"] = random.uniform(1.0, 2.0)
    data["gps_gps_pdop"] = random.uniform(1.2, 2.5)
    data["gps_gps_satellites_visible"] = random.randint(8, 15)
    data["gps_gps_satellites_used"] = random.randint(6, 12)
    data["gps_gps_fix_type"] = 3  # 3D fix
    data["gps_gps_utc_time_ms"] = int(time.time() * 1000)
    data["gps_gps_accuracy_horizontal_m"] = random.uniform(0.5, 2.0)
    data["gps_gps_accuracy_vertical_m"] = random.uniform(1.0, 3.0)
    data["gps_gps_geoid_separation_m"] = -30.0
    
    # IMU data (3 accelerometers, 3 gyros, 2 magnetometers)
    for unit in range(1, 4):
        for axis in ["x", "y", "z"]:
            data[f"imu_accel_{unit}_{axis}_mps2"] = random.uniform(-1, 1) + (9.81 if axis == "z" else 0)
            data[f"imu_gyro_{unit}_{axis}_radps"] = random.uniform(-0.1, 0.1)
        data[f"imu_accel_{unit}_temperature_c"] = random.uniform(20, 40)
        data[f"imu_accel_{unit}_status"] = 0
        data[f"imu_gyro_{unit}_temperature_c"] = random.uniform(20, 40)
        data[f"imu_gyro_{unit}_status"] = 0
    
    for unit in range(1, 3):
        for axis in ["x", "y", "z"]:
            data[f"imu_mag_{unit}_{axis}_gauss"] = random.uniform(-0.5, 0.5)
        data[f"imu_mag_{unit}_temperature_c"] = random.uniform(20, 40)
        data[f"imu_mag_{unit}_calibration_status"] = 3
    
    # Attitude
    data["attitude_roll_rad"] = math.radians(random.uniform(-5, 5))
    data["attitude_pitch_rad"] = math.radians(random.uniform(-3, 3))
    data["attitude_yaw_rad"] = math.radians((90 + message_id) % 360)
    data["attitude_roll_rate_radps"] = random.uniform(-0.1, 0.1)
    data["attitude_pitch_rate_radps"] = random.uniform(-0.1, 0.1)
    data["attitude_yaw_rate_radps"] = random.uniform(-0.1, 0.1)
    data["attitude_roll_deg"] = random.uniform(-5, 5)
    data["attitude_pitch_deg"] = random.uniform(-3, 3)
    data["attitude_yaw_deg"] = (90 + message_id) % 360
    data["attitude_heading_true_deg"] = (90 + message_id) % 360
    data["attitude_heading_magnetic_deg"] = (90 + message_id + 10) % 360
    data["attitude_quaternion_w"] = 1.0
    data["attitude_quaternion_x"] = 0.0
    data["attitude_quaternion_y"] = 0.0
    data["attitude_quaternion_z"] = 0.0
    data["attitude_attitude_source"] = "INS"
    data["attitude_attitude_valid"] = True
    
    # Environment
    data["environment_static_pressure_pa"] = 89875.0
    data["environment_dynamic_pressure_pa"] = 1500.0
    data["environment_total_pressure_pa"] = 91375.0
    data["environment_barometric_altitude_m"] = 1000.0 + message_id * 10
    data["environment_density_altitude_m"] = 1200.0 + message_id * 10
    data["environment_indicated_airspeed_mps"] = 50.0
    data["environment_true_airspeed_mps"] = 55.0
    data["environment_calibrated_airspeed_mps"] = 51.0
    data["environment_mach_number"] = 0.16
    data["environment_outside_air_temperature_c"] = -5.0
    data["environment_total_air_temperature_c"] = -3.0
    data["environment_humidity_pct"] = 45.0
    data["environment_wind_speed_mps"] = 8.0
    data["environment_wind_direction_deg"] = 270.0
    data["environment_angle_of_attack_deg"] = 3.0
    data["environment_sideslip_angle_deg"] = 0.5
    data["environment_icing_detected"] = False
    data["environment_pitot_heat_status"] = 1
    
    # Navigation
    data["navigation_nav_mode"] = "MISSION"
    data["navigation_current_waypoint_index"] = message_id % 10
    data["navigation_total_waypoints"] = 10
    data["navigation_waypoint_latitude_deg"] = base_lat + 0.01
    data["navigation_waypoint_longitude_deg"] = base_lon + 0.01
    data["navigation_waypoint_altitude_m"] = 1100.0
    data["navigation_distance_to_waypoint_m"] = 5000.0 - message_id * 100
    data["navigation_bearing_to_waypoint_deg"] = 90.0
    data["navigation_cross_track_error_m"] = random.uniform(-10, 10)
    data["navigation_home_latitude_deg"] = 37.7749
    data["navigation_home_longitude_deg"] = -122.4194
    data["navigation_home_altitude_m"] = 10.0
    data["navigation_distance_to_home_m"] = message_id * 1000
    data["navigation_bearing_to_home_deg"] = 270.0
    data["navigation_mission_elapsed_time_s"] = message_id * 60
    data["navigation_mission_remaining_time_s"] = (60 - message_id) * 60
    data["navigation_estimated_endurance_s"] = 7200.0
    data["navigation_geofence_status"] = "INSIDE"
    data["navigation_terrain_altitude_m"] = 500.0
    data["navigation_terrain_clearance_m"] = 500.0 + message_id * 5
    
    for i in range(1, 6):
        data[f"navigation_preview_wp_{i}_lat_deg"] = base_lat + i * 0.01
        data[f"navigation_preview_wp_{i}_lon_deg"] = base_lon + i * 0.01
        data[f"navigation_preview_wp_{i}_alt_m"] = 1000.0 + i * 50
        data[f"navigation_preview_wp_{i}_type"] = "WAYPOINT"
    
    # Payload/gimbal
    data["payload_payload_weight_kg"] = 15.0
    data["payload_payload_status"] = 1
    data["payload_gimbal_roll_deg"] = 0.0
    data["payload_gimbal_pitch_deg"] = -30.0
    data["payload_gimbal_yaw_deg"] = 0.0
    data["payload_gimbal_roll_rate_dps"] = 0.0
    data["payload_gimbal_pitch_rate_dps"] = 0.0
    data["payload_gimbal_yaw_rate_dps"] = 0.0
    data["payload_camera_mode"] = "VIDEO"
    data["payload_camera_zoom_level"] = 1.0
    data["payload_camera_focus_distance_m"] = 1000.0
    data["payload_camera_recording"] = True
    data["payload_camera_storage_used_pct"] = 25.0 + message_id * 0.5
    data["payload_target_latitude_deg"] = base_lat + 0.005
    data["payload_target_longitude_deg"] = base_lon + 0.005
    data["payload_target_altitude_m"] = 0.0
    data["payload_target_distance_m"] = 1200.0
    data["payload_target_bearing_deg"] = 85.0
    data["payload_laser_designator_active"] = False
    data["payload_laser_range_m"] = 0.0
    data["payload_laser_code"] = 1688
    
    # Servos (12 surfaces)
    surfaces = [
        "aileron_left", "aileron_right", "elevator_left", "elevator_right",
        "rudder", "flap_left", "flap_right", "spoiler_left", "spoiler_right",
        "trim_aileron", "trim_elevator", "trim_rudder"
    ]
    for surface in surfaces:
        data[f"servos_{surface}_position_deg"] = random.uniform(-5, 5)
        data[f"servos_{surface}_command_deg"] = random.uniform(-5, 5)
        data[f"servos_{surface}_current_a"] = random.uniform(0.1, 0.5)
        data[f"servos_{surface}_temperature_c"] = random.uniform(30, 50)
        data[f"servos_{surface}_status"] = 0
    
    # Communications (5 links)
    links = ["satcom", "radio_1", "radio_2", "lte", "wifi"]
    for link in links:
        data[f"communications_{link}_connected"] = link in ["radio_1", "satcom"]
        data[f"communications_{link}_signal_strength_dbm"] = random.uniform(-80, -40)
        data[f"communications_{link}_latency_ms"] = random.uniform(20, 200)
        data[f"communications_{link}_bandwidth_kbps"] = random.uniform(100, 2000)
        data[f"communications_{link}_packet_loss_pct"] = random.uniform(0, 2)
        data[f"communications_{link}_bytes_sent"] = message_id * 10000
        data[f"communications_{link}_bytes_received"] = message_id * 5000
        data[f"communications_{link}_status"] = 0
    
    data["communications_active_link"] = "radio_1"
    data["communications_encryption_enabled"] = True
    data["communications_encryption_algorithm"] = "AES256"
    
    # System status (16 subsystems)
    subsystems = [
        "flight_computer_1", "flight_computer_2", "flight_computer_3",
        "imu_unit", "gps_unit", "radar_altimeter", "transponder",
        "ads_b", "tcas", "weather_radar", "terrain_avoidance",
        "autopilot", "mission_computer", "video_encoder",
        "data_recorder", "emergency_beacon"
    ]
    for sys in subsystems:
        data[f"system_status_{sys}_status"] = "OK"
        data[f"system_status_{sys}_temperature_c"] = random.uniform(25, 45)
        data[f"system_status_{sys}_uptime_s"] = message_id * 60 + random.randint(0, 59)
        data[f"system_status_{sys}_error_count"] = 0
        data[f"system_status_{sys}_last_error_code"] = 0
    
    data["system_status_master_warning"] = False
    data["system_status_master_caution"] = False
    data["system_status_emergency_status"] = "NONE"
    
    # Batteries (2 packs, 12 cells each)
    for bat in [1, 2]:
        data[f"battery_{bat}_battery_{bat}_voltage_v"] = 48.0 + random.uniform(-1, 1)
        data[f"battery_{bat}_battery_{bat}_current_a"] = 20.0 + random.uniform(-5, 5)
        data[f"battery_{bat}_battery_{bat}_temperature_c"] = 35.0 + random.uniform(-5, 5)
        data[f"battery_{bat}_battery_{bat}_state_of_charge_pct"] = 85.0 - message_id * 0.5
        data[f"battery_{bat}_battery_{bat}_state_of_health_pct"] = 95.0
        data[f"battery_{bat}_battery_{bat}_capacity_remaining_ah"] = 20.0 - message_id * 0.1
        data[f"battery_{bat}_battery_{bat}_capacity_full_ah"] = 25.0
        data[f"battery_{bat}_battery_{bat}_cycles"] = 150
        data[f"battery_{bat}_battery_{bat}_status"] = 0
        data[f"battery_{bat}_battery_{bat}_fault_code"] = 0
        
        for cell in range(1, 13):
            data[f"battery_{bat}_battery_{bat}_cell_{cell}_voltage_v"] = 4.0 + random.uniform(-0.1, 0.1)
            data[f"battery_{bat}_battery_{bat}_cell_{cell}_temperature_c"] = 35.0 + random.uniform(-3, 3)
    
    # Engines (2 engines)
    for eng in [1, 2]:
        data[f"engine_{eng}_engine_{eng}_rpm"] = 5500 + random.randint(-100, 100)
        data[f"engine_{eng}_engine_{eng}_throttle_pct"] = 75.0 + random.uniform(-5, 5)
        data[f"engine_{eng}_engine_{eng}_manifold_pressure_kpa"] = 85.0
        data[f"engine_{eng}_engine_{eng}_fuel_flow_lph"] = 12.0 + random.uniform(-1, 1)
        data[f"engine_{eng}_engine_{eng}_oil_pressure_kpa"] = 400.0 + random.uniform(-20, 20)
        data[f"engine_{eng}_engine_{eng}_oil_temperature_c"] = 95.0 + random.uniform(-5, 5)
        data[f"engine_{eng}_engine_{eng}_cylinder_head_temp_c"] = 180.0 + random.uniform(-10, 10)
        data[f"engine_{eng}_engine_{eng}_exhaust_gas_temp_c"] = 650.0 + random.uniform(-20, 20)
        data[f"engine_{eng}_engine_{eng}_turbo_boost_kpa"] = 15.0
        data[f"engine_{eng}_engine_{eng}_vibration_level"] = random.uniform(0.5, 1.5)
        data[f"engine_{eng}_engine_{eng}_status"] = 0
        data[f"engine_{eng}_engine_{eng}_hours_total"] = 1250.5
        data[f"engine_{eng}_engine_{eng}_hours_since_overhaul"] = 250.5
    
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    
    # Load schema
    schema_path = Path(__file__).parent.parent / "input" / "uav_telemetry_schema.json"
    schema = load_schema(str(schema_path))
    
    # Create DDS type
    uav_type = create_dds_type_from_schema(schema, "UAVTelemetry")
    
    # Create DDS entities
    participant = dds.DomainParticipant(args.domain)
    topic = dds.DynamicData.Topic(participant, "UAVTelemetry", uav_type)
    
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    # Wait for discovery
    time.sleep(2.0)
    
    # Get field list for mapping
    fields = flatten_schema(schema)
    field_names = [name for name, _ in fields]
    
    print(f"Publishing {args.count} samples with {len(field_names)} fields each", file=sys.stderr)
    
    for i in range(args.count):
        # Generate data
        data = generate_sample_data(schema, i + 1)
        
        # Create DDS sample
        sample = dds.DynamicData(uav_type)
        
        # Set all fields
        for field_name in field_names:
            if field_name in data:
                try:
                    sample[field_name] = data[field_name]
                except Exception as e:
                    pass  # Skip fields that don't match
        
        writer.write(sample)
        print(f"[{i+1}] Published message_id={data.get('message_id')}", file=sys.stderr)
        
        time.sleep(args.delay)
    
    time.sleep(2.0)
    print(f"Published {args.count} samples", file=sys.stderr)


if __name__ == "__main__":
    main()


# S16: MQTT to DDS Protocol Bridge

## Goal
Test a model's ability to bridge between different pub/sub protocols.
This is an extremely common real-world pattern for IoT/Industrial systems.

## Architecture

```
┌──────────────┐      MQTT       ┌─────────────────┐      DDS       ┌──────────────┐
│ MQTT         │ ──────────────► │  Bridge/Adapter │ ─────────────► │ DDS          │
│ Publisher    │  sensors/temp   │  (to be built)  │  Temperature   │ Subscriber   │
└──────────────┘                 └─────────────────┘  Reading       └──────────────┘
                                         │
                                         ▼
                              ┌─────────────────┐
                              │ Topic Mapping   │
                              │ sensors/temp →  │
                              │ TemperatureData │
                              └─────────────────┘
```

## Components

### 1. MQTT Publisher (Provided)
Simulates IoT sensors publishing to MQTT topics:
- `sensors/temperature` - JSON: {"device_id": "...", "value": 23.5, "unit": "C"}
- `sensors/humidity` - JSON: {"device_id": "...", "value": 65.2, "unit": "%"}
- `sensors/status` - JSON: {"device_id": "...", "online": true, "battery": 85}

### 2. Bridge Adapter (To Be Built)
The model must create:
- Subscribe to MQTT topics
- Parse JSON payloads
- Convert to DDS DynamicData
- Publish to DDS topics
- Handle connection errors gracefully

### 3. DDS Subscriber (Provided for verification)
Receives the bridged data and outputs JSONL.

## Key Challenges

1. **Async I/O**: MQTT uses callbacks, need to bridge to DDS
2. **Schema Mapping**: JSON → DDS types
3. **Topic Mapping**: MQTT topic names → DDS topic names
4. **Error Handling**: What if MQTT disconnects?
5. **QoS Alignment**: MQTT QoS 0/1/2 → DDS QoS

## MQTT Topics → DDS Topics

| MQTT Topic | DDS Topic | Type |
|------------|-----------|------|
| sensors/temperature | SensorTemperature | {device_id, value, unit, timestamp} |
| sensors/humidity | SensorHumidity | {device_id, value, unit, timestamp} |
| sensors/status | DeviceStatus | {device_id, online, battery, timestamp} |

## Dependencies
- paho-mqtt (for MQTT client)
- rti-connext-dds (for DDS)

## Expected Difficulty: L4
- Multi-protocol knowledge required
- Async callback handling
- JSON parsing and type conversion
- Error recovery patterns


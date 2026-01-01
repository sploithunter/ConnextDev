# Phase 1: Basic Temperature Sensor Publisher

## Task
Create a temperature sensor publisher that publishes readings every second.

## Requirements

1. Create `sensor_publisher.py`:
   - Publish to topic "TemperatureReading"
   - Fields: sensor_id (string), value_celsius (float64), timestamp_ms (int64)
   - Use RELIABLE reliability and TRANSIENT_LOCAL durability
   - Publish every 1 second (configurable via --rate flag)
   - Support --count flag for number of samples (0 = infinite)
   - Use sensor_id "TEMP_001"

2. Create `types_v1.py`:
   - Define the TemperatureReading type using DynamicData

## Acceptance Criteria
- Publisher runs and outputs samples to stderr
- Use `dds-spy-wrapper` to verify data is being published
- Clean shutdown on SIGTERM/SIGINT


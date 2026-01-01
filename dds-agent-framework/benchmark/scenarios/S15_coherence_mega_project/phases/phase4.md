# Phase 4: Add Pressure Sensors with Keyed Instances

## Context
Phases 1-3 implemented temperature monitoring. Now add pressure sensors.

## Task
Extend the sensor publisher to also publish pressure readings.
Use keyed instances for proper instance lifecycle management.

## Requirements

1. Modify `sensor_publisher.py`:
   - Add pressure sensor publishing
   - Use multiple sensor IDs: TEMP_001, TEMP_002, PRESSURE_001, PRESSURE_002
   - Each sensor_id is a separate DDS instance (keyed)

2. Add to `types_v1.py`:
   - PressureReading type: sensor_id (key), value_kpa (float64), timestamp_ms

3. Modify `aggregator.py`:
   - Also subscribe to PressureReading
   - Calculate rolling averages for pressure too

4. Modify `alert_monitor.py`:
   - Add pressure thresholds (>110 kPa warning, <95 kPa warning)

## Acceptance Criteria
- Publisher outputs both temperature and pressure readings
- Aggregator processes both types
- Alert monitor detects both types of anomalies
- **All Phase 1-3 functionality still works**


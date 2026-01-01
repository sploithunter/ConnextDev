# S15: Long-Context Coherence Mega-Project

## Goal
Test a model's ability to build a complex, multi-component DDS system
incrementally while maintaining coherence across all files.

## The Project: Industrial Sensor Network

A complete industrial monitoring system with:
- Multiple sensor types
- Data aggregation/transformation
- Alerting
- Historical logging
- Request/Reply for configuration

## Phases (Incremental Instructions)

### Phase 1: Basic Sensor Publisher
"Create a temperature sensor publisher that publishes readings every second."
- Files: sensor_publisher.py
- Topics: TemperatureReading

### Phase 2: Add Subscriber with Aggregation  
"Add a subscriber that calculates rolling averages (last 10 readings)."
- Files: aggregator.py
- Must subscribe to TemperatureReading
- Publish to AggregatedMetrics

### Phase 3: Add Alert System
"Add an alerting component. If temperature > 50°C, publish an Alert."
- Files: alert_monitor.py
- Subscribe to TemperatureReading
- Publish to SystemAlert (with content filter on subscriber)

### Phase 4: Add Second Sensor Type
"Add a pressure sensor to the same publisher. Use keyed instances."
- Modify: sensor_publisher.py (add pressure)
- Topics: TemperatureReading, PressureReading
- Must use instance lifecycle correctly

### Phase 5: Add Configuration Service
"Add a request/reply service to change sensor polling rate."
- Files: config_service.py
- Must affect sensor_publisher.py behavior
- Request: SetPollingRate, Reply: ConfigResult

### Phase 6: Add Historical Logger
"Add a component that logs all data to JSONL files with durability."
- Files: data_logger.py
- Must use TRANSIENT_LOCAL to catch late-joining data
- Subscribe to ALL topics (TemperatureReading, PressureReading, AggregatedMetrics, SystemAlert)

### Phase 7: Refactor QoS
"Move all QoS settings to external XML files."
- Files: qos_profiles.xml
- Modify ALL existing files to use the XML profiles
- Must not break any existing functionality

### Phase 8: Add Type Extension
"Extend TemperatureReading with 'location' and 'sensor_model' fields.
Existing components must still work."
- Modify sensor_publisher.py (use V2 type)
- All existing subscribers must continue to work
- Add new V2 subscriber that uses extended fields

## Verification

After each phase:
1. All tests from previous phases must still pass
2. New functionality must work
3. No regressions

## Metrics
- Tokens used per phase
- Cumulative tokens
- Time per phase
- Number of regressions introduced
- Files modified correctly vs incorrectly

## Expected Difficulty: L5 (Extreme)
- Estimated tokens: 200k-500k
- Estimated time: 30-60 minutes
- Expected iterations: 15-30

## Why This Tests Coherence
1. **Incremental complexity**: Each phase builds on previous
2. **Cross-file consistency**: Changes must propagate correctly
3. **Regression prevention**: Must not break existing code
4. **Context retention**: Must remember earlier decisions
5. **Type compatibility**: Must handle extensibility correctly


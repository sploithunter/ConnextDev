# Task: Content Filtered Topic Subscriber

## Critical Development Principle

**TEST EARLY, TEST OFTEN** - Run tests after every change.

## The Problem

A publisher sends sensor data from 100 sensors, each with varying values.
You only care about a subset: sensors with `id > 50` AND `value > 75.0`.

**Inefficient approach** (don't do this):
```python
for sample in reader.take():
    if sample.data["id"] > 50 and sample.data["value"] > 75.0:
        process(sample)  # Filter in YOUR code
```

This wastes bandwidth - you receive ALL samples, then discard most.

**Efficient approach** (do this):
Use ContentFilteredTopic - the filter is evaluated at the DDS level,
often on the publisher side, so non-matching samples are never sent.

## Your Task

Create `subscriber.py` that:
1. Creates a ContentFilteredTopic with filter: `id > 50 AND value > 75.0`
2. Subscribes using this filtered topic
3. Outputs received samples as JSONL
4. Uses async pattern (WaitSet)

## Type Definition

The publisher sends:
```python
sensor_type = dds.StructType("SensorReading")
sensor_type.add_member(dds.Member("id", dds.Int32Type()))
sensor_type.add_member(dds.Member("value", dds.Float64Type()))
sensor_type.add_member(dds.Member("timestamp", dds.Float64Type()))
```

## ContentFilteredTopic API

```python
import rti.connextdds as dds

# Create base topic first
topic = dds.DynamicData.Topic(participant, "SensorReadings", sensor_type)

# Create content filtered topic
cft = dds.DynamicData.ContentFilteredTopic(
    participant,
    "FilteredSensors",      # Name for filtered topic
    topic,                   # Base topic
    dds.Filter("id > 50 AND value > 75.0")  # SQL filter expression
)

# Create reader on the FILTERED topic
reader = dds.DynamicData.DataReader(subscriber, cft)
```

## Filter Expression Syntax

DDS uses SQL-like filter expressions:
- Comparison: `>`, `<`, `>=`, `<=`, `=`, `<>`
- Logical: `AND`, `OR`, `NOT`
- Field names match type members exactly

Examples:
- `"id > 50"` - sensor ID greater than 50
- `"value > 75.0"` - value greater than 75
- `"id > 50 AND value > 75.0"` - both conditions

## Output Format

JSONL to stdout (only matching samples):
```jsonl
{"id": 51, "value": 80.5, "timestamp": 1234567890.123}
{"id": 75, "value": 99.1, "timestamp": 1234567890.456}
```

## Command Line

```bash
python subscriber.py --count 100 --timeout 30
```

## Tools to Help You

### Verify Publisher is Sending

```bash
# See ALL samples (unfiltered)
dds-spy-wrapper --domain 0 --topic SensorReadings --duration 10

# Your subscriber should receive FEWER samples than spy shows
```

## Success Criteria

1. Uses ContentFilteredTopic (not application filtering)
2. Filter expression: `id > 50 AND value > 75.0`
3. Uses WaitSet pattern (async)
4. Only matching samples in output
5. No non-matching samples received

## Why This Matters

In real systems:
- Sensors may publish 1000+ samples/second
- Subscribers may only need a subset
- Network bandwidth is precious
- CFT filters at source, saving bandwidth

## Anti-Patterns (Don't Do)

```python
# BAD: Application-level filtering
for sample in reader.take():
    if sample.data["id"] > 50:  # DON'T filter here!
        process(sample)

# GOOD: DDS-level filtering
cft = dds.DynamicData.ContentFilteredTopic(...)  # Filter at DDS level
reader = dds.DynamicData.DataReader(subscriber, cft)
for sample in reader.take():
    process(sample)  # All samples already match!
```


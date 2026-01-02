# Help! I need to filter DDS data efficiently

I have a publisher sending sensor data from 100 sensors, and I only care about a few of them - specifically sensors with ID > 50 that have values > 75.

Right now I'm filtering in my application code, but my colleague said DDS can filter at the network level using something called "ContentFilteredTopic"? That sounds way more efficient.

## What I need

A `subscriber.py` that:
- Subscribes to the "SensorReadings" topic
- Uses DDS content filtering (not application filtering) 
- Only receives samples where `id > 50` AND `value > 75.0`
- Outputs received samples as JSONL
- Uses async pattern (WaitSet), not polling

## Data Type

The publisher sends:
```
SensorReading:
  - id (integer)
  - value (float64)  
  - timestamp (float64)
```

## Output

JSONL to stdout:
```
{"id": 51, "value": 80.5, "timestamp": 1234567890.123}
```

## What I know

- RTI Connext DDS Python API (`rti.connextdds`)
- DDS has SQL-like filter expressions
- There's a `dds-spy-wrapper` tool to verify data flow

## Development approach

**Test early, test often!** Run `python test_subscriber.py` after changes.

## Help me!

Can you create subscriber.py? I want to use the proper DDS way, not filter in my code.

# Task: Create a DDS HelloWorld Subscriber

## Critical Development Principle

**TEST EARLY, TEST OFTEN** - After every change, run `python test_subscriber.py` to verify your code works. Do not write large amounts of code without testing. Small, incremental changes with immediate testing will lead to success.

## Objective

Create `subscriber.py` that subscribes to the "HelloWorld" DDS topic and outputs received samples as JSONL to stdout.

## CRITICAL: Use Asynchronous Callbacks

**DO NOT use polling loops!** You MUST use either:
1. **WaitSet pattern** (preferred) - Wait for data condition, then take()
2. **Listener pattern** - on_data_available callback

**BAD - Polling (DO NOT DO THIS):**
```python
# WRONG - This is polling!
while True:
    samples = reader.take()
    time.sleep(0.1)
```

**GOOD - WaitSet pattern:**
```python
waitset = dds.WaitSet()
read_condition = dds.ReadCondition(reader, dds.DataState.any_data)
waitset.attach_condition(read_condition)

while running:
    active = waitset.wait(dds.Duration.from_seconds(1.0))
    if read_condition in active:
        for sample in reader.take():
            if sample.info.valid:
                process(sample.data)
```

## RTI Connext DDS Python API - Correct Usage

Use `rti.connextdds` with DynamicData:

```python
import rti.connextdds as dds

# Create type dynamically
hello_type = dds.StructType("HelloWorld")
hello_type.add_member(dds.Member("message", dds.StringType(256)))
hello_type.add_member(dds.Member("count", dds.Int32Type()))

# Create participant and topic
participant = dds.DomainParticipant(0)
topic = dds.DynamicData.Topic(participant, "HelloWorld", hello_type)

# Create subscriber and reader
subscriber = dds.Subscriber(participant)
reader = dds.DynamicData.DataReader(subscriber, topic)

# Access sample data
for sample in reader.take():
    if sample.info.valid:
        message = sample.data["message"]
        count = sample.data["count"]
```

## Output Format

Output each received sample as JSONL (one JSON object per line) to stdout:

```jsonl
{"message": "Hello, World!", "count": 1}
{"message": "Hello, World!", "count": 2}
```

## Requirements

1. Subscribe to topic "HelloWorld" on domain 0
2. Use asynchronous reception (WaitSet or listener)
3. Output samples as JSONL to stdout
4. Run until `--count` samples received or `--timeout` seconds
5. Handle SIGTERM gracefully

## Command Line Arguments

```bash
python subscriber.py --count 10 --timeout 30
```

- `--count`: Number of samples to receive (default: 10)
- `--timeout`: Max seconds to wait (default: 30)

## Test Your Code

After writing `subscriber.py`, run:

```bash
python test_subscriber.py
```

This will:
1. Check syntax
2. Verify imports work
3. Start the reference publisher
4. Run your subscriber
5. Verify output matches expected JSONL

## Remember

- TEST EARLY, TEST OFTEN
- Use WaitSet or listener - NO POLLING
- Output to stdout as JSONL
- Handle signals gracefully


# Task: Create Hello World DDS Publisher (Python)

You are creating a DDS publisher using RTI Connext DDS Python API.

**IMPORTANT**: 
- Generate a COMPLETE, RUNNABLE `publisher.py` file
- After each edit, a test will run automatically to verify your code
- If the test fails, you'll see the error and can fix it
- Keep iterating until the test passes

## Requirements

Create a file named `publisher.py` that:

1. **Topic**: Publishes to topic named `"HelloWorld"`
2. **Type Structure**:
   - `message` (string, max 256 chars)
   - `count` (int32)
3. **Behavior**:
   - Publish exactly **10 samples**
   - Rate: 2 Hz (0.5 seconds between samples)
   - Domain ID: **85** (fixed, do not change)
4. **Sample Values**:
   - `message`: `"Hello World {n}"` where n is 1-10
   - `count`: 1-10 (matching the sample number)

## ⚠️ CRITICAL: Complete Solution Required

**Generate the ENTIRE working publisher in one response.**

### Mental Verification Checklist (verify each step mentally before proceeding)

1. **Type definition**: Does it have `message` (string 256) and `count` (int32)?
2. **DomainParticipant**: Is domain ID exactly 85?
3. **Topic**: Is the name exactly "HelloWorld"?
4. **Publishing loop**: Does it publish exactly 10 samples?
5. **Sample values**: Is message `"Hello World {n}"` and count `n` for n=1-10?
6. **Timing**: 2s discovery wait, 0.5s between samples, 1s at end?

### Required Code Structure

Your `publisher.py` MUST include:
- Import statement
- Type creation function
- Main code that creates participant, topic, writer
- Loop publishing 10 samples with correct values
- Proper timing and waits

### Anti-Patterns (DO NOT DO)

- ❌ Generate only partial code
- ❌ Create just the type definition without the main logic
- ❌ Omit the publishing loop
- ❌ Use wrong domain ID (must be 85)

## Technical Requirements

- Use `rti.connextdds` Python API
- Use `DynamicData` (not IDL-generated types)
- Use `DomainParticipant`, `Publisher`, `DataWriter`
- Wait 2 seconds after startup for discovery before publishing
- Wait 1 second after last publish for reliable delivery

## RTI Connext DDS Python API Pattern

**IMPORTANT**: Use `dds.DynamicData.Topic` and `dds.DynamicData.DataWriter` patterns:

```python
import time
import rti.connextdds as dds

def create_hello_world_type():
    hello_type = dds.StructType("HelloWorld")
    hello_type.add_member(dds.Member("message", dds.StringType(256)))
    hello_type.add_member(dds.Member("count", dds.Int32Type()))
    return hello_type

# Example usage (you must implement the full logic):
participant = dds.DomainParticipant(85)
hello_type = create_hello_world_type()
topic = dds.DynamicData.Topic(participant, "HelloWorld", hello_type)  # Note: DynamicData.Topic
publisher = dds.Publisher(participant)
writer = dds.DynamicData.DataWriter(publisher, topic)  # Note: DynamicData.DataWriter

# Create and write sample
sample = dds.DynamicData(hello_type)
sample["message"] = "Hello World 1"
sample["count"] = 1
writer.write(sample)
```

**DO NOT USE**: `dds.Topic`, `dds.DataWriter`, or `DynamicDataTypeSupport` - these are wrong patterns.

## Tools to Help You Succeed

### `dds-spy-wrapper` - Universal Subscriber (Use This!)

Before the automated test runs, you can verify your publisher manually:

```bash
# Terminal 1: Run your publisher
python publisher.py

# Terminal 2: Verify with spy (no type definition needed!)
dds-spy-wrapper --domain 85 --duration 15
```

If the spy shows your samples → publisher is working!
If the spy shows nothing → debug your publisher first.

**The spy is a universal subscriber** - it can see ANY DDS data without needing
to know the type definition ahead of time. Use it to verify your code works!

### `dds-sample-compare` - Output Comparison

```bash
dds-sample-compare --actual output.jsonl --expected expected.jsonl
```

## Verification

Your publisher will be tested by:
1. Running a reference subscriber that captures output to JSONL
2. Comparing captured output against expected values
3. **All 10 samples must match exactly** (message and count values)

## Success Criteria

- [ ] Code runs without errors
- [ ] Publishes exactly 10 samples
- [ ] Topic name is "HelloWorld"
- [ ] Domain ID is 85
- [ ] Sample values match: `message="Hello World {n}"`, `count=n`


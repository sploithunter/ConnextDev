# Help me write a DDS subscriber

I need to create a subscriber that receives "HelloWorld" messages and prints them.

## What I need

A `subscriber.py` file that:
- Subscribes to the "HelloWorld" topic on domain 0
- The topic has two fields: `message` (string) and `count` (integer)
- Prints each received sample as JSON, one per line (JSONL format)
- Accepts `--count N` to receive N samples and `--timeout T` for max wait time
- Should NOT use busy-waiting/polling - use proper async DDS patterns

## Output format

Each sample should be printed as a single JSON line:
```
{"message": "Hello World 1", "count": 1}
{"message": "Hello World 2", "count": 2}
```

## What I know

- Using RTI Connext DDS Python API (`rti.connextdds`)
- I've heard DDS has WaitSet and Listener patterns for async data reception
- There's a `dds-spy-wrapper` tool in this project for testing - it can verify if data is on the wire

## Development approach

**Test early, test often!** Run `python test_subscriber.py` after each change.

## Create subscriber.py

Please write the complete subscriber. I'll test it with the reference publisher.

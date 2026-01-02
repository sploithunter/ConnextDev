# Help me write a DDS Hello World publisher

I'm new to RTI Connext DDS and need to create a simple publisher in Python.

## What I need

A `publisher.py` file that:
- Creates a "HelloWorld" topic with two fields: `message` (string, max 256 chars) and `count` (integer)
- Publishes 10 samples at 2 Hz (every 0.5 seconds)
- Each sample should have `message` = "Hello World 1", "Hello World 2", etc. and `count` = 1, 2, etc.
- Uses domain 85

## What I know

- I have RTI Connext DDS 7.x installed with the Python API (`rti.connextdds`)
- I've heard about DynamicData for creating types at runtime without IDL files
- The project has a tool called `dds-spy-wrapper` that can subscribe to any topic without needing type definitions - good for testing

## Development approach

**Test early, test often!** I want to verify my publisher works before moving on. Run `python test_publisher.py` after making changes.

## Help me get started!

Can you create the complete `publisher.py`? I'll test it with the spy wrapper to make sure it's working.

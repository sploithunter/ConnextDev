# QoS Challenge: Late Joiner Problem

## Critical Principle

**TEST EARLY, TEST OFTEN** - Run the test after each change.

## The Problem

You have a sensor data publisher and subscriber. In production, the startup order is **UNDEFINED** - either could start first.

**Current Bug**: When the subscriber starts AFTER the publisher has already sent data, it misses those samples.

```
Scenario 1 (works):     Scenario 2 (BROKEN):
  Sub starts              Pub starts
  Pub starts              Pub sends 5 samples
  Pub sends 10            Sub starts  ← misses first 5!
  Sub receives 10 ✓       Sub receives 5 ✗
```

## Your Task

Fix `publisher.py` and `subscriber.py` so the subscriber receives ALL samples regardless of startup order.

## Rules

1. **Use DDS QoS features** - This is what they're designed for
2. **Do NOT use sleep() hacks** - No timing workarounds
3. **Do NOT add startup synchronization** - Pretend you can't control startup order
4. **Both files may need changes** - QoS must match on both sides

## Files to Fix

### publisher.py (broken)

```python
# Current (BROKEN) QoS:
writer_qos.durability.kind = dds.DurabilityKind.VOLATILE  # <-- PROBLEM
writer_qos.reliability.kind = dds.ReliabilityKind.BEST_EFFORT  # <-- PROBLEM
```

### subscriber.py (broken)

```python
# Current (BROKEN) QoS:
reader_qos.durability.kind = dds.DurabilityKind.VOLATILE  # <-- PROBLEM
reader_qos.reliability.kind = dds.ReliabilityKind.BEST_EFFORT  # <-- PROBLEM
```

## Hints

Think about:
1. **Durability**: How does DDS store data for late joiners?
2. **Reliability**: How does DDS guarantee delivery?
3. **History**: How much data should be kept?

## DDS Durability Kinds

| Kind | Behavior |
|------|----------|
| VOLATILE | Data only sent to currently matched readers |
| TRANSIENT_LOCAL | Data stored in writer's cache for late joiners |
| TRANSIENT | Data survives writer restart (external storage) |
| PERSISTENT | Data survives system restart |

## Tools to Help You Debug

### `dds-spy-wrapper` - Verify Data Flow

Use the spy to understand what's happening:

```bash
# Terminal 1: Run publisher
python publisher.py --count 10

# Terminal 2: Watch with spy
dds-spy-wrapper --domain 0 --duration 30
```

**Key insight**: The spy uses VOLATILE durability by default.
If you start the spy AFTER the publisher finishes, and see NO samples,
that demonstrates the late joiner problem you need to fix!

Try this experiment:
1. Start spy first, then publisher → spy sees data
2. Start publisher first, then spy → spy sees nothing (with VOLATILE)

Your fix should make #2 work too (using durability).

## Testing

The test runs 5 times with random startup delays:

```bash
python test_durability.py
```

ALL 5 runs must receive 10/10 samples to pass.

## Expected Solution

After fixing, both publisher and subscriber should work correctly regardless of which starts first. The key is using appropriate durability and reliability QoS settings.

## Explain Your Fix

After implementing, briefly explain:
1. What QoS settings did you change?
2. Why does this fix the late joiner problem?


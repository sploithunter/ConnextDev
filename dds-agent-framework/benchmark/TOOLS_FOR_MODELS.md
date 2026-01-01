# DDS Development Tools - For AI Models

## Our Goal: Help You Succeed

This benchmark exists to find the **best path forward for DDS development**.
We want DDS coding to be easy. We want you to succeed.

**These tools exist to help you:**
- Catch problems early before they cascade
- Debug issues systematically
- Verify your code works incrementally

**Use these tools!** They are designed to make DDS coding easier.

---

---

## Available CLI Tools

### 1. `dds-spy-wrapper` - Universal Subscriber

**What it does**: Subscribes to ANY DDS topic without needing type definitions.
Use this to verify your publisher is working BEFORE writing a subscriber.

```bash
# Watch all topics on domain 0 for 10 seconds
dds-spy-wrapper --domain 0 --duration 10

# Output to JSONL file for comparison
dds-spy-wrapper --domain 0 --duration 10 --output samples.jsonl

# Watch specific topic
dds-spy-wrapper --domain 0 --topic HelloWorld --duration 10
```

**Use case**: You just wrote a publisher. Before writing a subscriber, verify it works:
```bash
# Terminal 1: Run your publisher
python publisher.py --count 10

# Terminal 2: Verify with spy (no type knowledge needed!)
dds-spy-wrapper --domain 0 --duration 15
```

If spy sees samples → your publisher is working!
If spy sees nothing → debug your publisher first.

---

### 2. `dds-sample-compare` - Output Verification

**What it does**: Compares actual DDS output to expected output.

```bash
dds-sample-compare --actual output.jsonl --expected expected.jsonl
```

**Use case**: Verify your implementation matches expected behavior.

---

### 3. `dds-test-harness` - Automated Testing

**What it does**: Runs publisher/subscriber pairs with verification.

```bash
dds-test-harness --config test_config.yaml
```

---

## Recommended Development Workflow

### For Publishers (Recommended Order)

```
1. Write publisher.py
2. Run publisher
3. Verify with dds-spy-wrapper   ← Catch problems here!
4. If spy sees data → publisher works
5. Only then write subscriber (if needed)
```

### For Subscribers

```
1. Use reference publisher (provided)
2. Write subscriber.py
3. Run both together
4. Compare output to expected
```

### Why This Workflow?

- **dds-spy-wrapper is universal** - no type definitions needed
- **Catch bugs early** - before writing more code
- **Isolate problems** - know which component is broken

---

## Common Issues and How Tools Help

| Problem | Tool to Use | How It Helps |
|---------|-------------|--------------|
| "Is my publisher sending data?" | `dds-spy-wrapper` | Shows all published samples |
| "Why isn't subscriber receiving?" | `dds-spy-wrapper` | Verify data is on the wire |
| "Do my samples match expected?" | `dds-sample-compare` | Diff actual vs expected |
| "Is it a QoS mismatch?" | `dds-spy-wrapper` | If spy sees data but sub doesn't → QoS issue |

---

## Quick Debugging Guide

### Publisher not working?
```bash
# 1. Run your publisher
python publisher.py

# 2. In another terminal, check if data appears
dds-spy-wrapper --domain 0 --duration 10

# If no data: Check type definition, topic name, domain ID
# If data appears: Publisher works! Issue is elsewhere
```

### Subscriber not receiving?
```bash
# 1. Verify publisher is sending (use spy)
dds-spy-wrapper --domain 0 --duration 10

# 2. If spy sees data but subscriber doesn't:
#    - Check QoS compatibility (RELIABLE vs BEST_EFFORT)
#    - Check durability (VOLATILE vs TRANSIENT_LOCAL)
#    - Check topic name matches exactly
#    - Check type definition matches exactly
```

### Late joiner issues?
```bash
# Use TRANSIENT_LOCAL durability on BOTH sides
# Verify with spy that data persists for late joiners
```

---

## Remember

1. **TEST EARLY, TEST OFTEN** - Run tests after every change
2. **Use the spy** - It's your best friend for debugging
3. **Verify incrementally** - Don't write everything before testing
4. **Tools exist to help you succeed** - Use them!


# SOLUTION - Development/Testing Only
# This file should NEVER be visible to models during actual benchmarking

## The Fix

Change BOTH publisher.py AND subscriber.py QoS from:
- VOLATILE → TRANSIENT_LOCAL
- BEST_EFFORT → RELIABLE

Also add KEEP_ALL history and extend publisher wait time.

## publisher.py Changes

Replace:
```python
writer_qos.durability.kind = dds.DurabilityKind.VOLATILE
writer_qos.reliability.kind = dds.ReliabilityKind.BEST_EFFORT
```

With:
```python
writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
```

And change the final sleep from 0.5 to 3.0 seconds.

## subscriber.py Changes

Replace:
```python
reader_qos.durability.kind = dds.DurabilityKind.VOLATILE
reader_qos.reliability.kind = dds.ReliabilityKind.BEST_EFFORT
```

With:
```python
reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
```

## Why This Works

1. TRANSIENT_LOCAL: Publisher keeps data in cache for late joiners
2. RELIABLE: Guarantees delivery with acknowledgment
3. KEEP_ALL: Preserves all samples in history
4. Extended wait: Gives late joiners time to receive cached data


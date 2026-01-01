# Phase 2: Add Data Aggregator

## Context
Phase 1 created a temperature publisher. Now add aggregation.

## Task
Create a subscriber that calculates rolling averages from the last 10 readings.

## Requirements

1. Create `aggregator.py`:
   - Subscribe to "TemperatureReading" topic
   - Keep a rolling window of last 10 readings per sensor
   - When window is full, calculate avg/min/max
   - Publish to "AggregatedMetrics" topic

2. Add to `types_v1.py`:
   - AggregatedMetrics type with: sensor_id, metric_type, avg_value, 
     min_value, max_value, sample_count, window_start_ms, window_end_ms

## Acceptance Criteria
- Run publisher and aggregator together
- Aggregator outputs metrics when window fills
- Both components cleanly shut down
- **Phase 1 still works unchanged**


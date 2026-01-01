# Scenario Development Log

Tracking iterations needed to complete each scenario.
This helps calibrate difficulty levels.

| Scenario | Description | Iterations | Time | Difficulty |
|----------|-------------|------------|------|------------|
| S1 | Multi-Topic Vehicle (3 topics, correlation) | 1 | ~5min | L2 |
| S2 | Keyed Instance Lifecycle (dispose/unregister) | 2 | ~10min | L3 |
| S3 | Content Filtered Topic (SQL filtering) | 1 | ~5min | L2 |
| S4 | Request/Reply Pattern (correlation, bidirectional) | 4 | ~15min | L3-L4 |
| S5 | Binary Protocol Bridge (4 msg types, full loop) | 1 | ~10min | L4 |
| S6 | Discovery + Built-in Topics (participant/topic discovery) | 5 | ~20min | L4 |
| S7 | Large Data Model (439 fields from JSON Schema) | 1 | ~15min | L4-L5 |
| S8 | Data Transformer (sub+pub, aggregation, unit conv) | 1 | ~10min | L3 |
| | | | | |

---

## Scenario 1: Multi-Topic Vehicle Telemetry ✅

**Goal**: Publisher sends 3 related topics (Position, Velocity, Status).
Subscriber correlates and outputs combined data.

**Result**: PASSED first iteration
**Files**: scenarios/S1_multi_topic_vehicle/reference/
**Key Features**:
- 3 DynamicData types
- 3 topics with shared vehicle_id
- WaitSet with multiple ReadConditions
- State correlation by vehicle_id

### Iteration Log
- Iteration 1: Created publisher with 3 topics ✅
- Iteration 1: Created subscriber with correlation ✅
- Test: 10/10 samples received with velocity/status correlation ✅

---

## Scenario 2: Keyed Instance Lifecycle ✅

**Goal**: Publisher manages multiple vehicle instances.
Subscriber tracks instance state (alive, disposed, not_alive).

**Result**: PASSED after 2 iterations
**Files**: scenarios/S2_keyed_instance_lifecycle/reference/
**Key Features**:
- register_instance, dispose_instance, unregister_instance APIs
- DataState with InstanceState.ANY
- Invalid sample handling for lifecycle events
- autodispose_unregistered_instances setting

### Iteration Log
- Iteration 1: Created publisher/subscriber, hit API error (dispose_instance signature)
- Iteration 2: Fixed API calls - only pass handle, not sample ✅
- Test: 22 samples + lifecycle event captured ✅

---

## Scenario 3: Content Filtered Topic ✅

**Goal**: Publisher sends many samples, subscriber filters to subset.
Test: SQL-like content filtering.

**Result**: PASSED first iteration
**Files**: scenarios/S3_content_filtered_topic/reference/
**Key Features**:
- ContentFilteredTopic with SQL filter expression
- dds.Filter with parameters (%0, %1, etc.)
- Reader on CFT instead of base topic
- Filter verification in subscriber

### Iteration Log
- Iteration 1: Created publisher with varying severity alerts ✅
- Iteration 1: Created subscriber with CFT for severity >= 3 ✅
- Test: 30 sent, 13 received (only HIGH/CRITICAL) ✅

---

## Scenario 4: Request/Reply Pattern ✅

**Goal**: Implement RPC-style request/reply over DDS.
Uses correlation ID for matching requests to replies.

**Result**: PASSED after 4 iterations
**Files**: scenarios/S4_request_reply/reference/
**Key Features**:
- Bidirectional communication (request + reply topics)
- UUID correlation IDs
- Error handling (division by zero, unknown op)
- Discovery synchronization (publication_matched_status, subscription_matched_status)
- Client ID filtering

### Iteration Log
- Iteration 1: Created service and client, only 2/6 requests worked ❌
- Iteration 2: Added delay between requests, still only 1/6 ❌
- Iteration 3: Added discovery wait with matched status, still 1/6 ❌
- Iteration 4: Removed CFT, used app-level filtering ✅

**Note**: ContentFilteredTopic on reply topic had issues. Application-level filtering more reliable.

---

## Scenario 5: Binary Protocol Bridge ✅

**Goal**: Bridge between raw binary protocol and DDS.
Inbound: Binary → DDS topics
Outbound: DDS topics → Binary

**Result**: PASSED first iteration!
**Files**: scenarios/S5_binary_bridge/reference/
**Key Features**:
- Custom binary protocol (TLV format) with 4 message types
- Inbound adapter: decode binary → publish to 4 DDS topics
- Outbound adapter: subscribe 4 topics → encode to binary
- Full loop test with comparison
- Multi-topic WaitSet processing

### Iteration Log
- Iteration 1: Created protocol.py (encode/decode, unit tested) ✅
- Iteration 1: Created inbound_adapter.py ✅
- Iteration 1: Created outbound_adapter.py ✅
- Iteration 1: Created run_bridge_test.py, 10/10 messages matched ✅

---

## Scenario 6: Discovery + Built-in Topics ✅

**Goal**: Use DDS built-in topics to discover publishers/subscribers.
Extract GUIDs, endpoints, and QoS from discovery data.

**Result**: PASSED after 5 iterations
**Files**: scenarios/S6_discovery_builtin_topics/reference/
**Key Features**:
- discovered_participants() API
- discovered_topics() API
- discovered_participant_data() for details
- Polling-based discovery monitoring
- JSONL output of discovery events

### Iteration Log
- Iteration 1: Used lookup_datareader (wrong method name) ❌
- Iteration 2: Used find_datareader_by_topic_name (unsupported for builtin) ❌
- Iteration 3: Switched to simpler discovery API (methods not properties) ❌
- Iteration 4: Fixed method calls with () ✅
- Iteration 5: Added error handling for inaccessible topic data ✅

**Note**: Topic data via discovered_topic_data() has limitations in Python API.
Use matched_subscription_data/matched_publication_data for full info.

---

---

## Scenario 7: Large Data Model ✅

**Goal**: Build pub/sub from non-DDS format (JSON Schema) with ~440 fields.
Tests context handling, type management, and attention to detail.

**Result**: PASSED first iteration!
**Files**: scenarios/S7_large_data_model/reference/
**Key Features**:
- JSON Schema with 439 fields (UAV telemetry)
- Schema converter: JSON Schema → DynamicData types
- Nested object flattening with underscore naming
- Realistic aerospace data: GPS, IMU, attitude, engines, batteries
- Full round-trip verification

### Iteration Log
- Iteration 1: Created schema generator (439 fields) ✅
- Iteration 1: Created schema converter ✅
- Iteration 1: Created publisher with realistic data generation ✅
- Iteration 1: Created subscriber, received 5/5 samples with 439 fields each ✅

**Test for models**: Can they handle very large type definitions and generate all fields correctly?

---

## Scenario 8: Data Transformer ✅

**Goal**: Application that is BOTH subscriber AND publisher.
Common pattern for gateways, aggregators, and data enrichers.

**Result**: PASSED first iteration!
**Files**: scenarios/S8_data_transformer/reference/
**Key Features**:
- Subscribes: SensorReadings (raw data)
- Publishes: ProcessedMetrics (aggregated data)
- Time-windowed aggregation (configurable window)
- Statistics: min, max, mean, stddev
- Unit conversion (Celsius→Fahrenheit, Pa→kPa)
- Alert level computation
- Quality tracking

### Iteration Log
- Iteration 1: Created transformer with aggregation logic ✅
- Iteration 1: Created sensor generator ✅
- Iteration 1: Created metrics consumer ✅
- Test: 40 readings → 15 aggregated metrics → 10 consumed ✅

**Test for models**: Can they build a single app that is both subscriber and publisher with business logic in between?

---

## Planned Scenarios

### S9: DDS-RPC (RTI Request-Reply)
Use RTI's built-in RPC pattern instead of manual request/reply.

### S10: C++ Interoperability
Python publisher → C++ subscriber (or vice versa).

### S11: Security (DDS Secure)
Configure authentication and encryption.

### S12: Network Discovery (Wireshark/RTPS)
Discover topics from raw network traffic.

---

## Summary

| Level | Description | Iterations Range |
|-------|-------------|-----------------|
| L1 | Basic Hello World | 1-2 |
| L2 | Single feature (CFT, multi-topic) | 1 |
| L3 | Multi-feature (lifecycle, transformer) | 1-2 |
| L4 | Complex (bridge, discovery, large model) | 1-5 |
| L5 | Extreme (network sniffing, C++ interop) | 5+ (estimated) |

### Key Observations
1. API familiarity matters: S2 and S4 took more iterations due to API differences
2. Complex patterns (S5, S7, S8) were surprisingly quick when patterns are known
3. Discovery APIs (S6) required most iteration due to Python API limitations
4. Large data models (S7) are tractable with systematic approach



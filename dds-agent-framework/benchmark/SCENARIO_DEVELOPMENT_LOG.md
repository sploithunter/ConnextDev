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

## Summary

| Level | Description | Iterations Range |
|-------|-------------|-----------------|
| L1 | Basic Hello World | 1-2 |
| L2 | Single feature (CFT, multi-topic) | 1 |
| L3 | Multi-feature (lifecycle, request/reply) | 2-4 |
| L4 | Complex (bridge, discovery) | 1-5 |
| L5 | Extreme (network sniffing, C++ interop) | 5+ (estimated) |



# DDS Benchmark Difficulty Levels

## Design Principle

For each level:
1. **I create a complete, verified pipeline first** (reference implementation)
2. **Remove one or more components** for the model to implement
3. **Deterministic verification** via the remaining reference components

## Level 1: Foundational (Expected Success: >95%)

### L1-PY-01: Hello World Publisher ✅
- Task: Create publisher for simple topic
- Reference: Subscriber provided
- Verification: Subscriber captures JSONL, compare with expected

### L1-PY-02: Hello World Subscriber ✅
- Task: Create subscriber using async callbacks
- Reference: Publisher provided
- Verification: Subscriber outputs JSONL, compare with expected
- **Key test**: Must use WaitSet or listener, NOT polling

## Level 2: Intermediate (Expected Success: 80-90%)

### L2-PY-01: Multi-Topic Publisher (TODO)
- Task: Create publisher for 3 related topics (Position, Velocity, Status)
- Reference: Multi-topic subscriber provided
- Verification: All topics captured, correct data relationships

### L2-PY-02: Multi-Topic Subscriber (TODO)
- Task: Create subscriber for 3 topics with correlation
- Reference: Multi-topic publisher provided
- Verification: Correct sample correlation, JSONL output

### L2-PY-03: QoS Configuration (TODO)
- Task: Configure specific QoS (RELIABLE + TRANSIENT_LOCAL)
- Reference: Publisher that requires QoS match
- Verification: Late-joiner subscriber receives history

## Level 3: Advanced (Expected Success: 50-70%)

### L3-PY-01: Binary Protocol → DDS Adapter (TODO)
- Task: Create adapter that reads binary messages, publishes to DDS
- Reference: Binary message generator + DDS subscriber
- Verification: DDS samples match binary input
- Input: Simple binary protocol (length-prefixed JSON)

### L3-PY-02: DDS → Binary Protocol Adapter (TODO)
- Task: Create adapter that subscribes to DDS, outputs binary
- Reference: DDS publisher + binary message validator
- Verification: Binary output matches DDS input

### L3-PY-03: Full Loop Adapter (TODO)
- Task: Create BOTH adapters for full loop test
- Reference: Binary input → DDS → Binary output verification
- Verification: Input binary == Output binary (through DDS)

## Level 4: Expert (Expected Success: 20-40%)

### L4-PY-01: Protocol Translation Gateway (TODO)
- Task: Translate between two different DDS type schemas
- Reference: Type A publisher, Type B subscriber expected
- Verification: Semantic equivalence maintained

### L4-PY-02: Content-Filtered Router (TODO)
- Task: Route DDS samples based on content filters
- Reference: Publisher with mixed content, filtered subscribers
- Verification: Correct routing based on filter expressions

## Level 5: Extreme (Expected Success: <20%)

### L5-PY-01: PCAP → MavLink → DDS Gateway (Future)
- Based on real STANAG 4586 work
- Task: Parse PCAP, extract MavLink, publish to DDS
- This is one "pinnacle" test

### L5-PY-02: Network Discovery → Build Subscriber (Future)

**Concept**: Discover an unknown DDS system from network traffic and build a subscriber.

**Difficulty Tiers**:

**Tier A (L4)**: Use RTI DDS Spy
- Given: Unknown publisher running on the network
- Task: Use `rtiddsspy` to discover topic name and type
- Build a subscriber that receives the data
- Tools: rtiddsspy (universal subscriber)

**Tier B (L5)**: Use Wireshark/tshark
- Given: Unknown DDS traffic captured as PCAP
- Task: Analyze RTPS protocol to discover:
  - Participant GUIDs
  - Topic names
  - Type definitions (from TypeObject/TypeInformation)
- Build subscriber that matches discovered type
- Tools: tshark, Wireshark RTPS dissector

**Tier C (L5+)**: Raw RTPS Analysis
- Given: RTPS packet capture
- Task: Parse RTPS protocol manually
  - Decode submessages (DATA, HEARTBEAT, etc.)
  - Extract serialized type information
  - Reconstruct DynamicType from wire format
- Build subscriber from scratch
- Tools: RTI RTPS Analyzer (internal), custom parsing

**Why This is Extreme**:
1. Requires understanding RTPS protocol
2. Type information may be encoded in TypeObject format
3. Must handle partial discovery (not all info in every packet)
4. Real-world scenario: debugging unknown DDS systems

**Potential Tools to Provide**:
- `dds-spy-wrapper` (already have)
- `rtps-capture`: Wrapper around tshark with RTPS filtering
- `rtps-type-extractor`: Extract TypeObject from PCAP
- RTI RTPS Analyzer (if available)

---

## Cross-Language Tasks

All cross-language tasks use Python as the "gold standard" reference.
Verification is always: Does target language interoperate with Python?

### Two Difficulty Tiers

| Tier | Prefix | Given | Difficulty |
|------|--------|-------|------------|
| **Translation** | LX- | Python source code | L3 (40-60%) |
| **Native** | LN- | Spec/requirements only | L4 (20-40%) |

---

## LX- Translation Tasks (L3)

Model is given working Python code to translate.

### LX-CPP-01: Python → C++ Publisher
- Given: Python publisher source + Python subscriber for testing
- Task: Translate to C++ Modern API
- Create: publisher.cxx, HelloWorld.idl, CMakeLists.txt

### LX-CPP-02: Python → C++ Subscriber  
- Given: Python subscriber source + Python publisher for testing
- Task: Translate to C++ with WaitSet/Listener
- Key test: Async pattern correctly translated

### LX-CS-01: Python → C# Publisher
### LX-CS-02: Python → C# Subscriber
### LX-JAVA-01: Python → Java Publisher
### LX-JAVA-02: Python → Java Subscriber

---

## LN- Native Tasks (L4) - NO SOURCE CODE PROVIDED

Model creates from scratch given only requirements.
This tests true language + DDS expertise.

### LN-CPP-01: Create C++ Publisher (No Python Source)
- Given: Type spec, topic name, QoS requirements, Python subscriber for testing
- NOT Given: Any source code to translate
- Task: Create C++ publisher from scratch
- Tests: C++ DDS API knowledge, build system, type definition

### LN-CPP-02: Create C++ Subscriber (No Python Source)
- Given: Type spec, Python publisher for testing
- NOT Given: Source code
- Task: Create C++ subscriber with async pattern

### LN-CS-01: Create C# Publisher (No Source)
### LN-CS-02: Create C# Subscriber (No Source)
### LN-JAVA-01: Create Java Publisher (No Source)
### LN-JAVA-02: Create Java Subscriber (No Source)

---

## Full Matrix

| Language | Translation (LX) | Native (LN) |
|----------|------------------|-------------|
| C++ | LX-CPP-01, LX-CPP-02 | LN-CPP-01, LN-CPP-02 |
| C# | LX-CS-01, LX-CS-02 | LN-CS-01, LN-CS-02 |
| Java | LX-JAVA-01, LX-JAVA-02 | LN-JAVA-01, LN-JAVA-02 |

Total: 12 tasks per language pair × (number of languages) = scalable test suite

---

## Expected Success Rates

| Task Type | Expected Success |
|-----------|------------------|
| LX Publisher (translation) | 50-70% |
| LX Subscriber (translation) | 40-60% |
| LN Publisher (native) | 30-50% |
| LN Subscriber (native) | 20-40% |

---

## Why This Architecture Works

1. **Python is always the gold standard**: I create verified Python implementations
2. **Deterministic verification**: Target language must interop with Python
3. **Difficulty scaling**: Translation (easier) → Native (harder)
4. **Minimal infrastructure**: One Python reference, many target language tests
5. **Real-world relevant**: Cross-language DDS is common in production
6. **Catches subtle bugs**: Type mismatches, QoS incompatibilities, endianness

---

## QoS Challenge Tasks (LQ-)

These tasks test DDS *understanding*, not just coding.
They represent common real-world mistakes developers make.

### Design Philosophy

1. Give model a scenario with a subtle QoS problem
2. Model must diagnose AND fix the issue
3. Tests understanding of DDS semantics, not just API syntax

---

### LQ-01: Late Joiner Problem (Durability)

**Scenario**: Publisher and subscriber start in undefined order.
Sometimes subscriber starts first, sometimes publisher.
Currently samples are being lost.

**Given**:
- Publisher using VOLATILE durability
- Subscriber that sometimes misses samples

**Task**: Fix the QoS so it works regardless of startup order

**Solution**: Use TRANSIENT_LOCAL on both sides + RELIABLE

**Why This Matters**: Extremely common production bug

---

### LQ-02: History Depth Overflow

**Scenario**: Publisher sends 1000 samples/second.
Subscriber processes at 100 samples/second.
Samples are being dropped.

**Given**:
- Publisher with KEEP_LAST(10)
- Slow subscriber

**Task**: Configure QoS to prevent sample loss

**Solution**: KEEP_ALL + RELIABLE, or increase depth + flow control

---

### LQ-03: QoS Mismatch Detection

**Scenario**: Publisher and subscriber exist but no data flows.
No errors shown.

**Given**:
- Publisher with RELIABLE
- Subscriber with BEST_EFFORT
- (Or other incompatible QoS combinations)

**Task**: Diagnose and fix the incompatibility

**Solution**: Match reliability policies; use QoS debugging

---

### LQ-04: Liveliness Timeout

**Scenario**: Subscriber detects publisher as "dead" even though
it's still running. Connection drops intermittently.

**Given**:
- Publisher with AUTOMATIC liveliness, 1 second lease
- Subscriber checking liveliness
- Publisher doing heavy computation (>1s between samples)

**Task**: Fix the configuration to maintain connection

**Solution**: Use MANUAL_BY_PARTICIPANT + assert_liveliness(), or increase lease

---

### LQ-05: Ownership Strength

**Scenario**: Two publishers for the same topic (redundancy).
Subscriber should only receive from the "primary".
Currently receiving from both.

**Given**:
- Two publishers, same topic
- Subscriber receiving duplicates

**Task**: Configure ownership so only highest-strength publisher is used

**Solution**: EXCLUSIVE ownership + ownership_strength QoS

---

### LQ-06: Content Filter Optimization

**Scenario**: Subscriber only needs samples where `id > 100`.
Currently receiving ALL samples and filtering in application.
Network bandwidth is wasted.

**Given**:
- Publisher sending all samples
- Subscriber filtering in code

**Task**: Move filter to DDS level to reduce bandwidth

**Solution**: ContentFilteredTopic with SQL expression

---

### LQ-07: Security Configuration

**Scenario**: System requires encrypted DDS communication.
Currently running without security.

**Given**:
- Working non-secure publisher/subscriber
- Security governance/permissions files

**Task**: Enable DDS Security with encryption

**Solution**: Configure security plugins, governance, permissions

---

### LQ-08: Deadline Violation Handling

**Scenario**: Publisher must send at least every 100ms.
Subscriber must receive at least every 100ms.
Need to detect and handle violations.

**Given**:
- Basic publisher/subscriber
- Requirement for 100ms deadline

**Task**: Configure deadline QoS and implement violation callbacks

**Solution**: Set deadline QoS + on_offered_deadline_missed / on_requested_deadline_missed

---

### Expected Success Rates

| Task | Difficulty | Expected Success |
|------|------------|------------------|
| LQ-01 (Durability) | L2 | 70-80% |
| LQ-02 (History) | L2 | 60-70% |
| LQ-03 (Mismatch) | L2 | 50-60% |
| LQ-04 (Liveliness) | L3 | 40-50% |
| LQ-05 (Ownership) | L3 | 30-40% |
| LQ-06 (Filter) | L3 | 40-50% |
| LQ-07 (Security) | L4 | 20-30% |
| LQ-08 (Deadline) | L3 | 40-50% |

---

### Why QoS Challenges are Valuable

1. **Real-world relevance**: These are actual production issues
2. **Tests understanding**: Can't just copy-paste, must understand DDS
3. **Configuration + Code**: Mix of QoS settings and callback implementation
4. **Debugging skills**: Some require diagnosis before fixing
5. **Stress test for models**: Configuration nuances challenge AI

---

## Token/Iteration Limits

To prevent runaway costs:

| Level | Max Iterations | Max Tokens (approx) | Timeout |
|-------|----------------|---------------------|---------|
| L1 | 10 | 50K | 5 min |
| L2 | 15 | 100K | 10 min |
| L3 | 20 | 200K | 20 min |
| L4 | 25 | 500K | 30 min |
| L5 | 30 | 1M | 60 min |

If a model hits limits without success → FAILED (resource exhausted)

---

## Advanced DDS Concepts (LD- Tasks)

These tasks test specific DDS features and patterns.

### LD-01: Content Filtered Topic (Subscriber)

**Concept**: Subscriber only receives samples matching a filter expression.
Filter is evaluated on the publisher side (saves bandwidth).

**Task**: Create subscriber with ContentFilteredTopic
- Filter: `id > 100 AND status = 'ACTIVE'`
- Verify only matching samples received

**Why Harder**: Requires understanding of SQL filter syntax, CFT creation

---

### LD-02: Dynamic Data vs IDL-Generated Types

**Concept**: Compare two approaches:
- DynamicData: Runtime type definition (what we've been using)
- IDL-generated: Compile-time types via rtiddsgen

**Task A (Dynamic)**: Create pub/sub using DynamicData
**Task B (IDL)**: Create pub/sub using rtiddsgen + generated code

**Why Important**: Real projects often use IDL for performance

---

### LD-03: RTI DDS Gen Workflow

**Concept**: Full rtiddsgen workflow from IDL to working code

**Task**:
1. Write HelloWorld.idl
2. Run: `rtiddsgen -language python -d gen HelloWorld.idl`
3. Create publisher using generated types
4. Create subscriber using generated types

**Why Harder**: Multi-step workflow, understanding generated code structure

---

### LD-04: Instance Lifecycle (Keyed Topics)

**Concept**: DDS instances identified by key fields.
Each unique key = separate instance with own lifecycle.

**Task**: Create keyed topic publisher/subscriber
- Key field: `sensor_id`
- Handle: register_instance, dispose, unregister
- Subscriber must track instance state

**Why Harder**: Instance management is complex but critical for real systems

---

### LD-05: Request-Reply Pattern

**Concept**: Synchronous request-reply over DDS (not just pub-sub)

**Task**: Implement simple calculator service
- Request: `{operation: "add", a: 5, b: 3}`
- Reply: `{result: 8}`
- Use correlation IDs

**Why Harder**: Bidirectional, correlation, timeouts

---

### LD-06: Waitset with Multiple Conditions

**Concept**: Single WaitSet monitoring multiple conditions

**Task**: Create subscriber that waits for:
- Data on topic A
- Data on topic B  
- Status change condition
- Guard condition (for shutdown)

**Why Harder**: Complex async coordination

---

### LD-07: Discovery GUID Mining ✅

**Concept**: Discover GUIDs of remote entities using the API

**Task A (L3)**: Subscriber gets Publisher's GUID
- Use `sample.info.publication_handle`
- Use `reader.matched_publication_data(handle)`
- Relatively straightforward

**Task B (L4)**: Publisher gets Subscriber's GUIDs
- Subscribe to DCPSSubscription built-in topic
- Filter for subscribers to your topic
- Extract their GUIDs
- Much harder - requires understanding of DDS discovery

**Why Important**: Debugging, security, monitoring, failover detection

---

## Task Balance Matrix

Ensuring equal coverage of publishers and subscribers:

| Level | Publisher Tasks | Subscriber Tasks | Both/Other |
|-------|-----------------|------------------|------------|
| L1 | L1-PY-01 ✅ | L1-PY-02 ✅ | - |
| L2 | L2-PY-01 | L2-PY-02 | LQ-01 ✅ |
| L3 | L3-PY-01 | L3-PY-02 | L3-PY-03 ✅ |
| LX | LX-CPP-01 ✅ | LX-CPP-02 | - |
| LN | LN-CPP-01 ✅ | LN-CPP-02 | - |
| LD | LD-03 (pub) | LD-01, LD-04, LD-06 | LD-02, LD-05 |

### Subscriber-Specific Challenges

Subscribers are often HARDER because:

1. **Async patterns required**: WaitSet, Listener, ReadCondition
2. **State management**: Track what's been read vs unread
3. **Instance lifecycle**: Handle dispose, unregister
4. **Content filtering**: SQL expression syntax
5. **Multi-topic correlation**: Join data from multiple topics
6. **Error handling**: on_subscription_matched, on_sample_lost

### Publisher-Specific Challenges

1. **Flow control**: Don't overwhelm slow subscribers
2. **Instance management**: register/dispose/unregister
3. **Liveliness assertion**: Manual liveliness patterns
4. **Coherent updates**: Atomic multi-sample writes

---

## Implementation Priority (Updated)

### Phase 1: Core Balance ✅
- [x] L1-PY-01: Publisher
- [x] L1-PY-02: Subscriber

### Phase 2: QoS Understanding
- [x] LQ-01: Late Joiner
- [ ] LQ-02: History Depth
- [ ] LQ-03: QoS Mismatch

### Phase 3: Advanced Subscriber
- [ ] LD-01: Content Filtered Topic
- [ ] LD-04: Instance Lifecycle
- [ ] LD-06: Multi-Condition WaitSet

### Phase 4: IDL/CodeGen
- [ ] LD-03: RTI DDS Gen Workflow

### Phase 5: Cross-Language
- [x] LX-CPP-01: Python→C++ Publisher
- [ ] LX-CPP-02: Python→C++ Subscriber
- [x] LN-CPP-01: Native C++ Publisher
- [ ] LN-CPP-02: Native C++ Subscriber

### Phase 6: Extreme Tests (Future)
- [ ] L5-PY-01: PCAP → MavLink → DDS Gateway
- [ ] L5-PY-02a: Network Discovery via rtiddsspy
- [ ] L5-PY-02b: Network Discovery via Wireshark
- [ ] L5-PY-02c: Raw RTPS Protocol Analysis

---

## Future Tooling Needs

For extreme tests, we may need additional tools:

| Tool | Purpose | Status |
|------|---------|--------|
| `dds-spy-wrapper` | Universal subscriber | ✅ Implemented |
| `rtps-capture` | Capture RTPS traffic via tshark | TODO |
| `rtps-type-extractor` | Extract TypeObject from PCAP | TODO |
| `rtps-dissector` | Parse RTPS submessages | TODO |
| RTI RTPS Analyzer | Full RTPS analysis (RTI internal) | External |

### Wireshark Integration

Wireshark has built-in RTPS protocol dissection:

```bash
# Capture DDS traffic on port 7400-7500
tshark -i en0 -f "udp portrange 7400-7500" -w dds_capture.pcap

# Analyze RTPS traffic
tshark -r dds_capture.pcap -Y "rtps" -T fields \
  -e rtps.guid_prefix -e rtps.entity_id -e rtps.topic_name

# Extract type information (if present)
tshark -r dds_capture.pcap -Y "rtps.param.type_name" -T fields \
  -e rtps.param.type_name
```

These tools would enable L5-level tests where models must:
1. Capture/analyze network traffic
2. Discover DDS entities and types
3. Build compatible applications from wire format


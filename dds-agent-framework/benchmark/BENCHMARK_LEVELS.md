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

### L1-PY-02: Hello World Subscriber (TODO)
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
- This is the "pinnacle" test

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

## Next Implementation Priority

1. **L1-PY-02**: Subscriber task (tests async callback requirement)
2. **L3-PY-01**: Binary → DDS (first "real" adapter task)
3. **L3-PY-03**: Full loop (complete pipeline)


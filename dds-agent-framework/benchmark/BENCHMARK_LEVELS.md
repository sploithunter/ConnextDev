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


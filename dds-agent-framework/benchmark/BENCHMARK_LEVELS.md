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


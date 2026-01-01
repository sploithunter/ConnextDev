# DDS Agent Development Framework Plan

## Executive Summary

This plan outlines a framework for AI-assisted development of DDS publishers and subscribers. Based on lessons learned from the STANAG 4586 adapter project, we propose a development pipeline that leverages RTI DDS Spy as a universal subscriber for debugging, combined with automated testing infrastructure and agent supervision to enable junior teams to develop reliable DDS applications with AI assistance.

**Key Insight**: RTI DDS Spy is a universal subscriber that can capture and display any DDS data without compile-time knowledge of types. This makes it an ideal debugging tool for a "write publisher first, verify, then write subscriber" development pattern.

---

## 1. Development Pipeline Architecture

### 1.1 Three-Phase Development Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DDS DEVELOPMENT PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────────┘

Phase 1: Publisher Development (Verified by Universal Subscriber)
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────────┐         ┌─────────────────┐         ┌──────────────────┐
    │   Your       │   DDS   │  RTI DDS Spy    │  Text   │  Validation      │
    │   Publisher  │ ──────► │  (Universal     │ ──────► │  Framework       │
    │   (WIP)      │         │   Subscriber)   │         │  (Automated)     │
    └──────────────┘         └─────────────────┘         └──────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  Captured       │
                            │  Samples        │
                            │  (JSONL/Text)   │
                            └─────────────────┘

Phase 2: Subscriber Development (Fed by Verified Publisher)
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────────┐         ┌─────────────────┐         ┌──────────────────┐
    │  Verified    │   DDS   │   Your          │  Output │  Validation      │
    │  Publisher   │ ──────► │   Subscriber    │ ──────► │  Framework       │
    │  (Phase 1)   │         │   (WIP)         │         │  (Automated)     │
    └──────────────┘         └─────────────────┘         └──────────────────┘

Phase 3: Full Loop Verification
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────────┐         ┌─────────────────┐         ┌──────────────────┐
    │  Test Input  │   DDS   │   Publisher     │   DDS   │   Subscriber     │
    │  Data        │ ──────► │   (Verified)    │ ──────► │   (Verified)     │
    └──────────────┘         └─────────────────┘         └──────────────────┘
           │                                                      │
           │                  ┌─────────────────┐                 │
           └─────────────────►│   Comparator    │◄────────────────┘
                              │   (100% Match)  │
                              └─────────────────┘
```

### 1.2 Why This Pattern Works

1. **Universal Debugging**: RTI DDS Spy requires no code changes to subscribe to any topic
2. **Incremental Verification**: Each component is verified before building the next
3. **Clear Contracts**: DDS types serve as the interface specification
4. **Automated Testing**: Text output can be parsed and validated programmatically
5. **Language Agnostic**: Publishers and subscribers can be in different languages

---

## 2. Required Tools and Components

### 2.1 Core Tools

| Tool | Purpose | Priority |
|------|---------|----------|
| **dds-spy-wrapper** | Wraps rtiddsspy with structured output (JSON/JSONL) | P0 |
| **dds-sample-capture** | Captures DDS samples to files for comparison | P0 |
| **dds-sample-compare** | Compares captured samples with expected values | P0 |
| **dds-process-monitor** | Monitors DDS processes with timeout detection | P0 |
| **dds-port-allocator** | Allocates available ports and domain IDs | P1 |
| **dds-type-validator** | Validates DynamicData against IDL schemas | P1 |
| **dds-test-harness** | Orchestrates multi-process testing | P1 |

### 2.2 Tool Specifications

#### 2.2.1 dds-spy-wrapper

```bash
# Usage
dds-spy-wrapper --domain 222 --topics "Vehicle_*" --format jsonl --output samples.jsonl --timeout 30

# Features
- Parses rtiddsspy printSample output into structured JSON
- Handles library path issues (DYLD_LIBRARY_PATH on macOS, LD_LIBRARY_PATH on Linux)
- Configurable timeout to prevent hangs
- Filters by topic name patterns
- Outputs JSONL for streaming processing
```

**Implementation Notes**:
- RTI DDS Spy outputs human-readable text that needs parsing
- Common failure: library not found errors on macOS due to SIP
- Solution: Bundle as shell script that sets up environment correctly

#### 2.2.2 dds-process-monitor

```python
# Pseudocode
class DDSProcessMonitor:
    def __init__(self, timeout_seconds: int = 60):
        self.processes = {}
        self.timeout = timeout_seconds
        
    def start_process(self, name: str, command: List[str]) -> ProcessHandle:
        """Start a process with automatic timeout monitoring."""
        
    def check_health(self) -> Dict[str, ProcessStatus]:
        """Check all processes for hangs, crashes, output."""
        
    def kill_hung_processes(self) -> List[str]:
        """Terminate processes that have exceeded timeout."""
        
    def get_output(self, name: str) -> str:
        """Get stdout/stderr from a process."""
```

**Critical for Agent Automation**:
- Agents cannot observe real-time terminal output
- Processes that hang block the agent indefinitely
- Need automatic detection and termination

#### 2.2.3 dds-port-allocator

```python
# Features needed
- Check port availability before allocation (lsof/netstat)
- Allocate non-conflicting domain IDs (avoid high IDs that cause RTPS port issues)
- Clean up stale DDS processes from previous runs
- Reserve port ranges for specific test configurations
```

### 2.3 Configuration-Driven Testing

Based on our `adapter_config.yaml` pattern:

```yaml
# dds_test_config.yaml
publishers:
  vehicle_telemetry:
    description: "Publishes Vehicle_Kinematics samples"
    implementations:
      python:
        command: ["python", "-m", "publishers.vehicle_telemetry"]
        args: ["--domain", "{DOMAIN_ID}", "--rate", "10"]
      cpp:
        command: ["./build/vehicle_telemetry_pub"]
        args: ["--domain", "{DOMAIN_ID}"]
    expected_output:
      topic: "Vehicle_Kinematics"
      rate_hz: 10
      schema: "schemas/vehicle_kinematics.json"

subscribers:
  vehicle_monitor:
    description: "Subscribes to Vehicle_Kinematics"
    implementations:
      python:
        command: ["python", "-m", "subscribers.vehicle_monitor"]
        args: ["--domain", "{DOMAIN_ID}", "--output", "{OUTPUT_FILE}"]

test_configs:
  publisher_only:
    description: "Test publisher with rtiddsspy"
    publisher: vehicle_telemetry
    subscriber: rtiddsspy  # Built-in universal subscriber
    duration: 10
    validation:
      min_samples: 100
      schema_check: true
      
  full_loop:
    description: "Full publisher-subscriber loop test"
    publisher: vehicle_telemetry
    subscriber: vehicle_monitor
    duration: 10
    validation:
      content_match: 1.0  # 100% match required
      float_tolerance: 0.001
```

---

## 3. Agent Framework Integration

### 3.1 IDE Integration Points

#### Cursor / VS Code

```json
// .cursor/rules
{
  "dds_development": {
    "tools": [
      "dds-spy-wrapper",
      "dds-sample-capture", 
      "dds-process-monitor"
    ],
    "prompts": {
      "new_publisher": "prompts/create_publisher.md",
      "new_subscriber": "prompts/create_subscriber.md",
      "debug_type_mismatch": "prompts/debug_types.md"
    },
    "templates": {
      "cpp_publisher": "templates/cpp_publisher.cxx",
      "python_subscriber": "templates/python_subscriber.py"
    }
  }
}
```

#### MCP (Model Context Protocol) Tools

```typescript
// MCP tool definitions for DDS development
const tools = [
  {
    name: "dds_start_spy",
    description: "Start RTI DDS Spy to capture samples on specified domain/topics",
    parameters: {
      domain_id: { type: "integer", required: true },
      topic_filter: { type: "string", default: "*" },
      timeout: { type: "integer", default: 30 }
    }
  },
  {
    name: "dds_run_test",
    description: "Run a DDS test configuration with automatic timeout",
    parameters: {
      config_name: { type: "string", required: true },
      timeout: { type: "integer", default: 60 }
    }
  },
  {
    name: "dds_check_processes",
    description: "Check for running DDS processes and potential conflicts",
    parameters: {}
  },
  {
    name: "dds_cleanup",
    description: "Kill hung DDS processes and free ports",
    parameters: {
      domain_id: { type: "integer" }
    }
  }
];
```

### 3.2 Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│   Development Agent  │     │   Supervisor Agent   │     │   Test Agent     │
│   (Claude/GPT)       │     │   (Watchdog)         │     │   (Validation)   │
│                      │     │                      │     │                  │
│ - Writes code        │     │ - Monitors processes │     │ - Runs tests     │
│ - Debugs issues      │     │ - Detects hangs      │     │ - Compares output│
│ - Reads docs         │     │ - Kills stuck procs  │     │ - Reports results│
│                      │     │ - Alerts dev agent   │     │                  │
└──────────┬───────────┘     └──────────┬───────────┘     └────────┬─────────┘
           │                            │                          │
           └────────────────────────────┼──────────────────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   Shared State        │
                            │   - Process registry  │
                            │   - Port allocations  │
                            │   - Test results      │
                            │   - Error logs        │
                            └───────────────────────┘
```

### 3.3 Supervisor Agent Specification

The Supervisor Agent addresses the critical issue we encountered: **commands that hang indefinitely**.

```python
class SupervisorAgent:
    """
    Monitors development processes and intervenes when needed.
    
    Key responsibilities:
    1. Track all spawned processes with start times
    2. Monitor stdout/stderr for error patterns
    3. Detect hung processes (no output + timeout exceeded)
    4. Terminate hung processes and notify development agent
    5. Clean up resources (ports, domain participants)
    """
    
    def __init__(self):
        self.process_registry = {}
        self.default_timeout = 60  # seconds
        self.error_patterns = [
            r"ERROR.*library",
            r"Segmentation fault",
            r"SIGKILL",
            r"Address already in use",
            r"DDS_DynamicData.*cannot be mapped",
        ]
    
    async def monitor_loop(self):
        """Main monitoring loop - runs continuously."""
        while True:
            for proc_id, proc_info in self.process_registry.items():
                # Check for timeout
                if self._is_hung(proc_info):
                    await self._handle_hung_process(proc_id)
                
                # Check for error patterns
                errors = self._check_output_for_errors(proc_info)
                if errors:
                    await self._notify_development_agent(proc_id, errors)
            
            await asyncio.sleep(1)
    
    async def _handle_hung_process(self, proc_id: str):
        """Handle a hung process."""
        proc_info = self.process_registry[proc_id]
        
        # Terminate the process
        proc_info['process'].terminate()
        
        # Notify development agent
        await self._notify_development_agent(
            proc_id,
            f"Process '{proc_id}' hung after {proc_info['timeout']}s. "
            f"Last output: {proc_info['last_output'][-500:]}"
        )
        
        # Clean up resources
        await self._cleanup_resources(proc_info)
```

### 3.4 Error Pattern Recognition

Based on our experience, common DDS development errors that agents should recognize:

| Error Pattern | Meaning | Suggested Action |
|---------------|---------|------------------|
| `DDS_DynamicData.*cannot be mapped` | Type mismatch | Check IDL types vs code types |
| `member with member id X bound` | Multiple loans active | Return loans before new loan |
| `library not found` | Missing DDS libraries | Set DYLD_LIBRARY_PATH/LD_LIBRARY_PATH |
| `Address already in use` | Port conflict | Kill previous processes, use port allocator |
| `TypeCode not available` | Type not registered | Load QoS file with type definitions |
| `Domain ID too high` | RTPS port overflow | Use domain ID < 100 |

---

## 4. Lessons Learned from STANAG Project

### 4.1 What Worked Well

| Practice | Benefit | Recommendation |
|----------|---------|----------------|
| JSONL output for validation | Easy parsing, line-by-line comparison | Standardize across all tools |
| Content hashing | Finds mismatches regardless of order | Include in comparison framework |
| Separated processes | Clear network boundaries, language agnostic | Enforce as architecture pattern |
| Configuration-driven tests | Easy to add new test cases | Use YAML-based config |
| Incremental testing | Find issues early | Test each component before integration |

### 4.2 What Caused Problems

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Hanging commands** | Blocked agent indefinitely | Supervisor agent with timeouts |
| **rtiddsspy library issues** | Couldn't use for debugging | Pre-configured wrapper scripts |
| **Type mismatches (int32/uint32)** | Runtime errors, silent data corruption | Type validation tool |
| **Loan pattern complexity** | "Member already bound" errors | Documentation + examples |
| **Domain ID conflicts** | Data feedback loops | Domain ID allocator |
| **Port conflicts** | "Address in use" errors | Port availability checker |
| **Float precision differences** | False test failures | Configurable tolerance |

### 4.3 Development Time Analysis

From our C++ adapter development (1,563 lines, ~4 hours with AI assistance):

| Task | Time (Human) | Time (AI-Assisted) | Speedup |
|------|--------------|-------------------|---------|
| Understanding DDS API | 8-16 hours | 1-2 hours | 8x |
| Initial implementation | 16-24 hours | 1-2 hours | 12x |
| Debugging type mismatches | 8-16 hours | 1 hour | 12x |
| Testing and validation | 8-16 hours | 0.5 hours | 20x |
| **Total** | **40-72 hours** | **~4 hours** | **10-18x** |

**Key Insight**: Most speedup comes from rapid iteration and pattern recognition that AI excels at.

---

## 5. Implementation Roadmap

### Phase 1: Core Tools (Week 1-2)

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| dds-spy-wrapper | Shell script + Python parser for rtiddsspy output | P0 |
| dds-process-monitor | Python class for process lifecycle management | P0 |
| dds-sample-compare | Enhanced version of compare_samples.py | P0 |
| Basic test harness | Config-driven test runner | P0 |

### Phase 2: Agent Integration (Week 3-4)

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| Supervisor agent | Watchdog process with timeout detection | P0 |
| MCP tool definitions | Tool schemas for IDE integration | P1 |
| Cursor rules file | Prompts and configuration for Cursor | P1 |
| Error pattern database | Common errors and remediation | P1 |

### Phase 3: Templates and Documentation (Week 5-6)

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| C++ publisher template | Boilerplate with DynamicData best practices | P1 |
| Python subscriber template | Boilerplate with async patterns | P1 |
| DDS development guide | Loan pattern, type mappings, debugging | P1 |
| Agent prompt library | Tested prompts for common tasks | P2 |

### Phase 4: Advanced Features (Week 7-8)

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| Type validation tool | Validates code against IDL at development time | P2 |
| Performance profiler | Measures latency, throughput | P2 |
| Multi-language test harness | C++, Python, Rust in same test | P2 |
| CI/CD integration | GitHub Actions / GitLab CI templates | P2 |

---

## 6. Success Criteria

### 6.1 Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Junior developer productivity | 5x improvement | Time to first working publisher |
| Test automation coverage | 100% | All DDS types have automated tests |
| Hung process detection | < 5 seconds | Time from hang to termination |
| False positive rate | < 1% | Test failures due to framework issues |

### 6.2 Qualitative Goals

1. **Junior developers can create DDS publishers without DDS expertise**
   - Clear templates with documented patterns
   - AI assistance for debugging
   - Automated validation

2. **Agents can develop DDS code autonomously**
   - Timeout handling prevents infinite blocks
   - Error patterns trigger appropriate remediation
   - Full loop testing verifies correctness

3. **Framework is language-agnostic**
   - Same test harness works for C++, Python, Rust, etc.
   - DDS serves as the universal contract

---

## 7. File Structure

```
dds-agent-framework/
├── README.md
├── requirements.txt
│
├── tools/
│   ├── dds_spy_wrapper.py
│   ├── dds_spy_wrapper.sh
│   ├── dds_process_monitor.py
│   ├── dds_sample_capture.py
│   ├── dds_sample_compare.py
│   ├── dds_port_allocator.py
│   └── dds_type_validator.py
│
├── agents/
│   ├── supervisor_agent.py
│   ├── test_agent.py
│   └── error_patterns.yaml
│
├── templates/
│   ├── cpp/
│   │   ├── publisher_template.cxx
│   │   ├── subscriber_template.cxx
│   │   └── CMakeLists.txt.template
│   └── python/
│       ├── publisher_template.py
│       └── subscriber_template.py
│
├── prompts/
│   ├── create_publisher.md
│   ├── create_subscriber.md
│   ├── debug_type_mismatch.md
│   └── full_loop_test.md
│
├── config/
│   ├── cursor_rules.json
│   ├── mcp_tools.json
│   └── error_patterns.yaml
│
├── examples/
│   ├── vehicle_telemetry/
│   │   ├── publisher.py
│   │   ├── subscriber.py
│   │   └── test_config.yaml
│   └── hello_world/
│       ├── publisher.cxx
│       └── subscriber.cxx
│
└── tests/
    ├── test_spy_wrapper.py
    ├── test_process_monitor.py
    └── test_sample_compare.py
```

---

## 8. Appendix: Agent Prompts

### 8.1 Create Publisher Prompt

```markdown
# Create DDS Publisher

You are developing a DDS publisher. Follow this process:

1. **Understand the data model**
   - Read the IDL/XML type definitions
   - Identify key fields and their types (float32 vs float64, int16 vs int32)
   
2. **Use the template**
   - Start from templates/cpp/publisher_template.cxx or templates/python/publisher_template.py
   - Fill in topic name, type name, and field population

3. **Test with rtiddsspy**
   - Run: dds-spy-wrapper --domain {DOMAIN_ID} --topics "{TOPIC_NAME}" --timeout 10
   - Verify samples appear with correct values

4. **Common issues**:
   - If "library not found": Check NDDSHOME and library paths
   - If "type mismatch": Verify IDL types match your code
   - If no output: Check domain ID matches, topic name is correct

5. **Validation**
   - Use dds-sample-compare to verify output against expected values
   - All fields must match within tolerance
```

### 8.2 Debug Type Mismatch Prompt

```markdown
# Debug DDS Type Mismatch

You are seeing a DDS type mismatch error like:
`ERROR DDS_DynamicData2_checkMemberTypeToGet: Value of type (DDS_TK_LONG) cannot be mapped into a value of type (DDS_TK_ULONG)`

Follow this process:

1. **Identify the field**
   - The error occurs when accessing a specific field
   - Add debug output before each field access to find which one

2. **Check the IDL**
   - Look up the field in the XML/IDL type definition
   - Common types: int16, int32, uint32, float32, float64

3. **Map to C++/Python types**
   | IDL Type | C++ Type | Python Type |
   |----------|----------|-------------|
   | int16 | int16_t | int |
   | int32 | int32_t | int |
   | uint32 | uint32_t | int |
   | float32 | float | float |
   | float64 | double | float |

4. **Fix the code**
   - Change `value<uint32_t>()` to `value<int32_t>()` if IDL says int32
   - Cast the result if needed: `static_cast<uint32_t>(sample.value<int32_t>("field"))`
```

---

## 9. AI Model Benchmarking for DDS Programming

### 9.1 Purpose

This framework can serve as a **standardized benchmark for evaluating AI model capabilities in DDS/middleware programming**. Based on empirical observations from the STANAG 4586 project, we can create a progression of tasks that reveal model strengths and weaknesses in systems programming.

### 9.2 Empirical Observations from STANAG Project

| Task | Language | Result | Time | Notes |
|------|----------|--------|------|-------|
| Python STANAG adapter | Python | ✓ Success | ~45 min | Smooth, few iterations |
| C++ Routing Service adapter | C++ | ✗ Failed | ~2 hours | Configuration complexity, library issues |
| C++ Standalone adapter | C++ | ✓ Success | ~1.25 hours | Required multiple debug cycles |
| Type mismatch debugging | C++ | ✓ Success | ~30 min | Pattern recognition worked well |
| Process timeout issues | All | ✗ Required intervention | N/A | Model cannot observe real-time output |

**Key Findings**:
- **Python >> C++** in terms of model success rate and speed
- **Compile-time types > DynamicData** for model comprehension
- **Framework/plugin architectures** (Routing Service) are extremely difficult
- **Debugging existing code** is often faster than writing new code
- **Hanging processes** are a critical failure mode for autonomous agents

### 9.3 Benchmark Task Categories

#### Level 1: Foundational (Success Expected: >95%)

| Task ID | Description | Language | Key Challenge | Expected Time |
|---------|-------------|----------|---------------|---------------|
| L1-PY-01 | Hello World Publisher (compile-time types) | Python | Basic API | 5-10 min |
| L1-PY-02 | Hello World Subscriber | Python | Callback handling | 5-10 min |
| L1-PY-03 | Simple Pub/Sub Loop Test | Python | Process coordination | 10-15 min |
| L1-CPP-01 | Hello World Publisher (IDL-generated) | C++ | CMake setup, includes | 15-20 min |
| L1-CPP-02 | Hello World Subscriber | C++ | Listener pattern | 15-20 min |

**Pass Criteria**: Code compiles/runs, data is exchanged, no manual intervention required.

#### Level 2: Intermediate (Success Expected: 80-90%)

| Task ID | Description | Language | Key Challenge | Expected Time |
|---------|-------------|----------|---------------|---------------|
| L2-PY-01 | DynamicData Publisher | Python | Runtime type access | 15-20 min |
| L2-PY-02 | Multi-topic Publisher | Python | Multiple writers | 20-30 min |
| L2-PY-03 | QoS Configuration (Reliable, History) | Python | XML QoS profiles | 20-30 min |
| L2-CPP-01 | DynamicData Publisher | C++ | Type API differences | 30-45 min |
| L2-CPP-02 | WaitSet-based Subscriber | C++ | Async patterns | 30-45 min |
| L2-MIX-01 | Python Publisher → C++ Subscriber | Mixed | Interop, type matching | 30-45 min |

**Pass Criteria**: Correct data values, proper QoS behavior, 100% message delivery.

#### Level 3: Advanced (Success Expected: 50-70%)

| Task ID | Description | Language | Key Challenge | Expected Time |
|---------|-------------|----------|---------------|---------------|
| L3-CPP-01 | Nested Struct with DynamicData | C++ | Loan pattern | 45-60 min |
| L3-CPP-02 | Union with Discriminator | C++ | set_discriminator() API | 45-60 min |
| L3-CPP-03 | Type Conversion (float32↔float64) | C++ | IDL type mapping | 30-45 min |
| L3-PY-01 | Binary Protocol Adapter (Inbound) | Python | Socket + DDS integration | 45-60 min |
| L3-PY-02 | Binary Protocol Adapter (Outbound) | Python | DDS subscription + encoding | 45-60 min |
| L3-MIX-01 | Full Loop Translation Test | Mixed | Multi-process, validation | 60-90 min |

**Pass Criteria**: 100% data integrity, proper type handling, no memory leaks.

#### Level 4: Expert (Success Expected: 20-40%)

| Task ID | Description | Language | Key Challenge | Expected Time |
|---------|-------------|----------|---------------|---------------|
| L4-CPP-01 | Standalone C++ Protocol Adapter | C++ | Full integration | 60-90 min |
| L4-CPP-02 | Content-Filtered Topic with DynamicData | C++ | Filter expressions | 45-60 min |
| L4-CPP-03 | Custom Serialization | C++ | CDR encoding | 60-90 min |
| L4-PY-01 | High-Frequency Publisher (1000 Hz) | Python | Performance tuning | 45-60 min |
| L4-RS-01 | Routing Service Transformation | C++ | Plugin architecture | 90-120 min |

**Pass Criteria**: Correct functionality, meets performance targets, production-quality code.

#### Level 5: Extreme (Success Expected: <20%)

| Task ID | Description | Language | Key Challenge | Expected Time |
|---------|-------------|----------|---------------|---------------|
| L5-RS-01 | Routing Service Protocol Adapter | C++ | Full RS plugin | 2-4 hours |
| L5-CPP-01 | Real-Time Publisher with Deadline QoS | C++ | Real-time constraints | 2-4 hours |
| L5-CPP-02 | Zero-Copy Data Sharing | C++ | Shared memory transport | 2-4 hours |
| L5-SEC-01 | DDS Security Configuration | C++ | PKI, permissions | 2-4 hours |
| L5-PERF-01 | Latency Optimization (<100μs) | C++ | Low-latency tuning | 3-5 hours |

**Pass Criteria**: Fully functional, meets strict performance/security requirements.

### 9.4 Benchmark Metrics

#### 9.4.1 Primary Metrics

| Metric | Description | Measurement Method |
|--------|-------------|-------------------|
| **Success Rate** | Did the task complete successfully? | Binary pass/fail |
| **Time to Completion** | Wall-clock time from start to passing tests | Timestamps |
| **Iteration Count** | Number of edit-test cycles | Count tool invocations |
| **Intervention Required** | Did a human need to help? | Binary + description |
| **Code Quality Score** | Does code follow best practices? | Automated linting + review |

#### 9.4.2 Secondary Metrics

| Metric | Description | Measurement Method |
|--------|-------------|-------------------|
| **Lines of Code** | Total LOC generated | wc -l |
| **Bug Density** | Bugs per 100 LOC | Manual review |
| **Test Coverage** | % of code paths tested | Coverage tools |
| **Documentation Quality** | Are comments helpful? | Manual review |
| **Error Recovery** | Can model recover from errors? | Inject failures |

#### 9.4.3 Failure Mode Analysis

| Failure Mode | Description | Detection | Severity |
|--------------|-------------|-----------|----------|
| **Hang** | Process blocks indefinitely | Timeout exceeded | Critical |
| **Type Mismatch** | Wrong C++ type for DDS field | Runtime error | High |
| **Memory Leak** | Unreturned loans, unclosed resources | Valgrind/ASan | High |
| **Logic Error** | Wrong data values | Validation failure | Medium |
| **Build Failure** | Code doesn't compile | Compiler errors | Medium |
| **Style Violation** | Non-idiomatic code | Linter warnings | Low |

### 9.5 Benchmark Test Harness

```python
@dataclass
class BenchmarkTask:
    task_id: str
    description: str
    language: str
    level: int  # 1-5
    expected_time_minutes: int
    validation_script: str
    starter_files: List[str]
    reference_solution: str  # For scoring
    
@dataclass
class BenchmarkResult:
    task_id: str
    model_name: str
    success: bool
    time_seconds: float
    iterations: int
    intervention_required: bool
    intervention_description: Optional[str]
    error_modes: List[str]
    code_quality_score: float  # 0-100
    
class DDSBenchmarkRunner:
    """
    Runs DDS programming benchmarks against AI models.
    """
    
    def run_benchmark(self, task: BenchmarkTask, model: ModelInterface) -> BenchmarkResult:
        # 1. Initialize workspace with starter files
        self.setup_workspace(task)
        
        # 2. Start supervisor agent for timeout detection
        supervisor = SupervisorAgent(timeout=task.expected_time_minutes * 2 * 60)
        
        # 3. Run model with task prompt
        start_time = time.time()
        iterations = 0
        
        while not self.is_complete(task):
            iterations += 1
            
            # Check for hung state
            if supervisor.detect_hang():
                supervisor.terminate_all()
                return BenchmarkResult(
                    success=False,
                    error_modes=["HANG"],
                    ...
                )
            
            # Let model make one iteration
            model.step()
            
            # Check timeout
            if time.time() - start_time > task.expected_time_minutes * 3 * 60:
                return BenchmarkResult(success=False, error_modes=["TIMEOUT"], ...)
        
        # 4. Validate result
        validation_passed = self.run_validation(task)
        
        # 5. Score code quality
        quality_score = self.score_code_quality(task)
        
        return BenchmarkResult(
            success=validation_passed,
            time_seconds=time.time() - start_time,
            iterations=iterations,
            code_quality_score=quality_score,
            ...
        )
```

### 9.6 Language-Specific Difficulty Multipliers

Based on observed performance:

| Language | Difficulty Multiplier | Notes |
|----------|----------------------|-------|
| Python | 1.0x (baseline) | Best model performance |
| Java | 1.3x | Verbose but well-documented |
| C++ (IDL-generated) | 1.5x | Compile-time complexity |
| C++ (DynamicData) | 2.5x | Runtime API complexity |
| C++ (Routing Service) | 4.0x+ | Plugin architecture, XML config |
| Rust | 2.0x | Ownership + DDS bindings |
| Go | 2.0x | Less common DDS bindings |

### 9.7 Model Capability Tiers

Based on benchmark results, models can be classified:

| Tier | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 | Description |
|------|---------|---------|---------|---------|---------|-------------|
| **S** | 100% | 95%+ | 80%+ | 60%+ | 30%+ | Production-ready DDS development |
| **A** | 95%+ | 85%+ | 60%+ | 30%+ | <20% | Capable with supervision |
| **B** | 90%+ | 70%+ | 40%+ | <20% | <10% | Basic DDS tasks only |
| **C** | 80%+ | 50%+ | <30% | <10% | <5% | Limited DDS capability |
| **D** | <80% | <50% | <20% | <5% | 0% | Not suitable for DDS |

### 9.8 Benchmark Dataset Structure

```
dds-benchmark/
├── README.md
├── benchmark_runner.py
├── benchmark_config.yaml
│
├── tasks/
│   ├── level1/
│   │   ├── L1-PY-01_hello_publisher/
│   │   │   ├── task.yaml           # Task definition
│   │   │   ├── prompt.md           # Initial prompt for model
│   │   │   ├── starter/            # Starter files (if any)
│   │   │   ├── reference/          # Reference solution
│   │   │   └── validation/         # Validation scripts
│   │   └── ...
│   ├── level2/
│   ├── level3/
│   ├── level4/
│   └── level5/
│
├── results/
│   ├── claude-opus-4.5/
│   ├── claude-sonnet-4/
│   ├── gpt-5.2/
│   ├── gpt-5.2-codex/
│   ├── gemini-3.0/
│   └── comparison_report.md
│
└── analysis/
    ├── failure_mode_analysis.py
    ├── time_analysis.py
    └── generate_leaderboard.py
```

### 9.9 Sample Task Definition

```yaml
# tasks/level3/L3-CPP-02_union_discriminator/task.yaml
task_id: L3-CPP-02
name: "DynamicData Union with Discriminator"
description: |
  Create a C++ publisher that publishes DynamicData samples containing a union type.
  The union has 3 members and requires setting the discriminator correctly.
  
level: 3
language: cpp
estimated_time_minutes: 45

starter_files:
  - CMakeLists.txt
  - types/VehicleData.xml  # IDL with union definition

requirements:
  - Publish 100 samples alternating between union members
  - Correctly set discriminator for each member
  - Use DynamicData API (not IDL-generated types)
  - Handle nested structs within union members

validation:
  script: validate.py
  criteria:
    - samples_received: 100
    - discriminator_correct: 100%
    - data_values_match: 100%
    - no_memory_leaks: true

common_failure_modes:
  - "Forgetting to call set_discriminator()"
  - "Wrong discriminator value for member"
  - "Type mismatch in nested struct access"
  - "Memory leak from unreturned loans"

hints_if_stuck:
  - level1: "Check that you're calling set_discriminator() before setting union member"
  - level2: "The discriminator value must match the case label in the IDL"
  - level3: "For nested structs, use loan_value() and remember to return_loan()"
```

### 9.10 Expected Benchmark Outcomes

Based on the STANAG 4586 project experience, we predict:

| Model Type | Strength | Weakness | Expected Tier |
|------------|----------|----------|---------------|
| Claude Opus 4.5 | Complex reasoning, debugging, best at systems programming | Long processes, real-time observation | S |
| Claude Sonnet 4 | Speed, cost efficiency, strong coding | Complex multi-step tasks | A-S |
| GPT-5.2 | Broad knowledge, fast iteration | Deep systems programming | A |
| GPT-5.2 Codex | Code-specialized, strong on common patterns | Novel APIs, DDS-specific | A-S |
| Gemini 3.0 | Multi-modal, tool use, strong reasoning | Less systems programming training | A |
| Gemini 3.0 Pro | Extended context, complex tasks | API complexity | A |
| Open source (Llama 4, Qwen 3, etc.) | Cost, privacy, local execution | Limited DDS training data | B-C |

### 9.11 Integration with CI/CD

```yaml
# .github/workflows/dds_benchmark.yml
name: DDS Model Benchmark

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:
    inputs:
      model:
        description: 'Model to benchmark'
        required: true
        type: choice
        options:
          - claude-opus-4.5
          - claude-sonnet-4
          - gpt-5.2
          - gpt-5.2-codex
          - gemini-3.0
          - gemini-3.0-pro

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup RTI Connext DDS
        run: ./scripts/setup_dds.sh
        
      - name: Run Benchmark Suite
        run: |
          python benchmark_runner.py \
            --model ${{ inputs.model }} \
            --levels 1,2,3 \
            --timeout-multiplier 2.0 \
            --output results/${{ inputs.model }}/
            
      - name: Generate Report
        run: python analysis/generate_report.py results/
        
        - name: Update Leaderboard
        run: python analysis/update_leaderboard.py
```

### 9.12 Deterministic Verification Framework

For a benchmark to be scientifically valid, verification must be **100% deterministic** - no human judgment, no subjective scoring. Every test produces a binary PASS/FAIL result.

#### 9.12.1 Reference Implementation Pattern

The key insight: **One side is human-verified, the other is AI-generated.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REFERENCE IMPLEMENTATION PATTERN                          │
└─────────────────────────────────────────────────────────────────────────────┘

Pattern A: Test AI-Generated Publisher
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────────────┐       DDS        ┌──────────────────┐
    │  AI-Generated    │  ────────────►   │  Reference       │
    │  Publisher       │                  │  Subscriber      │
    │  (Under Test)    │                  │  (Human-Verified)│
    └──────────────────┘                  └────────┬─────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Validation      │
                                          │  Output File     │
                                          │  (Deterministic) │
                                          └──────────────────┘

Pattern B: Test AI-Generated Subscriber
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────────────┐       DDS        ┌──────────────────┐
    │  Reference       │  ────────────►   │  AI-Generated    │
    │  Publisher       │                  │  Subscriber      │
    │  (Human-Verified)│                  │  (Under Test)    │
    └──────────────────┘                  └────────┬─────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Validation      │
                                          │  Output File     │
                                          │  (Deterministic) │
                                          └──────────────────┘
```

#### 9.12.2 Verification Output Specification

All subscribers (reference or AI-generated) must output to a standardized JSONL format:

```jsonl
{"seq": 1, "topic": "HelloWorld", "timestamp": 1735600000.123, "data": {"message": "Hello", "count": 1}}
{"seq": 2, "topic": "HelloWorld", "timestamp": 1735600000.223, "data": {"message": "Hello", "count": 2}}
```

**Verification compares against expected output:**

```python
class DeterministicVerifier:
    """
    100% deterministic verification - no human judgment required.
    """
    
    def verify(self, actual_file: str, expected_file: str) -> VerificationResult:
        """
        Returns PASS only if ALL criteria are met.
        """
        actual = self.load_jsonl(actual_file)
        expected = self.load_jsonl(expected_file)
        
        checks = {
            "sample_count": len(actual) == len(expected),
            "all_topics_correct": all(a['topic'] == e['topic'] for a, e in zip(actual, expected)),
            "all_data_matches": all(self.data_matches(a['data'], e['data']) for a, e in zip(actual, expected)),
            "ordering_preserved": all(a['seq'] == e['seq'] for a, e in zip(actual, expected)),
        }
        
        return VerificationResult(
            passed=all(checks.values()),
            checks=checks,
            details=self.generate_diff(actual, expected) if not all(checks.values()) else None
        )
    
    def data_matches(self, actual: dict, expected: dict, float_tolerance: float = 1e-6) -> bool:
        """Compare data with configurable float tolerance."""
        for key in expected:
            if key not in actual:
                return False
            if isinstance(expected[key], float):
                if abs(actual[key] - expected[key]) > float_tolerance:
                    return False
            elif actual[key] != expected[key]:
                return False
        return True
```

#### 9.12.3 Pass/Fail Criteria Matrix

| Criterion | Measurement | Pass Condition | Failure Example |
|-----------|-------------|----------------|-----------------|
| **Compilation** | Exit code | exit_code == 0 | Syntax error |
| **Execution** | Process completes | No hang, no crash | Segfault, timeout |
| **Sample Count** | len(actual) | == len(expected) | Missing samples |
| **Topic Names** | String match | 100% match | Wrong topic name |
| **Data Values** | Field comparison | 100% match (with float tolerance) | Wrong field value |
| **Data Types** | Type checking | All types correct | int instead of float |
| **Ordering** | Sequence numbers | Preserved | Out of order |
| **QoS Behavior** | Reliability, history | Matches specification | Lost samples on reliable |
| **No Errors** | stderr analysis | No DDS errors | Type mismatch error |
| **Memory Clean** | Valgrind/ASan | No leaks | Unreturned loan |

### 9.13 Intermediate Step Verification

Complex tasks should have **checkpoints** - intermediate verification points that confirm partial progress.

#### 9.13.1 Checkpoint Definitions

```yaml
# Example task with intermediate checkpoints
task_id: L3-CPP-01
name: "Standalone C++ Protocol Adapter"
checkpoints:
  - id: CP1_COMPILES
    description: "Code compiles without errors"
    verification: "cmake --build . 2>&1 | grep -q 'Built target'"
    weight: 0.1
    
  - id: CP2_STARTS
    description: "Process starts and initializes DDS"
    verification: "timeout 5 ./adapter --domain 99 2>&1 | grep -q 'DDS initialized'"
    weight: 0.1
    
  - id: CP3_RECEIVES_DATA
    description: "Adapter receives DDS samples"
    verification: "Run with reference publisher, check log for 'Received sample'"
    weight: 0.2
    
  - id: CP4_TRANSFORMS
    description: "Data transformation produces output"
    verification: "Check output file has > 0 bytes"
    weight: 0.2
    
  - id: CP5_CORRECT_OUTPUT
    description: "Output matches expected format"
    verification: "Compare first 10 samples against reference"
    weight: 0.2
    
  - id: CP6_FULL_PASS
    description: "100% data integrity verified"
    verification: "Full comparison against reference output"
    weight: 0.2

scoring:
  full_pass: "All checkpoints pass"
  partial_score: "Sum of (checkpoint.weight * checkpoint.passed)"
```

#### 9.13.2 Checkpoint Runner

```python
class CheckpointRunner:
    """
    Runs intermediate checkpoints and reports partial progress.
    """
    
    def run_checkpoints(self, task: BenchmarkTask) -> CheckpointResults:
        results = []
        
        for checkpoint in task.checkpoints:
            try:
                passed = self.run_verification(checkpoint)
                results.append(CheckpointResult(
                    checkpoint_id=checkpoint.id,
                    passed=passed,
                    weight=checkpoint.weight
                ))
                
                # Stop at first failure? Or continue for diagnosis?
                if not passed and checkpoint.blocking:
                    break
                    
            except Exception as e:
                results.append(CheckpointResult(
                    checkpoint_id=checkpoint.id,
                    passed=False,
                    error=str(e)
                ))
        
        return CheckpointResults(
            checkpoints=results,
            partial_score=sum(r.weight for r in results if r.passed),
            full_pass=all(r.passed for r in results)
        )
```

### 9.14 QoS-Specific Benchmarks

QoS configuration is a distinct skill from basic DDS programming. These benchmarks test QoS understanding.

#### 9.14.1 QoS Benchmark Tasks

| Task ID | QoS Focus | Description | Verification |
|---------|-----------|-------------|--------------|
| **QOS-REL-01** | Reliability | Publisher with RELIABLE QoS | No samples lost |
| **QOS-REL-02** | Reliability | Handle slow subscriber | Backpressure works |
| **QOS-DUR-01** | Durability | TRANSIENT_LOCAL late joiner | Subscriber gets history |
| **QOS-DUR-02** | Durability | PERSISTENT with database | Data survives restart |
| **QOS-HIS-01** | History | KEEP_LAST(10) | Only last 10 samples |
| **QOS-HIS-02** | History | KEEP_ALL with limits | Resource limit handling |
| **QOS-DL-01** | Deadline | Deadline QoS | Callback on missed deadline |
| **QOS-LF-01** | Lifespan | Sample expiration | Old samples not delivered |
| **QOS-OWN-01** | Ownership | Exclusive ownership | Highest strength wins |
| **QOS-PART-01** | Partition | Multi-partition | Correct routing |
| **QOS-CF-01** | Content Filter | Filter expression | Only matching samples |
| **QOS-TIME-01** | Time-Based Filter | Minimum separation | Rate limiting works |

#### 9.14.2 QoS Verification Patterns

```python
class QoSVerifier:
    """Verifies QoS-specific behaviors."""
    
    def verify_reliable(self, publisher_log: str, subscriber_output: str) -> bool:
        """RELIABLE: All published samples must be received."""
        published = self.count_published(publisher_log)
        received = self.count_received(subscriber_output)
        return published == received
    
    def verify_transient_local(self, 
                                publisher_output: str, 
                                late_joiner_output: str,
                                history_depth: int) -> bool:
        """TRANSIENT_LOCAL: Late joiner gets last N samples."""
        pre_join_samples = self.get_pre_join_samples(publisher_output, history_depth)
        received = self.load_jsonl(late_joiner_output)
        return pre_join_samples == received[:history_depth]
    
    def verify_deadline(self, 
                        deadline_callbacks: List[dict],
                        expected_misses: int) -> bool:
        """DEADLINE: Correct number of deadline missed callbacks."""
        return len(deadline_callbacks) == expected_misses
    
    def verify_ownership(self,
                         subscriber_output: str,
                         expected_source: int) -> bool:
        """OWNERSHIP: All samples from highest strength publisher."""
        samples = self.load_jsonl(subscriber_output)
        return all(s['source_id'] == expected_source for s in samples)
```

### 9.15 Language Coverage Matrix

RTI Connext DDS supports multiple language bindings. Benchmarks should cover all major ones.

#### 9.15.1 Supported Languages

| Language | API Style | Binding | Difficulty | Priority |
|----------|-----------|---------|------------|----------|
| **Python** | Modern | rti.connextdds | Baseline (1.0x) | P0 |
| **Modern C++** | C++11/14/17 | dds::* namespace | 1.5x | P0 |
| **Traditional C++** | C++98 style | DDS::* namespace | 2.0x | P1 |
| **Java** | Object-oriented | com.rti.dds.* | 1.3x | P1 |
| **C** | Procedural | DDS_* functions | 2.5x | P2 |
| **C#** | .NET | Rti.Dds.* | 1.5x | P2 |
| **Go** | Go idioms | Community binding | 2.0x | P3 |
| **Rust** | Rust idioms | Community binding | 2.0x | P3 |

#### 9.15.2 Cross-Language Test Matrix

Each task should be tested across languages with interoperability checks:

```
                        SUBSCRIBER LANGUAGE
                    Python  C++    Java   C      C#
                 ┌────────┬──────┬──────┬──────┬──────┐
         Python  │   ✓    │  ✓   │  ✓   │  ✓   │  ✓   │
                 ├────────┼──────┼──────┼──────┼──────┤
P        C++     │   ✓    │  ✓   │  ✓   │  ✓   │  ✓   │
U                ├────────┼──────┼──────┼──────┼──────┤
B        Java    │   ✓    │  ✓   │  ✓   │  ✓   │  ✓   │
L                ├────────┼──────┼──────┼──────┼──────┤
I        C       │   ✓    │  ✓   │  ✓   │  ✓   │  ✓   │
S                ├────────┼──────┼──────┼──────┼──────┤
H        C#      │   ✓    │  ✓   │  ✓   │  ✓   │  ✓   │
E                └────────┴──────┴──────┴──────┴──────┘
R
```

#### 9.15.3 Language-Specific Benchmark Tasks

```yaml
# Per-language task variants
language_tasks:
  hello_world_publisher:
    base_task: L1-01
    variants:
      python:
        task_id: L1-PY-01
        reference_subscriber: reference/python/hello_subscriber.py
        expected_output: expected/hello_world_100_samples.jsonl
        
      cpp_modern:
        task_id: L1-CPP-01
        reference_subscriber: reference/cpp/hello_subscriber
        expected_output: expected/hello_world_100_samples.jsonl
        build_command: "cmake --build ."
        
      java:
        task_id: L1-JAVA-01
        reference_subscriber: reference/java/HelloSubscriber.jar
        expected_output: expected/hello_world_100_samples.jsonl
        build_command: "mvn package"
        
      c:
        task_id: L1-C-01
        reference_subscriber: reference/c/hello_subscriber
        expected_output: expected/hello_world_100_samples.jsonl
        build_command: "make"
```

### 9.16 Reference Implementation Library

Human-verified reference implementations serve as the "ground truth" for verification.

#### 9.16.1 Reference Implementation Requirements

| Requirement | Description |
|-------------|-------------|
| **Human-reviewed** | Code reviewed by DDS expert |
| **100% test coverage** | All code paths verified |
| **Documented** | Clear comments explaining DDS usage |
| **Multi-language** | Same logic in each supported language |
| **Deterministic output** | Same input → same output |
| **Configurable** | Domain ID, topic, sample count as parameters |

#### 9.16.2 Reference Implementation Structure

```
reference_implementations/
├── README.md
├── types/
│   ├── HelloWorld.xml          # Shared type definitions
│   ├── VehicleData.xml
│   └── ComplexTypes.xml
│
├── python/
│   ├── hello_publisher.py      # Reference publisher
│   ├── hello_subscriber.py     # Reference subscriber (outputs JSONL)
│   ├── vehicle_publisher.py
│   ├── vehicle_subscriber.py
│   └── qos_profiles.xml
│
├── cpp_modern/
│   ├── CMakeLists.txt
│   ├── hello_publisher.cxx
│   ├── hello_subscriber.cxx
│   ├── vehicle_publisher.cxx
│   └── vehicle_subscriber.cxx
│
├── java/
│   ├── pom.xml
│   └── src/main/java/
│       ├── HelloPublisher.java
│       └── HelloSubscriber.java
│
├── c/
│   ├── Makefile
│   ├── hello_publisher.c
│   └── hello_subscriber.c
│
└── expected_outputs/
    ├── hello_world_100_samples.jsonl
    ├── hello_world_1000_samples.jsonl
    ├── vehicle_data_reliable.jsonl
    └── vehicle_data_transient_local.jsonl
```

#### 9.16.3 Expected Output Generation

```bash
# Generate expected outputs using reference implementations
cd reference_implementations

# Run reference publisher and subscriber together
python python/hello_publisher.py --count 100 --domain 99 &
PUB_PID=$!
python python/hello_subscriber.py --count 100 --domain 99 --output expected_outputs/hello_world_100_samples.jsonl
kill $PUB_PID

# Verify output is reproducible (run 3 times, compare)
for i in 1 2 3; do
    python python/hello_publisher.py --count 100 --domain 99 &
    python python/hello_subscriber.py --count 100 --domain 99 --output /tmp/run_$i.jsonl
    wait
done

# All three runs must produce identical output (excluding timestamps)
python verify_deterministic.py /tmp/run_1.jsonl /tmp/run_2.jsonl /tmp/run_3.jsonl
```

### 9.17 Complete Verification Pipeline

```python
class BenchmarkVerificationPipeline:
    """
    Complete verification pipeline for DDS benchmarks.
    Produces 100% deterministic PASS/FAIL results.
    """
    
    def __init__(self, task: BenchmarkTask, language: str):
        self.task = task
        self.language = language
        self.reference_impl = self.load_reference(task, language)
        
    def run_full_verification(self, ai_code_path: str) -> VerificationReport:
        """
        Complete verification with checkpoints.
        Returns detailed report with PASS/FAIL for each step.
        """
        report = VerificationReport(task_id=self.task.task_id)
        
        # Checkpoint 1: Build
        build_result = self.verify_build(ai_code_path)
        report.add_checkpoint("BUILD", build_result)
        if not build_result.passed:
            return report.finalize(overall_pass=False)
        
        # Checkpoint 2: Startup
        startup_result = self.verify_startup(ai_code_path)
        report.add_checkpoint("STARTUP", startup_result)
        if not startup_result.passed:
            return report.finalize(overall_pass=False)
        
        # Checkpoint 3: DDS Communication
        if self.task.type == "publisher":
            comm_result = self.verify_publisher_with_reference_subscriber(ai_code_path)
        else:
            comm_result = self.verify_subscriber_with_reference_publisher(ai_code_path)
        report.add_checkpoint("COMMUNICATION", comm_result)
        if not comm_result.passed:
            return report.finalize(overall_pass=False)
        
        # Checkpoint 4: Data Integrity
        integrity_result = self.verify_data_integrity(
            actual_output=comm_result.output_file,
            expected_output=self.task.expected_output
        )
        report.add_checkpoint("DATA_INTEGRITY", integrity_result)
        
        # Checkpoint 5: QoS Behavior (if applicable)
        if self.task.qos_verification:
            qos_result = self.verify_qos_behavior()
            report.add_checkpoint("QOS_BEHAVIOR", qos_result)
        
        # Checkpoint 6: Resource Cleanup
        cleanup_result = self.verify_no_resource_leaks()
        report.add_checkpoint("RESOURCE_CLEANUP", cleanup_result)
        
        return report.finalize(
            overall_pass=all(cp.passed for cp in report.checkpoints)
        )
    
    def verify_data_integrity(self, actual_output: str, expected_output: str) -> CheckpointResult:
        """
        100% deterministic data comparison.
        """
        actual = self.load_and_normalize(actual_output)
        expected = self.load_and_normalize(expected_output)
        
        if len(actual) != len(expected):
            return CheckpointResult(
                passed=False,
                reason=f"Sample count mismatch: {len(actual)} vs {len(expected)}"
            )
        
        mismatches = []
        for i, (a, e) in enumerate(zip(actual, expected)):
            diff = self.compare_samples(a, e)
            if diff:
                mismatches.append({"index": i, "diff": diff})
        
        if mismatches:
            return CheckpointResult(
                passed=False,
                reason=f"{len(mismatches)} sample mismatches",
                details=mismatches[:10]  # First 10 for debugging
            )
        
        return CheckpointResult(passed=True)
```

### 9.18 Benchmark Scoring Summary

| Score | Criteria | Interpretation |
|-------|----------|----------------|
| **100%** | All checkpoints pass, data integrity verified | Full success |
| **80-99%** | Minor issues (e.g., style, minor QoS deviation) | Acceptable |
| **50-79%** | Partial functionality, some checkpoints fail | Needs improvement |
| **20-49%** | Compiles but major functionality missing | Significant issues |
| **1-19%** | Compiles only, no correct DDS behavior | Fundamental problems |
| **0%** | Does not compile or immediate crash | Complete failure |

### 9.19 Benchmark Harness Evaluation

#### 9.19.1 Requirements

For automated DDS benchmarking, the harness must support:

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **Full Automation** | P0 | No human intervention during benchmark runs |
| **Multi-Model Support** | P0 | Claude, GPT-4, Gemini, open source models |
| **Tool Execution** | P0 | Run builds, tests, capture output |
| **Timeout Handling** | P0 | Kill hung processes automatically |
| **Metrics Capture** | P0 | Time, iterations, token usage |
| **Reproducibility** | P0 | Same test → same environment |
| **File System Access** | P1 | Read/write code files |
| **Terminal Access** | P1 | Execute shell commands |
| **Parallel Execution** | P2 | Run multiple benchmarks simultaneously |
| **Cost Tracking** | P2 | Track API costs per benchmark |

#### 9.19.2 Harness Options Analysis

##### Option 1: Aider (CLI-based Agent)

```bash
# Example automated invocation
aider --model claude-opus-4.5 --yes --no-git \
    --message "Create a DDS publisher for Vehicle_Kinematics topic" \
    --file src/publisher.cpp
```

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Automation** | ⭐⭐⭐⭐⭐ | CLI-native, `--yes` mode, scriptable |
| **Multi-Model** | ⭐⭐⭐⭐⭐ | Claude, GPT-4, Gemini, Ollama, many others |
| **Tool Execution** | ⭐⭐⭐⭐ | Shell commands via `/run`, but limited |
| **Timeout Handling** | ⭐⭐⭐ | External wrapper needed |
| **Metrics** | ⭐⭐⭐ | Token counts, but needs wrapper for timing |
| **Maturity** | ⭐⭐⭐⭐⭐ | Production-ready, active development |

**Pros:**
- Purpose-built for automated coding tasks
- Excellent model coverage (20+ models)
- Git-aware (tracks changes)
- Lightweight, easy to containerize
- Active community and documentation

**Cons:**
- Limited tool execution (no native DDS tools)
- No built-in timeout handling
- Single-file focus (less natural for multi-file projects)
- No native benchmark metrics

##### Option 2: Cursor (IDE-based)

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Automation** | ⭐⭐ | No headless mode, requires GUI |
| **Multi-Model** | ⭐⭐⭐⭐⭐ | Excellent model support |
| **Tool Execution** | ⭐⭐⭐⭐⭐ | Full terminal, file system, tools |
| **Timeout Handling** | ⭐⭐ | Manual intervention often needed |
| **Metrics** | ⭐⭐ | No built-in benchmark metrics |
| **Maturity** | ⭐⭐⭐⭐ | Polished, but automation-unfriendly |

**Pros:**
- Best-in-class interactive experience
- Excellent multi-model support
- Rich tool integration
- Familiar IDE environment

**Cons:**
- **No headless/automation mode** (critical limitation)
- Requires human to start/monitor sessions
- No API for programmatic control
- Not suitable for CI/CD

##### Option 3: SWE-agent / OpenHands (Purpose-Built Evaluation)

```python
# SWE-agent style invocation
from sweagent import Agent, Environment

env = Environment(
    repo_path="./dds_benchmark_task",
    dockerfile="Dockerfile.dds"
)
agent = Agent(model="claude-opus-4.5")
result = agent.run(
    task="Create a DDS publisher for Vehicle_Kinematics",
    timeout=3600
)
```

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Automation** | ⭐⭐⭐⭐⭐ | Purpose-built for evaluation |
| **Multi-Model** | ⭐⭐⭐⭐ | Claude, GPT-4, open source |
| **Tool Execution** | ⭐⭐⭐⭐⭐ | Docker containers, full control |
| **Timeout Handling** | ⭐⭐⭐⭐⭐ | Built-in timeout management |
| **Metrics** | ⭐⭐⭐⭐⭐ | Designed for benchmarking |
| **Maturity** | ⭐⭐⭐⭐ | Research-grade, active development |

**Pros:**
- Designed specifically for agent evaluation
- Docker isolation (reproducible environments)
- Built-in metrics and logging
- Established methodology (SWE-bench)
- Handles hung processes gracefully

**Cons:**
- More complex setup
- Heavier resource requirements
- Less flexible for interactive development
- Learning curve

##### Option 4: Custom Framework (API-Direct)

```python
# Custom harness using Anthropic API
class DDSBenchmarkHarness:
    def __init__(self, model: str):
        self.client = anthropic.Client()
        self.model = model
        self.tools = self.define_dds_tools()
    
    def run_benchmark(self, task: BenchmarkTask) -> BenchmarkResult:
        conversation = []
        start_time = time.time()
        iterations = 0
        
        while not self.is_complete(task):
            response = self.client.messages.create(
                model=self.model,
                messages=conversation,
                tools=self.tools,
                max_tokens=4096
            )
            
            # Execute tool calls
            for tool_use in response.tool_uses:
                result = self.execute_tool(tool_use)
                conversation.append({"role": "tool", "content": result})
            
            iterations += 1
            
            # Timeout check
            if time.time() - start_time > task.timeout:
                return BenchmarkResult(success=False, reason="TIMEOUT")
        
        return self.verify_result(task)
```

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Automation** | ⭐⭐⭐⭐⭐ | Full control |
| **Multi-Model** | ⭐⭐⭐⭐ | Must implement each API |
| **Tool Execution** | ⭐⭐⭐⭐⭐ | Define exactly what's needed |
| **Timeout Handling** | ⭐⭐⭐⭐⭐ | Full control |
| **Metrics** | ⭐⭐⭐⭐⭐ | Capture everything |
| **Maturity** | ⭐⭐ | Must build from scratch |

**Pros:**
- Complete control over everything
- Exactly matches our requirements
- Can optimize for DDS-specific workflows
- No external dependencies

**Cons:**
- Significant development effort (2-4 weeks)
- Must maintain API compatibility
- Need to implement tool execution layer
- No community support

##### Option 5: VS Code + Continue.dev/Cline

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Automation** | ⭐⭐⭐ | Possible via Extension Host API |
| **Multi-Model** | ⭐⭐⭐⭐ | Continue supports many models |
| **Tool Execution** | ⭐⭐⭐⭐⭐ | Full VS Code capabilities |
| **Timeout Handling** | ⭐⭐⭐ | Must implement |
| **Metrics** | ⭐⭐⭐ | Must implement |
| **Maturity** | ⭐⭐⭐ | Extensions are stable, automation is custom |

**Pros:**
- Familiar VS Code environment
- Rich extension ecosystem
- Open source options (Continue.dev)
- Good terminal/file integration

**Cons:**
- Automation requires custom extension
- Extension Host API complexity
- Less straightforward than CLI tools
- Heavier runtime

#### 9.19.3 Recommendation

##### Primary: **Aider + Custom Wrapper**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED ARCHITECTURE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Benchmark Runner    │     │  Aider               │     │  DDS Environment │
│  (Python Wrapper)    │────►│  (Agent Core)        │────►│  (Docker)        │
│                      │     │                      │     │                  │
│  - Task selection    │     │  - Model interface   │     │  - RTI Connext   │
│  - Timeout handling  │     │  - Code generation   │     │  - Build tools   │
│  - Metrics capture   │     │  - Git integration   │     │  - Reference impl│
│  - Result validation │     │  - Multi-model       │     │  - Test harness  │
└──────────────────────┘     └──────────────────────┘     └──────────────────┘
           │                                                        │
           │                  ┌──────────────────────┐              │
           └─────────────────►│  Verification        │◄─────────────┘
                              │  Framework           │
                              │                      │
                              │  - JSONL comparison  │
                              │  - Checkpoint eval   │
                              │  - Pass/Fail report  │
                              └──────────────────────┘
```

**Why Aider:**
1. **Best automation support** - CLI-native with `--yes` mode
2. **Excellent model coverage** - All major models + local
3. **Lightweight** - Easy to containerize, fast startup
4. **Active development** - Regular updates, good community
5. **Proven** - Used in production by many teams

**Wrapper Responsibilities:**
- Process management with timeouts
- Metrics capture (time, tokens, iterations)
- Environment setup (Docker with DDS)
- Result verification
- Report generation

##### Backup: **SWE-agent / OpenHands**

If Aider proves insufficient (e.g., complex multi-file tasks):

**Why SWE-agent:**
1. **Purpose-built for evaluation** - Exactly what we need
2. **Docker isolation** - Reproducible environments
3. **Proven methodology** - Used in academic benchmarks
4. **Better for complex tasks** - Multi-step reasoning

**When to switch:**
- Tasks requiring deep codebase exploration
- Multi-file refactoring tasks
- Tasks where Aider's single-turn approach fails

#### 9.19.4 Implementation Plan

```yaml
# harness_config.yaml
harness:
  primary: aider
  backup: swe-agent
  
aider_config:
  models:
    - claude-opus-4.5
    - claude-sonnet-4
    - gpt-5.2
    - gpt-5.2-codex
    - gemini-3.0
    - gemini-3.0-pro
    - deepseek-v3
    - qwen-3-coder
  options:
    yes: true          # Non-interactive
    no_git: false      # Track changes
    auto_commits: true
    
wrapper_config:
  timeout_seconds: 3600
  max_iterations: 50
  checkpoint_interval: 10  # Verify every 10 iterations
  
docker_config:
  base_image: "rti-connext-dds:7.3.0"
  mount_workspace: true
  network_mode: "host"  # For DDS discovery
  
verification:
  reference_implementations: "./reference/"
  expected_outputs: "./expected/"
  float_tolerance: 1e-6
```

#### 9.19.5 Wrapper Implementation

```python
#!/usr/bin/env python3
"""
DDS Benchmark Harness - Aider Wrapper
"""

import subprocess
import time
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class BenchmarkConfig:
    task_id: str
    model: str
    timeout: int = 3600
    max_iterations: int = 50

class AiderBenchmarkHarness:
    """
    Wraps Aider for automated DDS benchmarking.
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.workspace = tempfile.mkdtemp(prefix=f"dds_bench_{config.task_id}_")
        self.metrics = {
            "start_time": None,
            "end_time": None,
            "iterations": 0,
            "tokens_used": 0,
            "checkpoints_passed": [],
        }
    
    def run(self, task_prompt: str) -> BenchmarkResult:
        """Run benchmark with full automation."""
        self.metrics["start_time"] = time.time()
        
        # Setup workspace with starter files
        self.setup_workspace()
        
        # Run Aider in non-interactive mode
        try:
            result = self._run_aider(task_prompt)
        except subprocess.TimeoutExpired:
            return BenchmarkResult(
                success=False,
                reason="TIMEOUT",
                metrics=self.metrics
            )
        
        self.metrics["end_time"] = time.time()
        
        # Run verification
        verification = self.verify_result()
        
        return BenchmarkResult(
            success=verification.passed,
            checkpoints=verification.checkpoints,
            metrics=self.metrics
        )
    
    def _run_aider(self, prompt: str) -> subprocess.CompletedProcess:
        """Execute Aider with timeout and monitoring."""
        cmd = [
            "aider",
            "--model", self.config.model,
            "--yes",  # Non-interactive
            "--no-pretty",  # Clean output for parsing
            "--message", prompt,
        ]
        
        return subprocess.run(
            cmd,
            cwd=self.workspace,
            timeout=self.config.timeout,
            capture_output=True,
            text=True
        )
    
    def verify_result(self) -> VerificationResult:
        """Run deterministic verification."""
        verifier = DeterministicVerifier()
        return verifier.run_checkpoints(
            workspace=self.workspace,
            task_id=self.config.task_id
        )


def main():
    """Run benchmark suite."""
    models = [
        "claude-opus-4.5",
        "claude-sonnet-4",
        "gpt-5.2",
        "gpt-5.2-codex",
        "gemini-3.0",
    ]
    
    tasks = load_benchmark_tasks("tasks/")
    results = []
    
    for model in models:
        for task in tasks:
            config = BenchmarkConfig(
                task_id=task.id,
                model=model,
                timeout=task.expected_time * 2
            )
            
            harness = AiderBenchmarkHarness(config)
            result = harness.run(task.prompt)
            results.append(result)
            
            print(f"{model} | {task.id} | {'PASS' if result.success else 'FAIL'}")
    
    generate_report(results)


if __name__ == "__main__":
    main()
```

#### 9.19.6 Harness Comparison Summary

| Harness | Automation | Models | Complexity | Recommendation |
|---------|------------|--------|------------|----------------|
| **Aider + Wrapper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **Primary** |
| SWE-agent | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **Backup** |
| Custom Framework | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Future option |
| Cursor | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | Not suitable |
| VS Code + Extensions | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Not recommended |

**Final Recommendation:**
1. **Start with Aider + Custom Wrapper** - Fast to implement, covers most cases
2. **Evaluate SWE-agent for complex tasks** - If Aider struggles with multi-file/multi-step
3. **Consider custom framework later** - If benchmark suite grows significantly

---

## 10. Conclusion

This framework addresses the key challenges we encountered in the STANAG 4586 project:

1. **Hung processes** → Supervisor agent with automatic timeout detection
2. **Type mismatches** → Type validation tool + error pattern recognition
3. **Testing complexity** → Configuration-driven test harness
4. **Debugging difficulty** → RTI DDS Spy wrapper with structured output
5. **Model evaluation** → Standardized benchmarks across difficulty levels

By implementing this framework, we achieve two goals:

1. **Reduce DDS development time from weeks to hours**, enabling junior teams to develop reliable DDS applications with AI assistance.

2. **Provide objective benchmarks for AI model capabilities** in systems programming, allowing organizations to select the right model for their DDS development needs.

The key insight is that **DDS's universal subscribability (via rtiddsspy) enables a verified-first development pattern** where each component is validated before building the next, dramatically reducing debugging time and integration issues.

The benchmarking component adds scientific rigor to AI-assisted development by providing:
- **Reproducible tasks** across difficulty levels
- **Quantitative metrics** (success rate, time, iterations, interventions)
- **Failure mode analysis** to understand model limitations
- **Model tier classification** for practical tool selection


# DDS Agent Development Framework

CLI tools for AI-assisted DDS development using RTI DDS Spy as a universal subscriber.

## Overview

This framework enables a "verified publisher first, then subscriber" development pattern:

1. **Phase 1**: Develop a DDS publisher and verify it using `dds-spy-wrapper` (which wraps RTI DDS Spy)
2. **Phase 2**: Once the publisher is verified, develop a subscriber against it

## Installation

```bash
# From the project directory
pip install -e ".[dev]"
```

## Requirements

- Python 3.10+
- RTI Connext DDS installed with `$NDDSHOME` environment variable set
- `rtiddsspy` available at `$NDDSHOME/bin/rtiddsspy`

## Tools

### dds-spy-wrapper

Wraps `rtiddsspy` and converts its human-readable output to structured JSONL.

```bash
dds-spy-wrapper --domain 222 --topics "Vehicle_*" --timeout 30 --output samples.jsonl
```

### dds-process-monitor

Manages DDS processes with automatic timeout detection and termination.

```bash
# Start a process with monitoring
dds-process-monitor start --name my_publisher --timeout 60 -- python publisher.py --domain 99

# Check status
dds-process-monitor status

# Kill a specific process
dds-process-monitor kill --name my_publisher

# Cleanup all managed processes
dds-process-monitor cleanup
```

### dds-sample-compare

Compares captured DDS samples against expected output.

```bash
dds-sample-compare --actual samples.jsonl --expected expected.jsonl --tolerance 1e-6
```

### dds-test-harness

Orchestrates the full publisher verification workflow.

```bash
dds-test-harness run --config test_config.yaml
dds-test-harness run --config test_config.yaml --test publisher_only
```

## Development Workflow

```
┌──────────────┐         ┌─────────────────┐         ┌──────────────────┐
│   Your       │   DDS   │  RTI DDS Spy    │  Text   │  Validation      │
│   Publisher  │ ──────► │  (Universal     │ ──────► │  Framework       │
│   (WIP)      │         │   Subscriber)   │         │  (Automated)     │
└──────────────┘         └─────────────────┘         └──────────────────┘
```

## DDS Development Guidelines

See [docs/DDS_DEVELOPMENT_GUIDELINES.md](docs/DDS_DEVELOPMENT_GUIDELINES.md) for required practices:

- **Test Early, Test Often**: Verify each component before proceeding (most critical)
- **Always Use Timeouts**: All commands must have `timeout` to prevent hangs
- **Async Callbacks**: Use WaitSet/on_data_available, NOT polling
- **External QoS**: Load QoS from XML files, NOT hardcoded  
- **Safe Domain IDs**: Use range 50-99 for testing

These guidelines apply to all AI-generated code in benchmarks unless explicitly overridden.

## License

MIT


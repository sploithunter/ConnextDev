# Task: Create C++ DDS Publisher from Scratch

## Critical Development Principle

**TEST EARLY, TEST OFTEN** - Build and test after each step. Don't write everything before testing.

## Objective

Create a DDS publisher in C++ that publishes to the "HelloWorld" topic.
Your publisher must interoperate with a Python subscriber (provided for testing).

**You are NOT given any source code to translate. Create this from scratch.**

## Type Specification

Create a DDS type with these exact fields:

| Field | Type | Notes |
|-------|------|-------|
| message | string | max length 256 |
| count | int32 | sequence number |

## QoS Requirements

For interoperability with the test subscriber:

| QoS Policy | Setting |
|------------|---------|
| Reliability | RELIABLE |
| Durability | TRANSIENT_LOCAL |
| History | KEEP_ALL |

## Behavior

1. Parse command line: `--count N` (default 10), `--domain D` (default 0)
2. Create DomainParticipant on specified domain
3. Create Topic "HelloWorld" with the type above
4. Create DataWriter with QoS settings above
5. Wait 2 seconds for subscriber discovery
6. Publish N samples:
   - message = "Hello, World!"
   - count = 1, 2, 3, ... N
   - 500ms delay between samples
7. Wait 2 seconds for reliable delivery
8. Exit cleanly

## Required Files

### 1. HelloWorld.idl

Define the DDS type in IDL format.

### 2. publisher.cxx

The C++ publisher using RTI Connext DDS Modern C++ API.

Key includes:
```cpp
#include <dds/dds.hpp>
#include "HelloWorld.hpp"  // Generated from IDL
```

### 3. CMakeLists.txt

Build configuration using RTI's CMake support.

Key elements:
- `find_package(RTIConnextDDS REQUIRED)`
- Use `connextdds_rtiddsgen()` to generate type support
- Link against `RTIConnextDDS::cpp2_api`

## Build Instructions

```bash
mkdir build && cd build
cmake .. -DCONNEXTDDS_DIR=$NDDSHOME
make
```

## Verification

Your publisher is correct when:
1. It compiles without errors
2. Running `./publisher --count 10` successfully publishes
3. The Python test subscriber receives all 10 samples
4. Sample content: message="Hello, World!", count=1..10

Run `./test_interop.sh` to verify interoperability.

## Hints

- RTI Modern C++ API uses `dds::` namespace
- QoS is set via stream operators: `qos << dds::core::policy::Reliability::Reliable()`
- Type-safe DataWriter: `dds::pub::DataWriter<HelloWorld>`
- Sample fields accessed via generated methods: `sample.message("Hello")`

## DO NOT

- Do not use the legacy C API
- Do not use XML QoS files (set QoS in code)
- Do not assume any header paths - use standard RTI includes


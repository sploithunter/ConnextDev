# Task: Translate Python DDS Publisher to C++

## Critical Development Principle

**TEST EARLY, TEST OFTEN** - Build and test after each change. Do not write large amounts of code without testing.

## Objective

Translate the provided Python DDS publisher to C++ while maintaining exact interoperability with the existing Python subscriber.

## Source Code to Translate

```python
#!/usr/bin/env python3
"""HelloWorld DDS Publisher - Translate this to C++"""

import argparse
import time
import sys
import rti.connextdds as dds

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", "-c", type=int, default=10)
    parser.add_argument("--domain", "-d", type=int, default=0)
    args = parser.parse_args()
    
    # Create type dynamically
    hello_type = dds.StructType("HelloWorld")
    hello_type.add_member(dds.Member("message", dds.StringType(256)))
    hello_type.add_member(dds.Member("count", dds.Int32Type()))
    
    # Create participant and topic
    participant = dds.DomainParticipant(args.domain)
    topic = dds.DynamicData.Topic(participant, "HelloWorld", hello_type)
    
    # Create publisher with QoS
    publisher = dds.Publisher(participant)
    writer_qos = dds.DataWriterQos()
    writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
    writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
    writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
    
    writer = dds.DynamicData.DataWriter(publisher, topic, writer_qos)
    
    time.sleep(2.0)  # Discovery
    
    for i in range(1, args.count + 1):
        sample = dds.DynamicData(hello_type)
        sample["message"] = "Hello, World!"
        sample["count"] = i
        writer.write(sample)
        print(f"Published: count={i}", file=sys.stderr)
        if i < args.count:
            time.sleep(0.5)
    
    time.sleep(2.0)  # Allow reliable delivery

if __name__ == "__main__":
    main()
```

## Requirements

### 1. Create HelloWorld.idl

```idl
struct HelloWorld {
    string<256> message;
    long count;
};
```

### 2. Create publisher.cxx

Use RTI Connext DDS Modern C++ API:

```cpp
#include <dds/dds.hpp>
#include "HelloWorld.hpp"  // Generated from IDL

int main(int argc, char* argv[]) {
    // Parse args (--count, --domain)
    // Create participant
    // Create topic
    // Create writer with matching QoS
    // Publish samples
}
```

### 3. Create/Update CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.10)
project(HelloWorldPublisher)

find_package(RTIConnextDDS REQUIRED)

# Generate type support from IDL
connextdds_rtiddsgen(
    INPUT HelloWorld.idl
    LANG C++11
)

add_executable(publisher publisher.cxx ${GENERATED_SOURCES})
target_link_libraries(publisher RTIConnextDDS::cpp2_api)
```

## Critical: QoS Must Match

For interoperability with the Python subscriber:
- Reliability: RELIABLE
- Durability: TRANSIENT_LOCAL
- History: KEEP_ALL

## Build and Test

```bash
# Build
mkdir build && cd build
cmake .. -DCONNEXTDDS_DIR=$NDDSHOME
make

# Test (Python subscriber in separate terminal)
./publisher --count 10 --domain 0
```

## Verification

Your C++ publisher is correct when:
1. It compiles without errors
2. The Python subscriber receives all 10 samples
3. Sample content matches: message="Hello, World!", count=1..10

## Files to Create

1. `HelloWorld.idl` - Type definition
2. `publisher.cxx` - C++ publisher implementation
3. `CMakeLists.txt` - Build configuration

Run `./test_interop.sh` after building to verify interoperability.


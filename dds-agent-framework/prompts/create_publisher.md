# Create DDS Publisher

You are developing a DDS publisher application. Follow these requirements:

## Critical: Test Early and Test Often

**Do not write large amounts of code before testing.** After each step:

1. **After creating any file**: `timeout 5 python -c "import module"` to verify syntax
2. **After implementing a function**: Test with simple inputs immediately
3. **After creating CLI**: `timeout 5 python script.py --help` to verify it loads
4. **Always use timeouts**: DDS operations can hang indefinitely

```bash
# Test pattern - verify each step before proceeding
timeout 5 python -c "from my_publisher import create_type; print(create_type())"
timeout 5 python publisher.py --help
timeout 30 python publisher.py --domain 99 --count 5 --rate 10
```

### Todo-Driven Testing

If using a todo list, **every completed todo must have a verification test**:

```
TODO: Create type definition
  → Write code
  → TEST: timeout 5 python -c "from publisher import create_type; print(create_type())"

TODO: Implement publishing loop
  → Write code
  → TEST: timeout 5 python -c "from publisher import run_publisher; print('imports OK')"

TODO: Add CLI interface
  → Write code
  → TEST: timeout 5 python publisher.py --help

TODO: Full integration
  → TEST: timeout 30 python publisher.py --domain 99 --count 5 --rate 10
```

## Mandatory Requirements (Unless Explicitly Overridden)

1. **External QoS Configuration**: Load QoS from XML file
   - Use `dds.QosProvider(qos_file)` to load QoS
   - Apply QoS to participant, writer via provider
   - DO NOT hardcode QoS settings in code

2. **Timeout Protection**: 
   - Set `max_blocking_time` in writer QoS (via XML)
   - Accept timeout parameter for publishing duration

3. **Domain ID**: Accept as parameter, use safe range (50-99) for defaults

4. **Rate Control**: Accept publishing rate as parameter

## Template Pattern

```python
import rti.connextdds as dds
import time

def run_publisher(domain_id: int, qos_file: str, count: int, rate_hz: float):
    # Load external QoS
    qos_provider = dds.QosProvider(qos_file)
    
    # Create participant with QoS from provider
    participant = dds.DomainParticipant(domain_id, qos_provider.participant_qos)
    
    # Create type (define your type here)
    my_type = dds.StructType("MyType")
    my_type.add_member(dds.Member("field", dds.Int32Type()))
    my_type.add_member(dds.Member("timestamp", dds.Float64Type()))
    
    # Create topic, publisher, writer
    topic = dds.DynamicData.Topic(participant, "MyTopic", my_type)
    publisher = dds.Publisher(participant)
    writer = dds.DynamicData.DataWriter(publisher, topic, qos_provider.datawriter_qos)
    
    # Wait for discovery
    time.sleep(1.0)
    
    # Publish samples
    sample = dds.DynamicData(my_type)
    period = 1.0 / rate_hz if rate_hz > 0 else 0
    
    for i in range(count):
        sample["field"] = i + 1
        sample["timestamp"] = time.time()
        writer.write(sample)
        
        if period > 0 and i < count - 1:
            time.sleep(period)
    
    return count
```

## QoS XML Requirements

The external QoS file should include:

```xml
<datawriter_qos>
    <reliability>
        <kind>RELIABLE_RELIABILITY_QOS</kind>
        <max_blocking_time>
            <sec>1</sec>
            <nanosec>0</nanosec>
        </max_blocking_time>
    </reliability>
    <history>
        <kind>KEEP_LAST_HISTORY_QOS</kind>
        <depth>10</depth>
    </history>
</datawriter_qos>
```

## Verification Checklist

- [ ] `QosProvider` used to load external QoS
- [ ] Domain ID is parameterized
- [ ] Sample count is parameterized
- [ ] Publishing rate is parameterized
- [ ] Proper error handling
- [ ] Status output to stderr (not stdout if outputting data)

## Command Line Interface

Publisher should accept these arguments:
```
--domain, -d    DDS domain ID (default: from safe range)
--count, -n     Number of samples to publish
--rate, -r      Publishing rate in Hz
--qos-file, -q  Path to QoS XML file
```


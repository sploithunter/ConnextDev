# Create DDS Subscriber

You are developing a DDS subscriber application. Follow these requirements:

## Critical: Test Early and Test Often

**Do not write large amounts of code before testing.** After each step:

1. **After creating any file**: `timeout 5 python -c "import module"` to verify syntax
2. **After implementing a function**: Test with simple inputs immediately
3. **After creating CLI**: `timeout 5 python script.py --help` to verify it loads
4. **Always use timeouts**: DDS operations can hang indefinitely

```bash
# Test pattern - verify each step before proceeding
timeout 5 python -c "from my_subscriber import create_type; print(create_type())"
timeout 5 python subscriber.py --help
timeout 30 python subscriber.py --domain 99 --timeout 10
```

### Todo-Driven Testing

If using a todo list, **every completed todo must have a verification test**:

```
TODO: Create type definition
  → Write code
  → TEST: timeout 5 python -c "from subscriber import create_type; print(create_type())"

TODO: Implement async reader  
  → Write code
  → TEST: timeout 5 python -c "from subscriber import run_subscriber; print('imports OK')"

TODO: Add CLI interface
  → Write code
  → TEST: timeout 5 python subscriber.py --help

TODO: Full integration
  → TEST: timeout 30 python subscriber.py --domain 99 --count 5 --timeout 20
```

## Mandatory Requirements (Unless Explicitly Overridden)

1. **Asynchronous Callbacks**: Use WaitSet with on_data_available pattern
   - DO NOT use polling loops
   - Use `dds.StatusCondition` and `dds.WaitSet`
   - Call `reader.take()` only when data is available

2. **External QoS Configuration**: Load QoS from XML file
   - Use `dds.QosProvider(qos_file)` to load QoS
   - Apply QoS to participant, reader via provider
   - DO NOT hardcode QoS settings in code

3. **Timeout Protection**: All wait operations must have timeouts
   - Use `waitset.wait(dds.Duration.from_seconds(timeout))`
   - Never wait indefinitely

4. **Domain ID**: Accept as parameter, use safe range (50-99) for defaults

## Template Pattern

```python
import rti.connextdds as dds
import time

def run_subscriber(domain_id: int, qos_file: str, timeout: float):
    # Load external QoS
    qos_provider = dds.QosProvider(qos_file)
    
    # Create participant with QoS from provider
    participant = dds.DomainParticipant(domain_id, qos_provider.participant_qos)
    
    # Create type (define your type here)
    my_type = dds.StructType("MyType")
    my_type.add_member(dds.Member("field", dds.Int32Type()))
    
    # Create topic, subscriber, reader
    topic = dds.DynamicData.Topic(participant, "MyTopic", my_type)
    subscriber = dds.Subscriber(participant)
    reader = dds.DynamicData.DataReader(subscriber, topic, qos_provider.datareader_qos)
    
    # Set up async notification (NOT polling)
    status_condition = dds.StatusCondition(reader)
    status_condition.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
    waitset = dds.WaitSet()
    waitset.attach_condition(status_condition)
    
    # Wait loop with timeout
    start = time.time()
    while time.time() - start < timeout:
        conditions = waitset.wait(dds.Duration.from_seconds(1.0))
        if status_condition in conditions:
            samples = reader.take()
            for sample in samples:
                if sample.info.valid:
                    # Process sample
                    process(sample.data)
```

## Verification Checklist

- [ ] No `while True: reader.take()` polling patterns
- [ ] `QosProvider` used to load external QoS
- [ ] `WaitSet` and `StatusCondition` used for async wait
- [ ] All wait calls have explicit timeout
- [ ] Domain ID is parameterized
- [ ] Proper error handling and cleanup

## Output Format

If outputting received samples, use JSONL format:
```json
{"topic": "TopicName", "sample_count": 1, "data": {"field": "value"}}
```


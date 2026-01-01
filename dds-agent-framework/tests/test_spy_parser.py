"""Tests for the rtiddsspy output parser."""

import pytest
from dds_tools.core.spy_parser import SpyParser, SpySample, parse_spy_output


class TestSpyParser:
    """Tests for SpyParser class."""

    def test_parse_simple_sample(self) -> None:
        """Test parsing a simple sample with basic fields."""
        text = '''Sample received, count 1, topic "HelloWorld"
    message: "Hello DDS World"
    count: 42
'''
        parser = SpyParser()
        samples = parser.parse_output(text)

        assert len(samples) == 1
        sample = samples[0]
        assert sample.topic == "HelloWorld"
        assert sample.sample_count == 1
        assert sample.data["message"] == "Hello DDS World"
        assert sample.data["count"] == 42

    def test_parse_multiple_samples(self) -> None:
        """Test parsing multiple samples."""
        text = '''Sample received, count 1, topic "Test"
    value: 100
Sample received, count 2, topic "Test"
    value: 200
Sample received, count 3, topic "Test"
    value: 300
'''
        samples = parse_spy_output(text)

        assert len(samples) == 3
        assert samples[0].sample_count == 1
        assert samples[0].data["value"] == 100
        assert samples[1].sample_count == 2
        assert samples[1].data["value"] == 200
        assert samples[2].sample_count == 3
        assert samples[2].data["value"] == 300

    def test_parse_numeric_types(self) -> None:
        """Test parsing various numeric types."""
        text = '''Sample received, count 1, topic "Numbers"
    int_val: 42
    negative_int: -17
    float_val: 3.14159
    negative_float: -273.15
    scientific: 1.23e-4
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert data["int_val"] == 42
        assert data["negative_int"] == -17
        assert abs(data["float_val"] - 3.14159) < 1e-6
        assert abs(data["negative_float"] - (-273.15)) < 1e-6
        assert abs(data["scientific"] - 1.23e-4) < 1e-10

    def test_parse_boolean_values(self) -> None:
        """Test parsing boolean values."""
        text = '''Sample received, count 1, topic "Booleans"
    is_active: true
    is_disabled: false
    is_enabled: True
    is_off: False
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert data["is_active"] is True
        assert data["is_disabled"] is False
        assert data["is_enabled"] is True
        assert data["is_off"] is False

    def test_parse_nested_struct(self) -> None:
        """Test parsing nested structures."""
        text = '''Sample received, count 1, topic "Nested"
    outer_field: 1
    inner:
        inner_field: 2
        deep:
            deepest_field: 3
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert data["outer_field"] == 1
        assert data["inner"]["inner_field"] == 2
        assert data["inner"]["deep"]["deepest_field"] == 3

    def test_parse_simple_array(self) -> None:
        """Test parsing simple arrays."""
        text = '''Sample received, count 1, topic "Arrays"
    values:
        [0]: 10
        [1]: 20
        [2]: 30
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert data["values"] == [10, 20, 30]

    def test_parse_array_of_structs(self) -> None:
        """Test parsing arrays of structures."""
        text = '''Sample received, count 1, topic "StructArray"
    items:
        [0]:
            name: "first"
            value: 1
        [1]:
            name: "second"
            value: 2
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "first"
        assert data["items"][0]["value"] == 1
        assert data["items"][1]["name"] == "second"
        assert data["items"][1]["value"] == 2

    def test_parse_hex_values(self) -> None:
        """Test parsing hexadecimal values."""
        text = '''Sample received, count 1, topic "Hex"
    address: 0xDEADBEEF
    small: 0xFF
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        data = samples[0].data
        assert data["address"] == 0xDEADBEEF
        assert data["small"] == 0xFF

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        sample = SpySample(
            topic="Test",
            sample_count=1,
            data={"message": "hello", "value": 42},
        )

        json_str = sample.to_json()
        assert '"topic": "Test"' in json_str
        assert '"sample_count": 1' in json_str
        assert '"message": "hello"' in json_str
        assert '"value": 42' in json_str

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        sample = SpySample(
            topic="Test",
            sample_count=1,
            data={"key": "value"},
        )

        d = sample.to_dict()
        assert d["topic"] == "Test"
        assert d["sample_count"] == 1
        assert d["data"]["key"] == "value"

    def test_streaming_parse(self) -> None:
        """Test line-by-line streaming parsing."""
        lines = [
            'Sample received, count 1, topic "Stream"',
            "    field1: 100",
            "    field2: 200",
            'Sample received, count 2, topic "Stream"',
            "    field1: 300",
        ]

        parser = SpyParser()
        samples = []

        for line in lines:
            result = parser.parse_line(line)
            if result:
                samples.append(result)

        # Flush the last sample
        final = parser.flush()
        if final:
            samples.append(final)

        assert len(samples) == 2
        assert samples[0].data["field1"] == 100
        assert samples[1].data["field1"] == 300

    def test_empty_input(self) -> None:
        """Test parsing empty input."""
        samples = parse_spy_output("")
        assert samples == []

    def test_no_samples(self) -> None:
        """Test parsing text with no samples."""
        text = "Some random text\nNo samples here\n"
        samples = parse_spy_output(text)
        assert samples == []

    def test_different_topics(self) -> None:
        """Test parsing samples from different topics."""
        text = '''Sample received, count 1, topic "TopicA"
    a_field: 1
Sample received, count 1, topic "TopicB"
    b_field: 2
'''
        samples = parse_spy_output(text)

        assert len(samples) == 2
        assert samples[0].topic == "TopicA"
        assert samples[1].topic == "TopicB"

    def test_rtiddsspy_7x_format(self) -> None:
        """Test parsing rtiddsspy 7.x 'New data' format."""
        text = '''RTI Connext DDS Spy built with DDS version: 7.3.0.5
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
rtiddsspy is listening for data, press CTRL+C to stop it.

19:49:58 New writer        from 192.168.1.12    : topic="HelloWorld" type="HelloWorld"
19:49:59 New data          from 192.168.1.12    : topic="HelloWorld" type="HelloWorld"
message: "Hello DDS World #1"
count: 1
timestamp: 1767296998.580184

19:49:59 New data          from 192.168.1.12    : topic="HelloWorld" type="HelloWorld"
message: "Hello DDS World #2"
count: 2
timestamp: 1767296999.0884411

19:50:00 No writers        from 192.168.1.12    : topic="HelloWorld" type="HelloWorld"
19:50:00 Deleted writer    from 192.168.1.12    : topic="HelloWorld" type="HelloWorld"
'''
        samples = parse_spy_output(text)

        assert len(samples) == 2
        assert samples[0].topic == "HelloWorld"
        assert samples[0].data["message"] == "Hello DDS World #1"
        assert samples[0].data["count"] == 1
        assert samples[1].data["message"] == "Hello DDS World #2"
        assert samples[1].data["count"] == 2

    def test_rtiddsspy_7x_nested_data(self) -> None:
        """Test parsing nested data in rtiddsspy 7.x format."""
        text = '''19:50:00 New data          from 192.168.1.12    : topic="Vehicle" type="Vehicle"
id: 123
position:
    x: 100.5
    y: 200.0
velocity: 25.5

'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        assert samples[0].topic == "Vehicle"
        assert samples[0].data["id"] == 123
        assert samples[0].data["position"]["x"] == 100.5
        assert samples[0].data["velocity"] == 25.5


"""Integration tests for the DDS tools workflow.

These tests verify the end-to-end workflow:
1. Spy parser correctly parses rtiddsspy output
2. Sample comparator correctly compares JSONL files
3. Process manager correctly handles processes
4. The overall workflow functions correctly
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from dds_tools.core.spy_parser import SpyParser, parse_spy_output
from dds_tools.core.sample_comparator import SampleComparator, compare_sample_files
from dds_tools.core.process_manager import ProcessManager, ProcessStatus
from dds_tools.core.port_utils import (
    calculate_rtps_ports,
    validate_domain_id,
    get_safe_domain_id,
)
from dds_tools.config.test_config import load_test_config


class TestSpyParserIntegration:
    """Integration tests for spy parser with realistic data."""

    def test_parse_complex_sample(self) -> None:
        """Test parsing a complex nested sample."""
        text = '''Sample received, count 1, topic "Vehicle_Kinematics"
    vehicle_id: 12345
    position:
        x: 100.5
        y: 200.75
        z: 50.25
    velocity:
        vx: 10.0
        vy: 5.0
        vz: 0.0
    orientation:
        roll: 0.1
        pitch: 0.2
        yaw: 3.14159
    timestamp: 1735600000.123
Sample received, count 2, topic "Vehicle_Kinematics"
    vehicle_id: 12345
    position:
        x: 110.5
        y: 205.75
        z: 50.25
    velocity:
        vx: 10.0
        vy: 5.0
        vz: 0.0
    orientation:
        roll: 0.1
        pitch: 0.2
        yaw: 3.14159
    timestamp: 1735600000.223
'''
        samples = parse_spy_output(text)

        assert len(samples) == 2

        # Check first sample
        s1 = samples[0]
        assert s1.topic == "Vehicle_Kinematics"
        assert s1.sample_count == 1
        assert s1.data["vehicle_id"] == 12345
        assert s1.data["position"]["x"] == 100.5
        assert s1.data["velocity"]["vx"] == 10.0
        assert abs(s1.data["orientation"]["yaw"] - 3.14159) < 1e-6

        # Check second sample
        s2 = samples[1]
        assert s2.sample_count == 2
        assert s2.data["position"]["x"] == 110.5

    def test_parse_with_arrays(self) -> None:
        """Test parsing samples with arrays."""
        text = '''Sample received, count 1, topic "SensorData"
    sensor_id: 42
    readings:
        [0]: 1.0
        [1]: 2.0
        [2]: 3.0
        [3]: 4.0
        [4]: 5.0
    metadata:
        name: "temperature"
        unit: "celsius"
'''
        samples = parse_spy_output(text)

        assert len(samples) == 1
        s = samples[0]
        assert s.data["sensor_id"] == 42
        assert s.data["readings"] == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert s.data["metadata"]["name"] == "temperature"


class TestSampleComparatorIntegration:
    """Integration tests for sample comparator."""

    def test_vehicle_telemetry_comparison(self, tmp_path: Path) -> None:
        """Test comparing vehicle telemetry samples."""
        actual = [
            {
                "topic": "Vehicle",
                "sample_count": 1,
                "data": {
                    "id": 1,
                    "position": {"x": 100.0000001, "y": 200.0, "z": 50.0},
                    "speed": 25.5,
                },
            },
            {
                "topic": "Vehicle",
                "sample_count": 2,
                "data": {
                    "id": 1,
                    "position": {"x": 110.0, "y": 205.0, "z": 50.0},
                    "speed": 26.0,
                },
            },
        ]

        expected = [
            {
                "topic": "Vehicle",
                "sample_count": 1,
                "data": {
                    "id": 1,
                    "position": {"x": 100.0, "y": 200.0, "z": 50.0},
                    "speed": 25.5,
                },
            },
            {
                "topic": "Vehicle",
                "sample_count": 2,
                "data": {
                    "id": 1,
                    "position": {"x": 110.0, "y": 205.0, "z": 50.0},
                    "speed": 26.0,
                },
            },
        ]

        # Write files
        actual_file = tmp_path / "actual.jsonl"
        expected_file = tmp_path / "expected.jsonl"

        with open(actual_file, "w") as f:
            for s in actual:
                f.write(json.dumps(s) + "\n")

        with open(expected_file, "w") as f:
            for s in expected:
                f.write(json.dumps(s) + "\n")

        # Compare with tolerance
        result = compare_sample_files(
            actual_file, expected_file, float_tolerance=1e-5
        )

        assert result.passed
        assert result.matched_count == 2


@pytest.mark.timeout(5)
class TestProcessManagerIntegration:
    """Integration tests for process manager."""

    def test_run_short_process(self) -> None:
        """Test running a short process to completion."""
        import sys

        manager = ProcessManager()

        try:
            # Run a simple Python script
            info = manager.start_process(
                name="short_test",
                command=[
                    sys.executable, "-c",
                    "import time; print('start'); time.sleep(0.2); print('end')"
                ],
                timeout=3,
            )

            assert info.status == ProcessStatus.RUNNING

            # Wait for completion
            time.sleep(0.5)

            info = manager.check_process("short_test")
            assert info is not None
            assert info.status == ProcessStatus.COMPLETED
            assert info.exit_code == 0

            # Check output
            output = manager.get_output("short_test")
            assert output is not None
            stdout, _ = output
            assert "start" in stdout
            assert "end" in stdout

        finally:
            manager.cleanup()

    def test_process_with_args(self) -> None:
        """Test process with command-line arguments."""
        import sys

        manager = ProcessManager()

        try:
            info = manager.start_process(
                name="args_test",
                command=[
                    sys.executable, "-c",
                    "import sys; print(' '.join(sys.argv[1:]))",
                    "arg1", "arg2", "arg3"
                ],
                timeout=3,
            )

            time.sleep(0.3)

            output = manager.get_output("args_test")
            assert output is not None
            stdout, _ = output
            assert "arg1 arg2 arg3" in " ".join(stdout)

        finally:
            manager.cleanup()


class TestPortUtilsIntegration:
    """Integration tests for port utilities."""

    def test_rtps_port_calculation(self) -> None:
        """Test RTPS port calculation matches expected formula."""
        # Domain 0
        ports = calculate_rtps_ports(0, 0)
        assert ports.discovery_multicast == 7400
        assert ports.discovery_unicast == 7410
        assert ports.user_multicast == 7401
        assert ports.user_unicast == 7411

        # Domain 1
        ports = calculate_rtps_ports(1, 0)
        assert ports.discovery_multicast == 7650
        assert ports.discovery_unicast == 7660

        # Domain with participant ID
        ports = calculate_rtps_ports(0, 1)
        assert ports.discovery_unicast == 7412  # 7410 + 2*1

    def test_domain_validation(self) -> None:
        """Test domain ID validation."""
        # Valid domains
        valid, _ = validate_domain_id(0)
        assert valid

        valid, _ = validate_domain_id(100)
        assert valid

        # Domain 232 may fail validation with max participant IDs
        # Domain 200 should always be safe
        valid, _ = validate_domain_id(200)
        assert valid

        # Invalid domains
        valid, msg = validate_domain_id(-1)
        assert not valid
        assert "negative" in msg.lower()

        valid, msg = validate_domain_id(250)
        assert not valid
        assert "too high" in msg.lower() or "invalid port" in msg.lower()

    def test_get_safe_domain(self) -> None:
        """Test getting a safe domain ID."""
        domain_id = get_safe_domain_id()

        assert 50 <= domain_id <= 99
        valid, _ = validate_domain_id(domain_id)
        assert valid


class TestConfigLoading:
    """Tests for loading test configuration files."""

    def test_load_example_config(self, tmp_path: Path) -> None:
        """Test loading a sample configuration file."""
        config_content = """
tests:
  basic_test:
    description: "A basic test"
    publisher:
      command: ["python", "publisher.py", "--domain", "{DOMAIN_ID}"]
      startup_delay: 1.0
      timeout: 30.0
    spy:
      topics: "TestTopic"
      timeout: 10.0
    validation:
      expected_output: "expected.jsonl"
      min_samples: 5
      float_tolerance: 0.001
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_test_config(config_file)

        assert "basic_test" in config.tests
        test = config.tests["basic_test"]
        assert test.description == "A basic test"
        assert test.publisher.startup_delay == 1.0
        assert test.spy.topics == "TestTopic"
        assert test.validation.min_samples == 5


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_spy_to_compare_workflow(self, tmp_path: Path) -> None:
        """Test the workflow from spy output to comparison."""
        # Simulate rtiddsspy output
        spy_output = '''Sample received, count 1, topic "Test"
    value: 100
    name: "first"
Sample received, count 2, topic "Test"
    value: 200
    name: "second"
'''
        # Parse spy output
        samples = parse_spy_output(spy_output)
        assert len(samples) == 2

        # Write to JSONL file
        actual_file = tmp_path / "actual.jsonl"
        with open(actual_file, "w") as f:
            for sample in samples:
                f.write(sample.to_json() + "\n")

        # Create expected output
        expected_file = tmp_path / "expected.jsonl"
        expected = [
            {"topic": "Test", "sample_count": 1, "data": {"value": 100, "name": "first"}},
            {"topic": "Test", "sample_count": 2, "data": {"value": 200, "name": "second"}},
        ]
        with open(expected_file, "w") as f:
            for s in expected:
                f.write(json.dumps(s) + "\n")

        # Compare
        result = compare_sample_files(actual_file, expected_file)
        assert result.passed
        assert result.matched_count == 2

    @pytest.mark.timeout(5)
    def test_full_tool_workflow(self, tmp_path: Path) -> None:
        """Test the full tool workflow with process management."""
        import sys

        manager = ProcessManager()

        try:
            # Start a "publisher" that outputs to a file
            output_file = tmp_path / "output.txt"
            script = f'''
import json
import time

samples = [
    {{"topic": "Test", "sample_count": 1, "data": {{"value": 1}}}},
    {{"topic": "Test", "sample_count": 2, "data": {{"value": 2}}}},
]

with open("{output_file}", "w") as f:
    for s in samples:
        f.write(json.dumps(s) + "\\n")
        time.sleep(0.05)

print("Done")
'''
            script_file = tmp_path / "test_pub.py"
            script_file.write_text(script)

            info = manager.start_process(
                name="test_publisher",
                command=[sys.executable, str(script_file)],
                timeout=3,
            )

            # Wait for completion
            time.sleep(0.5)

            info = manager.check_process("test_publisher")
            assert info is not None
            assert info.status == ProcessStatus.COMPLETED

            # Verify output was written
            assert output_file.exists()
            lines = output_file.read_text().strip().split("\n")
            assert len(lines) == 2

            # Parse as JSON
            samples = [json.loads(line) for line in lines]
            assert samples[0]["data"]["value"] == 1
            assert samples[1]["data"]["value"] == 2

        finally:
            manager.cleanup()

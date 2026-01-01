"""Tests for the sample comparator."""

import json
import tempfile
from pathlib import Path

import pytest
from dds_tools.core.sample_comparator import (
    SampleComparator,
    ComparisonResult,
    compare_sample_files,
)


class TestSampleComparator:
    """Tests for SampleComparator class."""

    def test_identical_samples_pass(self) -> None:
        """Test that identical samples pass comparison."""
        actual = [{"topic": "Test", "data": {"value": 42}}]
        expected = [{"topic": "Test", "data": {"value": 42}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)

        assert result.passed
        assert result.matched_count == 1
        assert result.mismatches == []

    def test_different_values_fail(self) -> None:
        """Test that different values cause failure."""
        actual = [{"topic": "Test", "data": {"value": 42}}]
        expected = [{"topic": "Test", "data": {"value": 43}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)

        assert not result.passed
        assert result.matched_count == 0
        assert len(result.mismatches) == 1

    def test_float_tolerance(self) -> None:
        """Test float comparison with tolerance."""
        actual = [{"topic": "Test", "data": {"value": 3.14159265}}]
        expected = [{"topic": "Test", "data": {"value": 3.14159266}}]

        # Should fail with tight tolerance
        comparator = SampleComparator(float_tolerance=1e-10)
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

        # Should pass with looser tolerance
        comparator = SampleComparator(float_tolerance=1e-6)
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_missing_field(self) -> None:
        """Test detection of missing fields."""
        actual = [{"topic": "Test", "data": {"a": 1}}]
        expected = [{"topic": "Test", "data": {"a": 1, "b": 2}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)

        assert not result.passed
        assert any("missing" in m.message.lower() for fm in result.mismatches 
                   for m in fm.field_mismatches)

    def test_extra_field(self) -> None:
        """Test detection of extra fields."""
        actual = [{"topic": "Test", "data": {"a": 1, "b": 2}}]
        expected = [{"topic": "Test", "data": {"a": 1}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)

        assert not result.passed

    def test_count_mismatch(self) -> None:
        """Test detection of sample count mismatch."""
        actual = [{"topic": "Test", "data": {"value": 1}}]
        expected = [
            {"topic": "Test", "data": {"value": 1}},
            {"topic": "Test", "data": {"value": 2}},
        ]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)

        assert not result.passed
        assert result.actual_count == 1
        assert result.expected_count == 2

    def test_ignore_fields(self) -> None:
        """Test ignoring specific fields."""
        actual = [{"topic": "Test", "timestamp": 100, "data": {"value": 42}}]
        expected = [{"topic": "Test", "timestamp": 200, "data": {"value": 42}}]

        # Should fail without ignore
        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

        # Should pass with ignore
        comparator = SampleComparator(ignore_fields=["timestamp"])
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_nested_field_ignore(self) -> None:
        """Test ignoring nested fields."""
        actual = [{"topic": "Test", "data": {"seq": 1, "value": 42}}]
        expected = [{"topic": "Test", "data": {"seq": 2, "value": 42}}]

        comparator = SampleComparator(ignore_fields=["data.seq"])
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_order_independent(self) -> None:
        """Test order-independent comparison."""
        actual = [
            {"topic": "Test", "data": {"id": 1}},
            {"topic": "Test", "data": {"id": 2}},
        ]
        expected = [
            {"topic": "Test", "data": {"id": 2}},
            {"topic": "Test", "data": {"id": 1}},
        ]

        # Should fail with ordered comparison
        comparator = SampleComparator(order_independent=False)
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

        # Should pass with order-independent comparison
        comparator = SampleComparator(order_independent=True)
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_nested_dict_comparison(self) -> None:
        """Test comparison of nested dictionaries."""
        actual = [{"topic": "Test", "data": {"outer": {"inner": {"deep": 42}}}}]
        expected = [{"topic": "Test", "data": {"outer": {"inner": {"deep": 42}}}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_list_comparison(self) -> None:
        """Test comparison of lists."""
        actual = [{"topic": "Test", "data": {"values": [1, 2, 3]}}]
        expected = [{"topic": "Test", "data": {"values": [1, 2, 3]}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_list_mismatch(self) -> None:
        """Test detection of list mismatches."""
        actual = [{"topic": "Test", "data": {"values": [1, 2, 3]}}]
        expected = [{"topic": "Test", "data": {"values": [1, 2, 4]}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

    def test_list_length_mismatch(self) -> None:
        """Test detection of list length mismatches."""
        actual = [{"topic": "Test", "data": {"values": [1, 2]}}]
        expected = [{"topic": "Test", "data": {"values": [1, 2, 3]}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

    def test_type_mismatch(self) -> None:
        """Test detection of type mismatches."""
        actual = [{"topic": "Test", "data": {"value": "42"}}]
        expected = [{"topic": "Test", "data": {"value": 42}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert not result.passed

    def test_int_float_compatible(self) -> None:
        """Test that int and float are compatible in comparison."""
        actual = [{"topic": "Test", "data": {"value": 42}}]
        expected = [{"topic": "Test", "data": {"value": 42.0}}]

        comparator = SampleComparator()
        result = comparator.compare_samples(actual, expected)
        assert result.passed

    def test_compare_files(self, tmp_path: Path) -> None:
        """Test comparing JSONL files."""
        actual_file = tmp_path / "actual.jsonl"
        expected_file = tmp_path / "expected.jsonl"

        actual_file.write_text(
            '{"topic": "Test", "data": {"value": 42}}\n'
            '{"topic": "Test", "data": {"value": 43}}\n'
        )
        expected_file.write_text(
            '{"topic": "Test", "data": {"value": 42}}\n'
            '{"topic": "Test", "data": {"value": 43}}\n'
        )

        result = compare_sample_files(actual_file, expected_file)
        assert result.passed

    def test_compare_files_missing_actual(self, tmp_path: Path) -> None:
        """Test error handling for missing actual file."""
        expected_file = tmp_path / "expected.jsonl"
        expected_file.write_text('{"topic": "Test"}\n')

        result = compare_sample_files(
            tmp_path / "nonexistent.jsonl", expected_file
        )
        assert not result.passed
        assert result.error is not None

    def test_compare_files_invalid_json(self, tmp_path: Path) -> None:
        """Test error handling for invalid JSON."""
        actual_file = tmp_path / "actual.jsonl"
        expected_file = tmp_path / "expected.jsonl"

        actual_file.write_text("not valid json\n")
        expected_file.write_text('{"topic": "Test"}\n')

        result = compare_sample_files(actual_file, expected_file)
        assert not result.passed
        assert result.error is not None

    def test_empty_files_pass(self, tmp_path: Path) -> None:
        """Test that empty files pass comparison."""
        actual_file = tmp_path / "actual.jsonl"
        expected_file = tmp_path / "expected.jsonl"

        actual_file.write_text("")
        expected_file.write_text("")

        result = compare_sample_files(actual_file, expected_file)
        assert result.passed
        assert result.actual_count == 0
        assert result.expected_count == 0

    def test_result_to_json(self) -> None:
        """Test JSON serialization of results."""
        result = ComparisonResult(
            passed=True,
            actual_count=10,
            expected_count=10,
            matched_count=10,
        )

        json_str = result.to_json()
        parsed = json.loads(json_str)

        assert parsed["passed"] is True
        assert parsed["actual_count"] == 10
        assert parsed["matched_count"] == 10


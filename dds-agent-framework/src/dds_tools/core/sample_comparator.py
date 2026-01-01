"""JSONL sample comparison with float tolerance.

This module compares DDS samples captured in JSONL format against expected
output, with configurable float tolerance for numerical comparisons.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FieldMismatch:
    """A single field mismatch between actual and expected."""

    path: str
    actual: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "actual": self.actual,
            "expected": self.expected,
            "message": self.message,
        }


@dataclass
class SampleMismatch:
    """A mismatch at the sample level."""

    index: int
    field_mismatches: list[FieldMismatch] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "message": self.message,
            "field_mismatches": [fm.to_dict() for fm in self.field_mismatches],
        }


@dataclass
class ComparisonResult:
    """Result of comparing actual vs expected samples."""

    passed: bool
    actual_count: int
    expected_count: int
    matched_count: int
    mismatches: list[SampleMismatch] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "actual_count": self.actual_count,
            "expected_count": self.expected_count,
            "matched_count": self.matched_count,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "error": self.error,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class SampleComparator:
    """Compares DDS samples with configurable tolerance.

    This class compares JSONL files containing DDS samples and reports
    any mismatches, with special handling for floating-point comparisons.

    Example:
        comparator = SampleComparator(float_tolerance=1e-6)
        result = comparator.compare_files("actual.jsonl", "expected.jsonl")
        if not result.passed:
            for mismatch in result.mismatches:
                print(f"Sample {mismatch.index}: {mismatch.message}")
    """

    def __init__(
        self,
        float_tolerance: float = 1e-6,
        ignore_fields: list[str] | None = None,
        order_independent: bool = False,
    ) -> None:
        """Initialize the comparator.

        Args:
            float_tolerance: Tolerance for float comparisons.
            ignore_fields: List of field paths to ignore (e.g., ["timestamp", "data.seq"]).
            order_independent: If True, compare samples regardless of order.
        """
        self.float_tolerance = float_tolerance
        self.ignore_fields = set(ignore_fields or [])
        self.order_independent = order_independent

    def compare_files(
        self, actual_path: str | Path, expected_path: str | Path
    ) -> ComparisonResult:
        """Compare two JSONL files.

        Args:
            actual_path: Path to the actual output file.
            expected_path: Path to the expected output file.

        Returns:
            ComparisonResult with detailed mismatch information.
        """
        actual_path = Path(actual_path)
        expected_path = Path(expected_path)

        # Load samples
        try:
            actual_samples = self._load_jsonl(actual_path)
        except Exception as e:
            return ComparisonResult(
                passed=False,
                actual_count=0,
                expected_count=0,
                matched_count=0,
                error=f"Failed to load actual file: {e}",
            )

        try:
            expected_samples = self._load_jsonl(expected_path)
        except Exception as e:
            return ComparisonResult(
                passed=False,
                actual_count=len(actual_samples),
                expected_count=0,
                matched_count=0,
                error=f"Failed to load expected file: {e}",
            )

        return self.compare_samples(actual_samples, expected_samples)

    def compare_samples(
        self, actual: list[dict], expected: list[dict]
    ) -> ComparisonResult:
        """Compare two lists of samples.

        Args:
            actual: List of actual sample dictionaries.
            expected: List of expected sample dictionaries.

        Returns:
            ComparisonResult with detailed mismatch information.
        """
        if self.order_independent:
            return self._compare_order_independent(actual, expected)
        else:
            return self._compare_ordered(actual, expected)

    def _compare_ordered(
        self, actual: list[dict], expected: list[dict]
    ) -> ComparisonResult:
        """Compare samples in order."""
        mismatches: list[SampleMismatch] = []
        matched_count = 0

        # Check count mismatch
        if len(actual) != len(expected):
            mismatches.append(
                SampleMismatch(
                    index=-1,
                    message=f"Sample count mismatch: {len(actual)} actual vs {len(expected)} expected",
                )
            )

        # Compare each sample
        for i in range(min(len(actual), len(expected))):
            field_mismatches = self._compare_dicts(actual[i], expected[i], "")
            if field_mismatches:
                mismatches.append(
                    SampleMismatch(
                        index=i,
                        field_mismatches=field_mismatches,
                        message=f"Sample {i} has {len(field_mismatches)} field mismatch(es)",
                    )
                )
            else:
                matched_count += 1

        # Report missing samples
        if len(actual) < len(expected):
            for i in range(len(actual), len(expected)):
                mismatches.append(
                    SampleMismatch(
                        index=i, message=f"Missing sample {i} in actual output"
                    )
                )
        elif len(actual) > len(expected):
            for i in range(len(expected), len(actual)):
                mismatches.append(
                    SampleMismatch(
                        index=i, message=f"Extra sample {i} in actual output"
                    )
                )

        return ComparisonResult(
            passed=len(mismatches) == 0,
            actual_count=len(actual),
            expected_count=len(expected),
            matched_count=matched_count,
            mismatches=mismatches,
        )

    def _compare_order_independent(
        self, actual: list[dict], expected: list[dict]
    ) -> ComparisonResult:
        """Compare samples regardless of order using content hashing."""
        # Hash each sample
        actual_hashes = {self._hash_sample(s): (i, s) for i, s in enumerate(actual)}
        expected_hashes = {self._hash_sample(s): (i, s) for i, s in enumerate(expected)}

        mismatches: list[SampleMismatch] = []
        matched_count = 0

        # Find unmatched expected samples
        for hash_val, (exp_idx, exp_sample) in expected_hashes.items():
            if hash_val in actual_hashes:
                matched_count += 1
            else:
                # Find closest match for better error reporting
                mismatches.append(
                    SampleMismatch(
                        index=exp_idx,
                        message=f"Expected sample {exp_idx} not found in actual output",
                    )
                )

        # Find extra actual samples
        for hash_val, (act_idx, act_sample) in actual_hashes.items():
            if hash_val not in expected_hashes:
                mismatches.append(
                    SampleMismatch(
                        index=act_idx,
                        message=f"Actual sample {act_idx} not in expected output",
                    )
                )

        return ComparisonResult(
            passed=len(mismatches) == 0,
            actual_count=len(actual),
            expected_count=len(expected),
            matched_count=matched_count,
            mismatches=mismatches,
        )

    def _compare_dicts(
        self, actual: dict, expected: dict, path_prefix: str
    ) -> list[FieldMismatch]:
        """Compare two dictionaries recursively."""
        mismatches: list[FieldMismatch] = []

        all_keys = set(actual.keys()) | set(expected.keys())

        for key in all_keys:
            path = f"{path_prefix}.{key}" if path_prefix else key

            # Skip ignored fields
            if path in self.ignore_fields:
                continue

            if key not in actual:
                mismatches.append(
                    FieldMismatch(
                        path=path,
                        actual=None,
                        expected=expected[key],
                        message="Field missing in actual",
                    )
                )
            elif key not in expected:
                mismatches.append(
                    FieldMismatch(
                        path=path,
                        actual=actual[key],
                        expected=None,
                        message="Extra field in actual",
                    )
                )
            else:
                field_mismatches = self._compare_values(
                    actual[key], expected[key], path
                )
                mismatches.extend(field_mismatches)

        return mismatches

    def _compare_values(
        self, actual: Any, expected: Any, path: str
    ) -> list[FieldMismatch]:
        """Compare two values."""
        mismatches: list[FieldMismatch] = []

        # Handle None
        if actual is None and expected is None:
            return []
        if actual is None or expected is None:
            mismatches.append(
                FieldMismatch(
                    path=path,
                    actual=actual,
                    expected=expected,
                    message="One value is None",
                )
            )
            return mismatches

        # Handle type mismatch (but allow int/float mixing)
        if type(actual) != type(expected):
            if not (
                isinstance(actual, (int, float)) and isinstance(expected, (int, float))
            ):
                mismatches.append(
                    FieldMismatch(
                        path=path,
                        actual=actual,
                        expected=expected,
                        message=f"Type mismatch: {type(actual).__name__} vs {type(expected).__name__}",
                    )
                )
                return mismatches

        # Handle nested dicts
        if isinstance(expected, dict):
            return self._compare_dicts(actual, expected, path)

        # Handle lists
        if isinstance(expected, list):
            return self._compare_lists(actual, expected, path)

        # Handle floats with tolerance
        if isinstance(expected, float) or isinstance(actual, float):
            if abs(float(actual) - float(expected)) > self.float_tolerance:
                mismatches.append(
                    FieldMismatch(
                        path=path,
                        actual=actual,
                        expected=expected,
                        message=f"Float mismatch (tolerance={self.float_tolerance})",
                    )
                )
            return mismatches

        # Direct comparison for other types
        if actual != expected:
            mismatches.append(
                FieldMismatch(
                    path=path,
                    actual=actual,
                    expected=expected,
                    message="Value mismatch",
                )
            )

        return mismatches

    def _compare_lists(
        self, actual: list, expected: list, path: str
    ) -> list[FieldMismatch]:
        """Compare two lists."""
        mismatches: list[FieldMismatch] = []

        if len(actual) != len(expected):
            mismatches.append(
                FieldMismatch(
                    path=path,
                    actual=len(actual),
                    expected=len(expected),
                    message="List length mismatch",
                )
            )

        for i in range(min(len(actual), len(expected))):
            element_path = f"{path}[{i}]"
            element_mismatches = self._compare_values(
                actual[i], expected[i], element_path
            )
            mismatches.extend(element_mismatches)

        return mismatches

    def _hash_sample(self, sample: dict) -> str:
        """Create a content hash for a sample, ignoring ignored fields."""
        filtered = self._filter_ignored(sample, "")
        canonical = json.dumps(filtered, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _filter_ignored(self, obj: Any, path: str) -> Any:
        """Recursively filter out ignored fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if new_path not in self.ignore_fields:
                    result[key] = self._filter_ignored(value, new_path)
            return result
        elif isinstance(obj, list):
            return [self._filter_ignored(item, f"{path}[]") for item in obj]
        elif isinstance(obj, float):
            # Round floats for hashing
            return round(obj / self.float_tolerance) * self.float_tolerance
        else:
            return obj

    def _load_jsonl(self, path: Path) -> list[dict]:
        """Load samples from a JSONL file."""
        samples = []
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {line_num}: {e}")
        return samples


def compare_sample_files(
    actual_path: str | Path,
    expected_path: str | Path,
    float_tolerance: float = 1e-6,
    ignore_fields: list[str] | None = None,
    order_independent: bool = False,
) -> ComparisonResult:
    """Convenience function to compare two JSONL files.

    Args:
        actual_path: Path to actual output file.
        expected_path: Path to expected output file.
        float_tolerance: Tolerance for float comparisons.
        ignore_fields: Fields to ignore in comparison.
        order_independent: If True, ignore sample order.

    Returns:
        ComparisonResult with detailed mismatch information.
    """
    comparator = SampleComparator(
        float_tolerance=float_tolerance,
        ignore_fields=ignore_fields,
        order_independent=order_independent,
    )
    return comparator.compare_files(actual_path, expected_path)


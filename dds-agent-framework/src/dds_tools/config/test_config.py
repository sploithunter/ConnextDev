"""Test configuration loading and management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PublisherConfig:
    """Configuration for a publisher in a test."""

    command: list[str]
    startup_delay: float = 2.0
    timeout: float = 60.0


@dataclass
class SpyConfig:
    """Configuration for dds-spy-wrapper in a test."""

    topics: str = "*"
    timeout: float = 30.0


@dataclass
class ValidationConfig:
    """Configuration for test validation."""

    expected_output: str
    min_samples: int = 1
    float_tolerance: float = 1e-6


@dataclass
class TestCase:
    """A single test case configuration."""

    name: str
    description: str
    publisher: PublisherConfig
    spy: SpyConfig
    validation: ValidationConfig


@dataclass
class TestConfig:
    """Root configuration for a test suite."""

    tests: dict[str, TestCase] = field(default_factory=dict)
    domain_id: int | None = None  # If None, auto-select


def load_test_config(config_path: str | Path) -> TestConfig:
    """Load test configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed TestConfig object.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If the config format is invalid.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML dictionary")

    tests: dict[str, TestCase] = {}
    tests_data = data.get("tests", {})

    for name, test_data in tests_data.items():
        tests[name] = _parse_test_case(name, test_data)

    return TestConfig(
        tests=tests,
        domain_id=data.get("domain_id"),
    )


def _parse_test_case(name: str, data: dict[str, Any]) -> TestCase:
    """Parse a single test case from config data."""
    publisher_data = data.get("publisher", {})
    publisher = PublisherConfig(
        command=publisher_data.get("command", []),
        startup_delay=publisher_data.get("startup_delay", 2.0),
        timeout=publisher_data.get("timeout", 60.0),
    )

    spy_data = data.get("spy", {})
    spy = SpyConfig(
        topics=spy_data.get("topics", "*"),
        timeout=spy_data.get("timeout", 30.0),
    )

    validation_data = data.get("validation", {})
    validation = ValidationConfig(
        expected_output=validation_data.get("expected_output", ""),
        min_samples=validation_data.get("min_samples", 1),
        float_tolerance=validation_data.get("float_tolerance", 1e-6),
    )

    return TestCase(
        name=name,
        description=data.get("description", ""),
        publisher=publisher,
        spy=spy,
        validation=validation,
    )


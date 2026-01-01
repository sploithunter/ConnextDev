"""CLI for orchestrating DDS publisher verification tests.

This tool runs complete test workflows that:
1. Start a publisher with monitoring
2. Capture samples using dds-spy-wrapper
3. Compare samples against expected output
4. Report results

Usage:
    dds-test-harness run --config test_config.yaml
    dds-test-harness run --config test_config.yaml --test publisher_only
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from dds_tools.config.test_config import TestConfig, TestCase, load_test_config
from dds_tools.core.process_manager import ProcessManager, ProcessStatus
from dds_tools.core.sample_comparator import SampleComparator
from dds_tools.core.port_utils import get_safe_domain_id, validate_domain_id


@dataclass
class TestResult:
    """Result of a single test run."""

    test_name: str
    passed: bool
    samples_captured: int = 0
    samples_matched: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "samples_captured": self.samples_captured,
            "samples_matched": self.samples_matched,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "details": self.details,
        }


@dataclass
class TestSuiteResult:
    """Result of running a test suite."""

    total: int
    passed: int
    failed: int
    results: list[TestResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict(), indent=2)


def get_rtiddsspy_path() -> Path | None:
    """Get the path to rtiddsspy executable."""
    nddshome = os.environ.get("NDDSHOME")
    if not nddshome:
        return None

    spy_path = Path(nddshome) / "bin" / "rtiddsspy"
    if spy_path.exists():
        return spy_path

    return None


def get_spy_env() -> dict[str, str]:
    """Get environment variables for running rtiddsspy."""
    import platform

    nddshome = os.environ.get("NDDSHOME", "")
    lib_dir = Path(nddshome) / "lib"

    # Find the architecture-specific library directory
    arch_dirs = list(lib_dir.glob("*"))
    if arch_dirs:
        lib_path = str(arch_dirs[0])
    else:
        lib_path = str(lib_dir)

    env = os.environ.copy()

    system = platform.system()
    if system == "Darwin":
        existing = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = f"{lib_path}:{existing}" if existing else lib_path
    else:
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{lib_path}:{existing}" if existing else lib_path

    return env


class TestRunner:
    """Runs DDS verification tests."""

    def __init__(
        self,
        config: TestConfig,
        work_dir: Path | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the test runner.

        Args:
            config: Test configuration.
            work_dir: Working directory for test files.
            verbose: Enable verbose output.
        """
        self.config = config
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="dds_test_"))
        self.verbose = verbose
        self.process_manager = ProcessManager()

    def run_test(self, test_case: TestCase, domain_id: int) -> TestResult:
        """Run a single test case.

        Args:
            test_case: The test case to run.
            domain_id: DDS domain ID to use.

        Returns:
            TestResult with pass/fail status and details.
        """
        start_time = time.time()
        output_file = self.work_dir / f"{test_case.name}_samples.jsonl"

        try:
            # Start the publisher
            if self.verbose:
                click.echo(f"  Starting publisher...")

            pub_command = self._substitute_vars(
                test_case.publisher.command, domain_id
            )
            self.process_manager.start_process(
                name=f"{test_case.name}_publisher",
                command=pub_command,
                timeout=test_case.publisher.timeout,
            )

            # Wait for publisher startup
            time.sleep(test_case.publisher.startup_delay)

            # Check if publisher is still running
            pub_info = self.process_manager.check_process(f"{test_case.name}_publisher")
            if pub_info and not pub_info.is_running:
                # Publisher crashed during startup
                stdout, stderr = self.process_manager.get_output(
                    f"{test_case.name}_publisher"
                ) or ([], [])
                return TestResult(
                    test_name=test_case.name,
                    passed=False,
                    duration_seconds=time.time() - start_time,
                    error=f"Publisher crashed: {pub_info.error_message or 'Unknown error'}",
                    details={
                        "publisher_exit_code": pub_info.exit_code,
                        "stdout": "\n".join(stdout[-20:]),
                        "stderr": "\n".join(stderr[-20:]),
                    },
                )

            # Capture samples using rtiddsspy
            if self.verbose:
                click.echo(f"  Capturing samples...")

            samples_captured = self._capture_samples(
                domain_id=domain_id,
                topics=test_case.spy.topics,
                timeout=test_case.spy.timeout,
                output_file=output_file,
            )

            if samples_captured == 0:
                return TestResult(
                    test_name=test_case.name,
                    passed=False,
                    samples_captured=0,
                    duration_seconds=time.time() - start_time,
                    error="No samples captured",
                )

            # Compare samples
            if self.verbose:
                click.echo(f"  Comparing samples...")

            expected_path = Path(test_case.validation.expected_output)
            if not expected_path.is_absolute():
                # Try relative to config file or work dir
                if not expected_path.exists():
                    expected_path = self.work_dir / expected_path

            if not expected_path.exists():
                return TestResult(
                    test_name=test_case.name,
                    passed=False,
                    samples_captured=samples_captured,
                    duration_seconds=time.time() - start_time,
                    error=f"Expected output file not found: {expected_path}",
                )

            comparator = SampleComparator(
                float_tolerance=test_case.validation.float_tolerance
            )
            comparison = comparator.compare_files(output_file, expected_path)

            # Check minimum samples
            if samples_captured < test_case.validation.min_samples:
                return TestResult(
                    test_name=test_case.name,
                    passed=False,
                    samples_captured=samples_captured,
                    samples_matched=comparison.matched_count,
                    duration_seconds=time.time() - start_time,
                    error=f"Insufficient samples: {samples_captured} < {test_case.validation.min_samples}",
                )

            return TestResult(
                test_name=test_case.name,
                passed=comparison.passed,
                samples_captured=samples_captured,
                samples_matched=comparison.matched_count,
                duration_seconds=time.time() - start_time,
                error=None if comparison.passed else "Sample comparison failed",
                details={
                    "comparison": comparison.to_dict() if not comparison.passed else {},
                },
            )

        except Exception as e:
            return TestResult(
                test_name=test_case.name,
                passed=False,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

        finally:
            # Clean up publisher
            self.process_manager.kill_process(f"{test_case.name}_publisher")

    def run_all(self, test_names: list[str] | None = None) -> TestSuiteResult:
        """Run all tests or specific tests.

        Args:
            test_names: Optional list of test names to run.

        Returns:
            TestSuiteResult with all test results.
        """
        # Select tests to run
        if test_names:
            tests = [
                (name, self.config.tests[name])
                for name in test_names
                if name in self.config.tests
            ]
        else:
            tests = list(self.config.tests.items())

        if not tests:
            return TestSuiteResult(total=0, passed=0, failed=0)

        # Determine domain ID
        if self.config.domain_id is not None:
            domain_id = self.config.domain_id
            valid, msg = validate_domain_id(domain_id)
            if not valid:
                click.secho(f"Warning: {msg}", fg="yellow", err=True)
        else:
            domain_id = get_safe_domain_id()
            if self.verbose:
                click.echo(f"Using domain ID: {domain_id}")

        # Run tests
        results: list[TestResult] = []
        for name, test_case in tests:
            if self.verbose:
                click.echo(f"\nRunning test: {name}")

            result = self.run_test(test_case, domain_id)
            results.append(result)

            if self.verbose:
                if result.passed:
                    click.secho(f"  PASSED ({result.samples_matched} samples)", fg="green")
                else:
                    click.secho(f"  FAILED: {result.error}", fg="red")

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        return TestSuiteResult(
            total=len(results),
            passed=passed,
            failed=failed,
            results=results,
        )

    def _substitute_vars(self, command: list[str], domain_id: int) -> list[str]:
        """Substitute variables in command arguments."""
        result = []
        for arg in command:
            arg = arg.replace("{DOMAIN_ID}", str(domain_id))
            arg = arg.replace("{WORK_DIR}", str(self.work_dir))
            result.append(arg)
        return result

    def _capture_samples(
        self,
        domain_id: int,
        topics: str,
        timeout: float,
        output_file: Path,
    ) -> int:
        """Capture samples using rtiddsspy.

        Returns the number of samples captured.
        """
        spy_path = get_rtiddsspy_path()
        if spy_path is None:
            raise RuntimeError("rtiddsspy not found. Is NDDSHOME set?")

        env = get_spy_env()

        # Build command
        cmd = [
            str(spy_path),
            "-domainId", str(domain_id),
            "-printSample",
        ]

        # Run rtiddsspy
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)

            # Parse output
            from dds_tools.core.spy_parser import SpyParser, SpySample

            parser = SpyParser()
            samples = parser.parse_output(stdout)

            # Filter by topic if needed
            if topics != "*":
                import fnmatch
                samples = [s for s in samples if fnmatch.fnmatch(s.topic, topics)]

            # Write to output file
            with open(output_file, "w") as f:
                for sample in samples:
                    f.write(sample.to_json() + "\n")

            return len(samples)

        except Exception as e:
            if self.verbose:
                click.secho(f"  Error capturing samples: {e}", fg="red", err=True)
            return 0

    def cleanup(self) -> None:
        """Clean up resources."""
        self.process_manager.cleanup()


@click.group()
def main() -> None:
    """DDS Test Harness - Orchestrate publisher verification tests."""
    pass


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    required=True,
    help="Test configuration YAML file",
)
@click.option(
    "--test",
    "-t",
    "test_names",
    multiple=True,
    help="Specific test(s) to run (can be specified multiple times)",
)
@click.option(
    "--domain",
    "-d",
    type=int,
    default=None,
    help="Override domain ID from config",
)
@click.option(
    "--work-dir",
    type=click.Path(),
    default=None,
    help="Working directory for test files",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
def run(
    config: str,
    test_names: tuple[str, ...],
    domain: int | None,
    work_dir: str | None,
    as_json: bool,
    verbose: bool,
) -> None:
    """Run DDS verification tests.

    This command runs publisher verification tests as defined in a YAML
    configuration file. Each test:

    1. Starts a publisher process
    2. Captures DDS samples using rtiddsspy
    3. Compares samples against expected output
    4. Reports pass/fail status

    Examples:

        # Run all tests from config
        dds-test-harness run --config test_config.yaml

        # Run specific test
        dds-test-harness run --config test_config.yaml --test publisher_only

        # Override domain ID
        dds-test-harness run --config test_config.yaml --domain 99
    """
    # Load configuration
    try:
        test_config = load_test_config(config)
    except Exception as e:
        raise click.ClickException(f"Failed to load config: {e}")

    # Override domain if specified
    if domain is not None:
        test_config.domain_id = domain

    # Set up work directory
    work_path = Path(work_dir) if work_dir else None
    if work_path:
        work_path.mkdir(parents=True, exist_ok=True)

    # Create runner
    runner = TestRunner(
        config=test_config,
        work_dir=work_path,
        verbose=verbose,
    )

    try:
        # Run tests
        test_list = list(test_names) if test_names else None
        suite_result = runner.run_all(test_list)

        # Output results
        if as_json:
            click.echo(suite_result.to_json())
        else:
            _print_results(suite_result)

        # Exit with appropriate code
        sys.exit(0 if suite_result.failed == 0 else 1)

    finally:
        runner.cleanup()


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    required=True,
    help="Test configuration YAML file",
)
def list_tests(config: str) -> None:
    """List tests defined in a configuration file."""
    try:
        test_config = load_test_config(config)
    except Exception as e:
        raise click.ClickException(f"Failed to load config: {e}")

    if not test_config.tests:
        click.echo("No tests defined in configuration")
        return

    click.echo(f"Tests in {config}:\n")
    for name, test_case in test_config.tests.items():
        click.echo(f"  {name}")
        if test_case.description:
            click.echo(f"    {test_case.description}")


@main.command()
def check_env() -> None:
    """Check that the DDS environment is properly configured."""
    issues = []

    # Check NDDSHOME
    nddshome = os.environ.get("NDDSHOME")
    if not nddshome:
        issues.append("NDDSHOME environment variable is not set")
    else:
        click.echo(f"NDDSHOME: {nddshome}")

        # Check rtiddsspy
        spy_path = get_rtiddsspy_path()
        if spy_path:
            click.secho(f"rtiddsspy: {spy_path} ✓", fg="green")
        else:
            issues.append(f"rtiddsspy not found at {Path(nddshome) / 'bin' / 'rtiddsspy'}")

    # Check for available domain
    domain_id = get_safe_domain_id()
    click.echo(f"Available domain ID: {domain_id}")

    # Report issues
    if issues:
        click.echo()
        click.secho("Issues found:", fg="red")
        for issue in issues:
            click.echo(f"  - {issue}")
        sys.exit(1)
    else:
        click.echo()
        click.secho("Environment check passed ✓", fg="green")


def _print_results(suite_result: TestSuiteResult) -> None:
    """Print formatted test results."""
    click.echo()
    click.echo("=" * 60)
    click.echo("TEST RESULTS")
    click.echo("=" * 60)
    click.echo()

    for result in suite_result.results:
        if result.passed:
            status = click.style("PASS", fg="green")
        else:
            status = click.style("FAIL", fg="red")

        click.echo(f"  [{status}] {result.test_name}")
        click.echo(f"         Duration: {result.duration_seconds:.2f}s")
        click.echo(f"         Samples: {result.samples_captured} captured, {result.samples_matched} matched")

        if result.error:
            click.echo(f"         Error: {result.error}")

        click.echo()

    click.echo("=" * 60)
    click.echo(
        f"Total: {suite_result.total} | "
        f"Passed: {suite_result.passed} | "
        f"Failed: {suite_result.failed}"
    )
    click.echo("=" * 60)


if __name__ == "__main__":
    main()


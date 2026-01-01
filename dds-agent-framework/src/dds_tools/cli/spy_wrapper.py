"""CLI wrapper for RTI DDS Spy (rtiddsspy).

This tool wraps rtiddsspy and converts its human-readable output to structured
JSONL format suitable for automated validation.

Usage:
    dds-spy-wrapper --domain 222 --topics "Vehicle_*" --timeout 30 --output samples.jsonl
"""

import fnmatch
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path

import click

from dds_tools.core.spy_parser import SpyParser


def get_rtiddsspy_path() -> Path:
    """Get the path to rtiddsspy executable.

    Returns:
        Path to rtiddsspy.

    Raises:
        click.ClickException: If NDDSHOME is not set or rtiddsspy not found.
    """
    nddshome = os.environ.get("NDDSHOME")
    if not nddshome:
        raise click.ClickException(
            "NDDSHOME environment variable is not set. "
            "Please set it to your RTI Connext DDS installation directory."
        )

    spy_path = Path(nddshome) / "bin" / "rtiddsspy"
    if not spy_path.exists():
        raise click.ClickException(
            f"rtiddsspy not found at {spy_path}. "
            "Please verify your RTI Connext DDS installation."
        )

    return spy_path


def get_library_path_env() -> dict[str, str]:
    """Get environment variables for library paths.

    Returns:
        Dictionary of environment variables to set.
    """
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
        # macOS uses DYLD_LIBRARY_PATH
        existing = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = f"{lib_path}:{existing}" if existing else lib_path
    else:
        # Linux uses LD_LIBRARY_PATH
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{lib_path}:{existing}" if existing else lib_path

    return env


def matches_topic_filter(topic: str, pattern: str) -> bool:
    """Check if a topic matches the filter pattern.

    Args:
        topic: The topic name to check.
        pattern: Glob-style pattern (e.g., "Vehicle_*").

    Returns:
        True if the topic matches the pattern.
    """
    if pattern == "*":
        return True
    return fnmatch.fnmatch(topic, pattern)


@click.command()
@click.option(
    "--domain",
    "-d",
    type=int,
    default=0,
    help="DDS domain ID to monitor (default: 0)",
)
@click.option(
    "--topics",
    "-t",
    type=str,
    default="*",
    help="Topic filter pattern (glob-style, e.g., 'Vehicle_*'). Default: '*'",
)
@click.option(
    "--timeout",
    type=int,
    default=30,
    help="Timeout in seconds (default: 30). Use 0 for no timeout.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file for JSONL data. Default: stdout",
)
@click.option(
    "--count",
    "-n",
    type=int,
    default=0,
    help="Number of samples to capture (0 = unlimited until timeout)",
)
@click.option(
    "--qos-file",
    type=click.Path(exists=True),
    default=None,
    help="QoS profile XML file for type information",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print verbose output to stderr",
)
def main(
    domain: int,
    topics: str,
    timeout: int,
    output: str | None,
    count: int,
    qos_file: str | None,
    verbose: bool,
) -> None:
    """Wrap rtiddsspy and output structured JSONL.

    This tool runs RTI DDS Spy to capture DDS samples and converts the
    human-readable output to structured JSONL format for automated validation.

    Examples:

        # Capture samples on domain 0 for 10 seconds
        dds-spy-wrapper --domain 0 --timeout 10

        # Capture Vehicle_* topics and save to file
        dds-spy-wrapper --domain 222 --topics "Vehicle_*" --output samples.jsonl

        # Capture exactly 100 samples
        dds-spy-wrapper --domain 0 --count 100
    """
    spy_path = get_rtiddsspy_path()
    env = get_library_path_env()

    # Build rtiddsspy command
    cmd = [str(spy_path), "-domainId", str(domain), "-printSample"]

    if qos_file:
        cmd.extend(["-qosFile", qos_file])

    if verbose:
        click.echo(f"Running: {' '.join(cmd)}", err=True)
        click.echo(f"Domain: {domain}, Topics: {topics}, Timeout: {timeout}s", err=True)

    # Open output file if specified
    out_file = open(output, "w") if output else sys.stdout

    parser = SpyParser()
    samples_captured = 0

    try:
        # Start rtiddsspy process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Set up timeout handling
        if timeout > 0:
            def timeout_handler(signum: int, frame: object) -> None:
                if verbose:
                    click.echo(f"\nTimeout after {timeout}s", err=True)
                process.terminate()

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)

        try:
            # Read stdout line by line
            assert process.stdout is not None
            for line in process.stdout:
                sample = parser.parse_line(line)
                if sample:
                    # Apply topic filter
                    if matches_topic_filter(sample.topic, topics):
                        out_file.write(sample.to_json() + "\n")
                        out_file.flush()
                        samples_captured += 1

                        if verbose:
                            click.echo(
                                f"Captured sample {samples_captured} from topic {sample.topic}",
                                err=True,
                            )

                        # Check count limit
                        if count > 0 and samples_captured >= count:
                            if verbose:
                                click.echo(f"Reached sample count limit: {count}", err=True)
                            process.terminate()
                            break

            # Flush any remaining sample
            final_sample = parser.flush()
            if final_sample and matches_topic_filter(final_sample.topic, topics):
                out_file.write(final_sample.to_json() + "\n")
                samples_captured += 1

        finally:
            if timeout > 0:
                signal.alarm(0)  # Cancel the alarm

            # Ensure process is terminated
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

    except KeyboardInterrupt:
        if verbose:
            click.echo("\nInterrupted by user", err=True)

    finally:
        if output and out_file != sys.stdout:
            out_file.close()

    if verbose:
        click.echo(f"Total samples captured: {samples_captured}", err=True)

    # Exit with appropriate code
    sys.exit(0 if samples_captured > 0 else 1)


if __name__ == "__main__":
    main()


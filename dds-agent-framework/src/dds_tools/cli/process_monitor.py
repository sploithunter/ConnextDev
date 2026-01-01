"""CLI for managing DDS processes with timeout detection.

This tool manages DDS processes, providing:
- Automatic timeout detection and termination
- stdout/stderr capture
- Process registry for cleanup

Usage:
    dds-process-monitor start --name my_pub --timeout 60 -- python publisher.py
    dds-process-monitor status
    dds-process-monitor kill --name my_pub
    dds-process-monitor cleanup
"""

import json
import sys
from pathlib import Path

import click

from dds_tools.core.process_manager import ProcessManager, ProcessStatus


# Default state file location
DEFAULT_STATE_FILE = Path.home() / ".dds-tools" / "process_state.json"


def get_manager(state_file: str | None = None) -> ProcessManager:
    """Get a ProcessManager instance with the state file."""
    path = Path(state_file) if state_file else DEFAULT_STATE_FILE
    return ProcessManager(state_file=path)


@click.group()
@click.option(
    "--state-file",
    type=click.Path(),
    default=None,
    help=f"State file for process registry (default: {DEFAULT_STATE_FILE})",
)
@click.pass_context
def main(ctx: click.Context, state_file: str | None) -> None:
    """Manage DDS processes with timeout detection.

    This tool helps manage DDS processes for testing and development,
    with automatic timeout handling to prevent hung processes.
    """
    ctx.ensure_object(dict)
    ctx.obj["state_file"] = state_file


@main.command()
@click.option("--name", "-n", required=True, help="Unique name for this process")
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=60.0,
    help="Timeout in seconds (0 = no timeout, default: 60)",
)
@click.option(
    "--cwd",
    type=click.Path(exists=True),
    default=None,
    help="Working directory for the process",
)
@click.argument("command", nargs=-1, required=True)
@click.pass_context
def start(
    ctx: click.Context,
    name: str,
    timeout: float,
    cwd: str | None,
    command: tuple[str, ...],
) -> None:
    """Start a new process with monitoring.

    The command should be provided after --, for example:

        dds-process-monitor start --name my_pub -- python publisher.py --domain 99
    """
    manager = get_manager(ctx.obj.get("state_file"))

    try:
        info = manager.start_process(
            name=name,
            command=list(command),
            timeout=timeout,
            cwd=cwd,
        )

        click.echo(f"Started process '{name}' with PID {info.pid}")
        click.echo(f"Command: {' '.join(command)}")
        if timeout > 0:
            click.echo(f"Timeout: {timeout}s")
        else:
            click.echo("Timeout: none")

    except ValueError as e:
        raise click.ClickException(str(e))


@main.command()
@click.option("--name", "-n", default=None, help="Filter by process name")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def status(ctx: click.Context, name: str | None, as_json: bool) -> None:
    """Show status of managed processes."""
    manager = get_manager(ctx.obj.get("state_file"))

    if name:
        info = manager.check_process(name)
        if info is None:
            raise click.ClickException(f"Process '{name}' not found")

        if as_json:
            click.echo(json.dumps(info.to_dict(), indent=2))
        else:
            _print_process_info(info)
    else:
        all_procs = manager.get_all_processes()

        if not all_procs:
            if as_json:
                click.echo("[]")
            else:
                click.echo("No managed processes")
            return

        if as_json:
            click.echo(
                json.dumps([info.to_dict() for info in all_procs.values()], indent=2)
            )
        else:
            for info in all_procs.values():
                _print_process_info(info)
                click.echo()


@main.command()
@click.option("--name", "-n", required=True, help="Name of process to kill")
@click.option("--force", "-f", is_flag=True, help="Force kill (SIGKILL)")
@click.pass_context
def kill(ctx: click.Context, name: str, force: bool) -> None:
    """Kill a managed process."""
    manager = get_manager(ctx.obj.get("state_file"))

    if manager.kill_process(name, force=force):
        click.echo(f"Killed process '{name}'")
    else:
        raise click.ClickException(
            f"Could not kill process '{name}' (not found or not running)"
        )


@main.command()
@click.option("--name", "-n", required=True, help="Name of process")
@click.option("--stderr", is_flag=True, help="Show stderr instead of stdout")
@click.option("--tail", "-t", type=int, default=0, help="Show last N lines only")
@click.pass_context
def logs(ctx: click.Context, name: str, stderr: bool, tail: int) -> None:
    """Show output logs from a process."""
    manager = get_manager(ctx.obj.get("state_file"))

    output = manager.get_output(name)
    if output is None:
        raise click.ClickException(f"Process '{name}' not found")

    stdout_lines, stderr_lines = output
    lines = stderr_lines if stderr else stdout_lines

    if tail > 0:
        lines = lines[-tail:]

    for line in lines:
        click.echo(line)


@main.command()
@click.option("--force", "-f", is_flag=True, help="Force kill all (SIGKILL)")
@click.pass_context
def cleanup(ctx: click.Context, force: bool) -> None:
    """Kill all managed processes and clean up state."""
    manager = get_manager(ctx.obj.get("state_file"))

    cleaned = manager.cleanup()

    if cleaned:
        click.echo(f"Cleaned up {len(cleaned)} process(es): {', '.join(cleaned)}")
    else:
        click.echo("No processes to clean up")


@main.command()
@click.option("--name", "-n", required=True, help="Name of process to wait for")
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=0,
    help="Additional wait timeout (0 = wait until process timeout)",
)
@click.pass_context
def wait(ctx: click.Context, name: str, timeout: float) -> None:
    """Wait for a process to complete."""
    import time

    manager = get_manager(ctx.obj.get("state_file"))

    start_time = time.time()
    while True:
        info = manager.check_process(name)
        if info is None:
            raise click.ClickException(f"Process '{name}' not found")

        if not info.is_running:
            click.echo(f"Process '{name}' finished with status: {info.status.value}")
            if info.exit_code is not None:
                click.echo(f"Exit code: {info.exit_code}")
            sys.exit(0 if info.status == ProcessStatus.COMPLETED else 1)

        if timeout > 0 and (time.time() - start_time) > timeout:
            raise click.ClickException(f"Wait timeout after {timeout}s")

        time.sleep(0.5)


def _print_process_info(info) -> None:
    """Print formatted process info."""
    status_colors = {
        ProcessStatus.RUNNING: "green",
        ProcessStatus.COMPLETED: "blue",
        ProcessStatus.TIMEOUT: "yellow",
        ProcessStatus.ERROR: "red",
        ProcessStatus.KILLED: "yellow",
        ProcessStatus.PENDING: "white",
    }

    click.echo(f"Name: {info.name}")
    click.echo(f"  PID: {info.pid or 'N/A'}")
    click.secho(
        f"  Status: {info.status.value}",
        fg=status_colors.get(info.status, "white"),
    )
    click.echo(f"  Command: {' '.join(info.command)}")

    if info.elapsed_time is not None:
        click.echo(f"  Elapsed: {info.elapsed_time:.2f}s")

    if info.exit_code is not None:
        click.echo(f"  Exit code: {info.exit_code}")

    if info.error_message:
        click.secho(f"  Error: {info.error_message}", fg="red")

    click.echo(f"  Stdout lines: {len(info.stdout_lines)}")
    click.echo(f"  Stderr lines: {len(info.stderr_lines)}")


if __name__ == "__main__":
    main()


"""Process lifecycle management with timeout detection.

This module provides a process manager that can start, monitor, and terminate
DDS processes with automatic timeout detection. This is critical for AI-assisted
development where hung processes can block indefinitely.
"""

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import IO


class ProcessStatus(Enum):
    """Status of a managed process."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"
    KILLED = "killed"


@dataclass
class ProcessInfo:
    """Information about a managed process."""

    name: str
    command: list[str]
    pid: int | None = None
    status: ProcessStatus = ProcessStatus.PENDING
    start_time: float | None = None
    end_time: float | None = None
    exit_code: int | None = None
    timeout: float = 60.0
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    error_message: str | None = None

    @property
    def elapsed_time(self) -> float | None:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_running(self) -> bool:
        """Check if the process is currently running."""
        return self.status == ProcessStatus.RUNNING

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "command": self.command,
            "pid": self.pid,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "exit_code": self.exit_code,
            "timeout": self.timeout,
            "elapsed_time": self.elapsed_time,
            "stdout_lines": len(self.stdout_lines),
            "stderr_lines": len(self.stderr_lines),
            "error_message": self.error_message,
        }


class ProcessManager:
    """Manages DDS processes with timeout detection.

    This class provides:
    - Starting processes with automatic timeout monitoring
    - Capturing stdout/stderr in real-time
    - Detecting and terminating hung processes
    - Process registry for cleanup

    Example:
        manager = ProcessManager()
        info = manager.start_process(
            name="my_publisher",
            command=["python", "publisher.py", "--domain", "99"],
            timeout=60.0
        )
        # ... later ...
        status = manager.check_process("my_publisher")
        manager.kill_process("my_publisher")
    """

    def __init__(self, state_file: str | Path | None = None) -> None:
        """Initialize the process manager.

        Args:
            state_file: Optional path to persist process state.
        """
        self._processes: dict[str, ProcessInfo] = {}
        self._popen_handles: dict[str, subprocess.Popen] = {}
        self._output_threads: dict[str, list[threading.Thread]] = {}
        self._lock = threading.Lock()
        self._state_file = Path(state_file) if state_file else None

        # Load state from file if it exists
        if self._state_file and self._state_file.exists():
            self._load_state()

    def start_process(
        self,
        name: str,
        command: list[str],
        timeout: float = 60.0,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessInfo:
        """Start a new process with monitoring.

        Args:
            name: Unique name for this process.
            command: Command and arguments to run.
            timeout: Timeout in seconds (0 = no timeout).
            cwd: Working directory for the process.
            env: Environment variables (merged with current env).

        Returns:
            ProcessInfo for the started process.

        Raises:
            ValueError: If a process with this name already exists and is running.
        """
        with self._lock:
            if name in self._processes and self._processes[name].is_running:
                raise ValueError(f"Process '{name}' is already running")

            # Prepare environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            # Create process info
            info = ProcessInfo(
                name=name,
                command=command,
                timeout=timeout,
            )

            try:
                # Start the process
                popen = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=process_env,
                    text=True,
                    bufsize=1,
                )

                info.pid = popen.pid
                info.start_time = time.time()
                info.status = ProcessStatus.RUNNING

                self._processes[name] = info
                self._popen_handles[name] = popen

                # Start output capture threads
                stdout_thread = threading.Thread(
                    target=self._capture_output,
                    args=(name, popen.stdout, info.stdout_lines),
                    daemon=True,
                )
                stderr_thread = threading.Thread(
                    target=self._capture_output,
                    args=(name, popen.stderr, info.stderr_lines),
                    daemon=True,
                )
                stdout_thread.start()
                stderr_thread.start()
                self._output_threads[name] = [stdout_thread, stderr_thread]

                # Start timeout monitor if timeout > 0
                if timeout > 0:
                    timeout_thread = threading.Thread(
                        target=self._monitor_timeout,
                        args=(name, timeout),
                        daemon=True,
                    )
                    timeout_thread.start()

                self._save_state()

            except Exception as e:
                info.status = ProcessStatus.ERROR
                info.error_message = str(e)
                self._processes[name] = info
                self._save_state()

            return info

    def check_process(self, name: str) -> ProcessInfo | None:
        """Check the status of a process.

        Args:
            name: Name of the process to check.

        Returns:
            ProcessInfo or None if process not found.
        """
        with self._lock:
            info = self._processes.get(name)
            if info is None:
                return None

            # Update status if process has a handle
            if name in self._popen_handles:
                popen = self._popen_handles[name]
                exit_code = popen.poll()

                if exit_code is not None and info.status == ProcessStatus.RUNNING:
                    info.exit_code = exit_code
                    info.end_time = time.time()
                    info.status = (
                        ProcessStatus.COMPLETED
                        if exit_code == 0
                        else ProcessStatus.ERROR
                    )
                    self._save_state()

            return info

    def get_all_processes(self) -> dict[str, ProcessInfo]:
        """Get all managed processes.

        Returns:
            Dictionary of process name to ProcessInfo.
        """
        with self._lock:
            # Update all statuses inline (without recursive lock)
            for name, info in self._processes.items():
                if name in self._popen_handles and info.status == ProcessStatus.RUNNING:
                    popen = self._popen_handles[name]
                    exit_code = popen.poll()
                    if exit_code is not None:
                        info.exit_code = exit_code
                        info.end_time = time.time()
                        info.status = (
                            ProcessStatus.COMPLETED
                            if exit_code == 0
                            else ProcessStatus.ERROR
                        )
            return dict(self._processes)

    def get_output(self, name: str) -> tuple[list[str], list[str]] | None:
        """Get stdout and stderr output for a process.

        Args:
            name: Name of the process.

        Returns:
            Tuple of (stdout_lines, stderr_lines) or None if not found.
        """
        with self._lock:
            info = self._processes.get(name)
            if info is None:
                return None
            return (list(info.stdout_lines), list(info.stderr_lines))

    def kill_process(self, name: str, force: bool = False) -> bool:
        """Kill a running process.

        Args:
            name: Name of the process to kill.
            force: If True, use SIGKILL instead of SIGTERM.

        Returns:
            True if process was killed, False if not found or not running.
        """
        with self._lock:
            info = self._processes.get(name)
            if info is None or not info.is_running:
                return False

            popen = self._popen_handles.get(name)
            if popen is None:
                return False

            try:
                if force:
                    popen.kill()
                else:
                    popen.terminate()

                # Close streams to unblock reader threads
                if popen.stdout:
                    try:
                        popen.stdout.close()
                    except Exception:
                        pass
                if popen.stderr:
                    try:
                        popen.stderr.close()
                    except Exception:
                        pass

                # Wait briefly for termination
                try:
                    popen.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    popen.kill()
                    try:
                        popen.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass  # Process is really stuck, but we've done what we can

                info.exit_code = popen.returncode
                info.end_time = time.time()
                info.status = ProcessStatus.KILLED
                self._save_state()
                return True

            except Exception as e:
                info.error_message = f"Failed to kill: {e}"
                return False

    def cleanup(self) -> list[str]:
        """Kill all running processes and clean up.

        Returns:
            List of process names that were cleaned up.
        """
        # Get list of processes to kill without holding the lock
        with self._lock:
            to_kill = [
                name for name, info in self._processes.items()
                if info.is_running
            ]
        
        # Kill processes (each call acquires its own lock)
        cleaned = []
        for name in to_kill:
            if self.kill_process(name):
                cleaned.append(name)

        # Now clean up the registry
        with self._lock:
            self._processes.clear()
            self._popen_handles.clear()
            self._output_threads.clear()

            if self._state_file and self._state_file.exists():
                try:
                    self._state_file.unlink()
                except Exception:
                    pass

        return cleaned

    def _capture_output(
        self, name: str, stream: IO[str] | None, lines: list[str]
    ) -> None:
        """Capture output from a stream to a list."""
        if stream is None:
            return

        try:
            # Use readline with a check for process status
            while True:
                try:
                    line = stream.readline()
                    if not line:  # EOF
                        break
                    lines.append(line.rstrip("\n"))
                except (ValueError, OSError):
                    # Stream closed
                    break
        except Exception:
            # Any other error, just stop
            pass

    def _monitor_timeout(self, name: str, timeout: float) -> None:
        """Monitor a process for timeout."""
        time.sleep(timeout)

        with self._lock:
            info = self._processes.get(name)
            if info is None or not info.is_running:
                return

            popen = self._popen_handles.get(name)
            if popen is None:
                return

            # Process is still running after timeout
            if popen.poll() is None:
                try:
                    popen.terminate()
                    
                    # Close streams to unblock reader threads
                    if popen.stdout:
                        try:
                            popen.stdout.close()
                        except Exception:
                            pass
                    if popen.stderr:
                        try:
                            popen.stderr.close()
                        except Exception:
                            pass
                    
                    try:
                        popen.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        popen.kill()
                        try:
                            popen.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass

                    info.exit_code = popen.returncode
                    info.end_time = time.time()
                    info.status = ProcessStatus.TIMEOUT
                    info.error_message = f"Process timed out after {timeout}s"
                    self._save_state()
                except Exception as e:
                    info.error_message = f"Timeout handling failed: {e}"

    def _save_state(self) -> None:
        """Save process state to file."""
        if self._state_file is None:
            return

        state = {
            name: info.to_dict() for name, info in self._processes.items()
        }

        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass  # Ignore save errors

    def _load_state(self) -> None:
        """Load process state from file."""
        if self._state_file is None or not self._state_file.exists():
            return

        try:
            with open(self._state_file) as f:
                state = json.load(f)

            for name, data in state.items():
                # Only load completed/error processes (not running ones)
                if data.get("status") in ("running", "pending"):
                    continue

                info = ProcessInfo(
                    name=name,
                    command=data.get("command", []),
                    pid=data.get("pid"),
                    status=ProcessStatus(data.get("status", "error")),
                    start_time=data.get("start_time"),
                    end_time=data.get("end_time"),
                    exit_code=data.get("exit_code"),
                    timeout=data.get("timeout", 60.0),
                    error_message=data.get("error_message"),
                )
                self._processes[name] = info
        except Exception:
            pass  # Ignore load errors


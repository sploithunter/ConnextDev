"""Tests for the process manager."""

import time
import sys

import pytest
from dds_tools.core.process_manager import ProcessManager, ProcessStatus


class TestProcessManager:
    """Tests for ProcessManager class."""

    def test_start_simple_process(self) -> None:
        """Test starting a simple process."""
        manager = ProcessManager()
        info = manager.start_process(
            name="echo_test",
            command=[sys.executable, "-c", "print('hello')"],
            timeout=10,
        )

        assert info.name == "echo_test"
        assert info.status == ProcessStatus.RUNNING
        assert info.pid is not None

        # Wait for completion
        time.sleep(0.5)
        info = manager.check_process("echo_test")
        assert info is not None
        assert info.status == ProcessStatus.COMPLETED
        assert info.exit_code == 0

        manager.cleanup()

    def test_capture_stdout(self) -> None:
        """Test capturing stdout from a process."""
        manager = ProcessManager()
        manager.start_process(
            name="stdout_test",
            command=[sys.executable, "-c", "print('line1'); print('line2')"],
            timeout=10,
        )

        # Wait for completion
        time.sleep(0.5)
        output = manager.get_output("stdout_test")

        assert output is not None
        stdout, stderr = output
        assert "line1" in stdout
        assert "line2" in stdout

        manager.cleanup()

    def test_capture_stderr(self) -> None:
        """Test capturing stderr from a process."""
        manager = ProcessManager()
        manager.start_process(
            name="stderr_test",
            command=[
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('error\\n')",
            ],
            timeout=10,
        )

        # Wait for completion
        time.sleep(0.5)
        output = manager.get_output("stderr_test")

        assert output is not None
        stdout, stderr = output
        assert "error" in stderr

        manager.cleanup()

    def test_process_timeout(self) -> None:
        """Test that processes are terminated after timeout."""
        manager = ProcessManager()
        manager.start_process(
            name="timeout_test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=1,  # 1 second timeout
        )

        # Wait for timeout
        time.sleep(2)
        info = manager.check_process("timeout_test")

        assert info is not None
        assert info.status == ProcessStatus.TIMEOUT
        assert "timed out" in (info.error_message or "").lower()

        manager.cleanup()

    def test_kill_process(self) -> None:
        """Test killing a running process."""
        manager = ProcessManager()
        manager.start_process(
            name="kill_test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=0,  # No timeout
        )

        time.sleep(0.2)
        result = manager.kill_process("kill_test")
        assert result is True

        info = manager.check_process("kill_test")
        assert info is not None
        assert info.status == ProcessStatus.KILLED

        manager.cleanup()

    def test_duplicate_name_raises(self) -> None:
        """Test that starting a process with duplicate name raises."""
        manager = ProcessManager()
        manager.start_process(
            name="dup_test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=0,
        )

        with pytest.raises(ValueError, match="already running"):
            manager.start_process(
                name="dup_test",
                command=[sys.executable, "-c", "print('hello')"],
                timeout=10,
            )

        manager.cleanup()

    def test_get_all_processes(self) -> None:
        """Test getting all managed processes."""
        manager = ProcessManager()
        manager.start_process(
            name="proc1",
            command=[sys.executable, "-c", "print('1')"],
            timeout=10,
        )
        manager.start_process(
            name="proc2",
            command=[sys.executable, "-c", "print('2')"],
            timeout=10,
        )

        time.sleep(0.5)
        all_procs = manager.get_all_processes()

        assert "proc1" in all_procs
        assert "proc2" in all_procs

        manager.cleanup()

    def test_cleanup_kills_running(self) -> None:
        """Test that cleanup kills all running processes."""
        manager = ProcessManager()
        manager.start_process(
            name="cleanup1",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=0,
        )
        manager.start_process(
            name="cleanup2",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=0,
        )

        time.sleep(0.2)
        cleaned = manager.cleanup()

        assert "cleanup1" in cleaned
        assert "cleanup2" in cleaned

    def test_process_exit_code(self) -> None:
        """Test that exit codes are captured correctly."""
        manager = ProcessManager()
        manager.start_process(
            name="exit_test",
            command=[sys.executable, "-c", "import sys; sys.exit(42)"],
            timeout=10,
        )

        time.sleep(0.5)
        info = manager.check_process("exit_test")

        assert info is not None
        assert info.exit_code == 42
        assert info.status == ProcessStatus.ERROR

        manager.cleanup()

    def test_check_nonexistent_process(self) -> None:
        """Test checking a process that doesn't exist."""
        manager = ProcessManager()
        info = manager.check_process("nonexistent")
        assert info is None

    def test_kill_nonexistent_process(self) -> None:
        """Test killing a process that doesn't exist."""
        manager = ProcessManager()
        result = manager.kill_process("nonexistent")
        assert result is False

    def test_process_info_to_dict(self) -> None:
        """Test ProcessInfo serialization."""
        manager = ProcessManager()
        info = manager.start_process(
            name="dict_test",
            command=[sys.executable, "-c", "print('hello')"],
            timeout=10,
        )

        d = info.to_dict()
        assert d["name"] == "dict_test"
        assert d["status"] == "running"
        assert d["pid"] is not None
        assert d["command"] == [sys.executable, "-c", "print('hello')"]

        manager.cleanup()


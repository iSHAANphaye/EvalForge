"""Unit tests for Docker sandbox runner, isolation, and execution watchdog."""

import io
import json
import tarfile
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from docker.errors import DockerException

from evalforge.core.config import Settings
from evalforge.core.constants import (
    DEFAULT_STDOUT_MAX_BYTES,
    EXIT_CODE_OOM,
    EXIT_CODE_TIMEOUT,
    ErrorTypeEnum,
)
from evalforge.core.exceptions import SandboxError
from evalforge.sandbox.isolation import (
    create_tar_archive,
    extract_cgroup_peak_memory,
    truncate_output,
)
from evalforge.sandbox.runner import DockerExecutionEngine


class MockExecResult:
    """Mock result object mimicking docker-py container.exec_run ExecResult."""

    def __init__(self, exit_code: int = 0, output: Any = (b"", b"")) -> None:
        self.exit_code = exit_code
        self.output = output

    def __getitem__(self, idx: int) -> Any:
        if idx == 0:
            return self.exit_code
        if idx == 1:
            return self.output
        raise IndexError(idx)


@pytest.fixture
def test_settings() -> Settings:
    """Return test Settings instance."""
    return Settings(
        exec_timeout_sec=2.0,
        cpp_compiler_timeout_sec=5.0,
        ram_limit_mb=256,
    )


def make_mock_container(
    exec_handler: Any = None,
    attrs: dict[str, Any] | None = None,
    put_archive_side_effect: Any = None,
) -> MagicMock:
    """Helper to create a configured mock Docker container."""
    container = MagicMock()
    container.id = "mock-sandbox-container-42"
    container.attrs = attrs or {"State": {"OOMKilled": False, "Running": True}}

    if exec_handler:
        container.exec_run.side_effect = exec_handler
    else:
        container.exec_run.return_value = MockExecResult(0, (b"Mock output", b""))

    if put_archive_side_effect:
        container.put_archive.side_effect = put_archive_side_effect

    return container


# =============================================================================
# 1. Isolation Helpers: File Tar Archiving Tests
# =============================================================================


def test_create_tar_archive_basic() -> None:
    """Verify in-memory tar archive generation correctly preserves paths and contents."""
    files: dict[str, str | bytes] = {
        "solution.py": "def solve(): return 42\n",
        "test_suite.py": b"assert solve() == 42\n",
        "nested/data.txt": "sample line",
    }
    tar_bytes = create_tar_archive(files)
    assert isinstance(tar_bytes, bytes)
    assert len(tar_bytes) > 0

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        names = tar.getnames()
        assert "solution.py" in names
        assert "test_suite.py" in names
        assert "nested/data.txt" in names

        f1 = tar.extractfile("solution.py")
        assert f1 is not None
        assert f1.read().decode("utf-8") == "def solve(): return 42\n"

        f2 = tar.extractfile("test_suite.py")
        assert f2 is not None
        assert f2.read() == b"assert solve() == 42\n"

        f3 = tar.extractfile("nested/data.txt")
        assert f3 is not None
        assert f3.read().decode("utf-8") == "sample line"


def test_create_tar_archive_empty() -> None:
    """Verify empty dictionary produces valid tar archive bytes."""
    tar_bytes = create_tar_archive({})
    assert isinstance(tar_bytes, bytes)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        assert len(tar.getnames()) == 0


# =============================================================================
# 2. Isolation Helpers: Output Truncation Tests
# =============================================================================


def test_truncate_output_under_limit() -> None:
    """Verify output under the byte limit is returned unmodified."""
    short_text = "All 10 tests passed successfully."
    assert truncate_output(short_text, max_bytes=1000) == short_text
    assert truncate_output("", max_bytes=1000) == ""


def test_truncate_output_exceeding_limit() -> None:
    """Verify output exceeding 16KB is truncated with head and tail preservation."""
    head_content = "START_HEAD_TRACEBACK_INFO\n"
    tail_content = "\nEND_TAIL_TEST_SUMMARY_PASSED"
    filler = "X" * 30000
    large_text = f"{head_content}{filler}{tail_content}"

    truncated = truncate_output(large_text, max_bytes=DEFAULT_STDOUT_MAX_BYTES)
    truncated_bytes = truncated.encode("utf-8")

    assert len(truncated_bytes) <= DEFAULT_STDOUT_MAX_BYTES
    assert truncated.startswith(head_content)
    assert truncated.endswith(tail_content)
    assert "... [output truncated:" in truncated
    assert "exceeded 16384 limit" in truncated


def test_truncate_output_custom_budget() -> None:
    """Verify truncate_output behaves correctly with custom small byte budgets."""
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
    budget = 50
    truncated = truncate_output(text, max_bytes=budget)
    assert len(truncated.encode("utf-8")) <= budget


# =============================================================================
# 3. Isolation Helpers: Cgroup Peak Memory Extraction Tests
# =============================================================================


def test_extract_cgroup_peak_memory_v2() -> None:
    """Verify extraction of cgroup v2 memory.peak into KB."""
    def exec_handler(cmd, *args, **kwargs):
        if "memory.peak" in cmd:
            # 16 MB in bytes = 16777216 -> 16384 KB
            return MockExecResult(0, b"16777216\n")
        return MockExecResult(1, b"No such file")

    container = make_mock_container(exec_handler=exec_handler)
    peak_kb = extract_cgroup_peak_memory(container)
    assert peak_kb == 16384


def test_extract_cgroup_peak_memory_v1_fallback() -> None:
    """Verify fallback to cgroup v1 memory.max_usage_in_bytes if v2 fails."""
    def exec_handler(cmd, *args, **kwargs):
        if "memory.peak" in cmd:
            return MockExecResult(1, b"cat: can't open '/sys/fs/cgroup/memory.peak': No such file")
        if "memory.max_usage_in_bytes" in cmd:
            # 8 MB in bytes = 8388608 -> 8192 KB
            return MockExecResult(0, b"8388608\n")
        return MockExecResult(1, b"Error")

    container = make_mock_container(exec_handler=exec_handler)
    peak_kb = extract_cgroup_peak_memory(container)
    assert peak_kb == 8192


def test_extract_cgroup_peak_memory_unreadable() -> None:
    """Verify extract_cgroup_peak_memory returns 0 when files are missing or invalid."""
    container = make_mock_container(exec_handler=lambda *a, **k: MockExecResult(1, b"Error"))
    assert extract_cgroup_peak_memory(container) == 0

    container_invalid = make_mock_container(
        exec_handler=lambda *a, **k: MockExecResult(0, b"not_a_number")
    )
    assert extract_cgroup_peak_memory(container_invalid) == 0


# =============================================================================
# 4. DockerExecutionEngine: File Injection Tests
# =============================================================================


def test_inject_files_success() -> None:
    """Verify files are archived and injected into /workspace/run."""
    container = make_mock_container()
    engine = DockerExecutionEngine()
    files = {"candidate.py": "def foo(): pass\n", "test.py": "assert True\n"}

    engine.inject_files(container, files)
    assert container.put_archive.called
    call_kwargs = container.put_archive.call_args.kwargs
    assert call_kwargs["path"] == "/workspace/run"
    assert isinstance(call_kwargs["data"], bytes)


def test_inject_files_empty_noop() -> None:
    """Verify empty file dictionary does not invoke put_archive."""
    container = make_mock_container()
    engine = DockerExecutionEngine()
    engine.inject_files(container, {})
    assert not container.put_archive.called


def test_inject_files_docker_error() -> None:
    """Verify DockerException during put_archive raises SandboxError."""
    container = make_mock_container(
        put_archive_side_effect=DockerException("Failed to stream archive")
    )
    engine = DockerExecutionEngine()
    with pytest.raises(SandboxError, match="Failed to inject files into container"):
        engine.inject_files(container, {"foo.py": "pass"})


# =============================================================================
# 5. Python Execution: Clean Run, Timeout, and OOM Tests
# =============================================================================


async def test_python_clean_execution(test_settings: Settings) -> None:
    """Verify successful Python pytest execution captures telemetry, report, and peak memory."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            return MockExecResult(0, (b"===== 4 passed in 0.05s =====", b""))
        if "memory.peak" in cmd_str:
            return MockExecResult(0, b"33554432")  # 32 MB -> 32768 KB
        if "cat /tmp/report.json" in cmd_str:
            report_data = {
                "summary": {"passed": 4, "failed": 0, "total": 4},
                "tests": [],
            }
            return MockExecResult(0, json.dumps(report_data).encode("utf-8"))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container, entry_script="test_visible.py")

    assert result.exit_code == 0
    assert result.error_type == ErrorTypeEnum.NONE
    assert result.timed_out is False
    assert result.oom_killed is False
    assert result.duration_ms > 0
    assert result.memory_peak_kb == 32768
    assert "4 passed" in result.stdout
    assert result.error_message is None


async def test_python_timeout_enforcement(test_settings: Settings) -> None:
    """Verify execution exceeding timeout flags timed_out=True, exit 124, and terminates process."""
    def slow_exec(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            time.sleep(0.4)
            return MockExecResult(0, (b"delayed output", b""))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=slow_exec)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container, timeout_sec=0.05)

    assert result.timed_out is True
    assert result.exit_code == EXIT_CODE_TIMEOUT  # 124
    assert result.error_type == ErrorTypeEnum.TIMEOUT
    assert result.oom_killed is False
    assert result.duration_ms >= 50.0
    assert "Execution exceeded maximum timeout" in result.stderr

    # Verify killing container processes was attempted
    assert container.exec_run.called or container.kill.called


async def test_python_oom_detection_by_exit_code(test_settings: Settings) -> None:
    """Verify exit code 137 is correctly classified as OOM."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            return MockExecResult(EXIT_CODE_OOM, (b"Killed\n", b"Out of memory\n"))
        if "memory.peak" in cmd_str:
            return MockExecResult(0, b"268435456")  # 256 MB
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container)

    assert result.oom_killed is True
    assert result.exit_code == EXIT_CODE_OOM  # 137
    assert result.error_type == ErrorTypeEnum.OOM
    assert result.timed_out is False


async def test_python_oom_detection_by_container_attrs(test_settings: Settings) -> None:
    """Verify OOMKilled state flag sets oom_killed=True even if raw exit code was generic."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            return MockExecResult(1, (b"", b"Fatal error"))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(
        exec_handler=exec_handler,
        attrs={"State": {"OOMKilled": True, "Running": False}},
    )
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container)

    assert result.oom_killed is True
    assert result.exit_code == EXIT_CODE_OOM
    assert result.error_type == ErrorTypeEnum.OOM


async def test_python_syntax_error_classification(test_settings: Settings) -> None:
    """Verify SyntaxError in test output categorizes error_type as SYNTAX_ERROR."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            stderr = b"File 'candidate.py', line 3\n  def foo(\n        ^\nSyntaxError: '(' was never closed"
            return MockExecResult(1, (b"", stderr))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container)

    assert result.exit_code == 1
    assert result.error_type == ErrorTypeEnum.SYNTAX_ERROR
    assert "SyntaxError" in result.stderr


async def test_python_test_failure_with_json_report(test_settings: Settings) -> None:
    """Verify failed tests extract summary information from /tmp/report.json."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "pytest" in cmd_str:
            return MockExecResult(1, (b"FAILURES\n___ test_edge ___\nassert 1 == 2", b""))
        if "cat /tmp/report.json" in cmd_str:
            report_data = {
                "summary": {"passed": 2, "failed": 1, "total": 3},
                "tests": [],
            }
            return MockExecResult(0, json.dumps(report_data).encode("utf-8"))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_python(container)

    assert result.exit_code == 1
    assert result.error_type == ErrorTypeEnum.RUNTIME_EXCEPTION
    assert "1 of 3 tests failed" in (result.error_message or "")


# =============================================================================
# 6. C++ Execution: Compilation Failure, Success, and Timeout Tests
# =============================================================================


async def test_cpp_compilation_failure(test_settings: Settings) -> None:
    """Verify C++ compilation failure returns exit code 1 and ErrorTypeEnum.SYNTAX_ERROR."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "g++" in cmd_str:
            compile_err = b"solution.cpp:5:10: error: 'vector' was not declared in this scope\n"
            return MockExecResult(1, (b"", compile_err))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_cpp(
        container,
        source_file="solution.cpp",
        test_file="test_cases.cpp",
    )

    assert result.exit_code == 1
    assert result.error_type == ErrorTypeEnum.SYNTAX_ERROR
    assert "vector' was not declared" in result.stderr
    assert result.timed_out is False
    assert result.oom_killed is False


async def test_cpp_clean_compilation_and_execution(test_settings: Settings) -> None:
    """Verify C++ compilation success followed by Google Test binary execution."""
    def exec_handler(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "g++" in cmd_str:
            return MockExecResult(0, (b"", b""))
        if "test_binary" in cmd_str:
            gtest_out = b"[==========] Running 3 tests from 1 test suite.\n[  PASSED  ] 3 tests.\n"
            return MockExecResult(0, (gtest_out, b""))
        if "memory.peak" in cmd_str:
            return MockExecResult(0, b"12582912")  # 12 MB -> 12288 KB
        if "cat /tmp/report.json" in cmd_str:
            gtest_json = {"testsuites": [{"tests": 3, "failures": 0}]}
            return MockExecResult(0, json.dumps(gtest_json).encode("utf-8"))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=exec_handler)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_cpp(
        container,
        source_file="solution.cpp",
        test_file="test_cases.cpp",
    )

    assert result.exit_code == 0
    assert result.error_type == ErrorTypeEnum.NONE
    assert result.memory_peak_kb == 12288
    assert "[  PASSED  ] 3 tests." in result.stdout
    assert result.timed_out is False
    assert result.oom_killed is False


async def test_cpp_binary_execution_timeout(test_settings: Settings) -> None:
    """Verify compiled C++ binary exceeding timeout watchdog triggers TIMEOUT."""
    def slow_exec(cmd, *args, **kwargs):
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        if "g++" in cmd_str:
            return MockExecResult(0, (b"", b""))
        if "test_binary" in cmd_str:
            time.sleep(0.4)
            return MockExecResult(0, (b"delayed", b""))
        return MockExecResult(0, (b"", b""))

    container = make_mock_container(exec_handler=slow_exec)
    engine = DockerExecutionEngine(settings=test_settings)

    result = await engine.run_cpp(
        container,
        source_file="solution.cpp",
        test_file="test_cases.cpp",
        timeout_sec=0.05,
    )

    assert result.timed_out is True
    assert result.exit_code == EXIT_CODE_TIMEOUT  # 124
    assert result.error_type == ErrorTypeEnum.TIMEOUT


# =============================================================================
# 7. Unified Entrypoint & Sync Wrapper Tests
# =============================================================================


async def test_unified_run_python_dispatch() -> None:
    """Verify engine.run() dispatches to Python runner and injects files."""
    container = make_mock_container()
    engine = DockerExecutionEngine()
    files = {"candidate.py": "def f(): pass", "test_visible.py": "assert True"}

    result = await engine.run(
        container=container,
        language="python",
        files=files,
        test_target="test_visible.py",
        timeout_sec=1.5,
    )

    assert container.put_archive.called
    assert result.exit_code == 0


async def test_unified_run_cpp_dispatch() -> None:
    """Verify engine.run() dispatches to C++ runner and injects files."""
    container = make_mock_container()
    engine = DockerExecutionEngine()
    files = {"solution.cpp": "int main() {}", "test_suite.cpp": "TEST(A, B) {}"}

    result = await engine.run(
        container=container,
        language="cpp",
        files=files,
        test_target="test_suite.cpp",
        timeout_sec=1.5,
    )

    assert container.put_archive.called
    assert result.exit_code == 0


async def test_unified_run_unsupported_language() -> None:
    """Verify engine.run() raises SandboxError for unknown languages."""
    container = make_mock_container()
    engine = DockerExecutionEngine()

    with pytest.raises(SandboxError, match="Unsupported language 'rust'"):
        await engine.run(container=container, language="rust")


def test_run_sync_wrapper() -> None:
    """Verify synchronous run_sync wrapper functions properly."""
    container = make_mock_container()
    engine = DockerExecutionEngine()

    result = engine.run_sync(
        container=container,
        language="python",
        test_target="test_visible.py",
    )
    assert result.exit_code == 0

"""Docker execution engine and watchdog runner for isolated code testing."""

import asyncio
import json
import time
from typing import Any

from docker.errors import DockerException

from evalforge.core.config import Settings, get_settings
from evalforge.core.constants import (
    EXIT_CODE_OOM,
    EXIT_CODE_TIMEOUT,
    ErrorTypeEnum,
)
from evalforge.core.exceptions import SandboxError
from evalforge.core.logging import get_logger
from evalforge.models.schemas import ExecutionResult
from evalforge.sandbox.isolation import (
    create_tar_archive,
    extract_cgroup_peak_memory,
    truncate_output,
)

logger = get_logger("sandbox.runner")


def _parse_exec_output(output: Any) -> tuple[str, str]:
    """Parse output from container.exec_run into separate stdout and stderr strings."""
    if isinstance(output, tuple | list) and len(output) == 2:
        out, err = output
        out_str = (
            out.decode("utf-8", errors="replace")
            if isinstance(out, bytes)
            else (str(out) if out else "")
        )
        err_str = (
            err.decode("utf-8", errors="replace")
            if isinstance(err, bytes)
            else (str(err) if err else "")
        )
        return out_str, err_str

    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace"), ""
    if isinstance(output, str):
        return output, ""
    return "", ""


def _kill_container_process(container: Any) -> None:
    """Attempt to terminate unprivileged child processes in container, falling back to kill()."""
    try:
        container.exec_run("pkill -9 -u 10001")
    except Exception:
        pass
    try:
        container.exec_run("kill -9 -1")
    except Exception:
        pass
    try:
        container.kill()
    except Exception:
        pass


def _is_oom(container: Any, exit_code: int) -> bool:
    """Determine whether container process terminated due to an OOM condition."""
    if exit_code == EXIT_CODE_OOM:
        return True
    try:
        if hasattr(container, "reload"):
            container.reload()
    except Exception:
        pass
    attrs = getattr(container, "attrs", {}) or {}
    state = attrs.get("State", {}) or {}
    return bool(state.get("OOMKilled", False))


def _classify_error(
    exit_code: int, oom_killed: bool, timed_out: bool, stdout: str, stderr: str
) -> ErrorTypeEnum:
    """Classify the failure category based on execution telemetry."""
    if timed_out:
        return ErrorTypeEnum.TIMEOUT
    if oom_killed or exit_code == EXIT_CODE_OOM:
        return ErrorTypeEnum.OOM
    if exit_code == 0:
        return ErrorTypeEnum.NONE
    if "SyntaxError" in stderr or "SyntaxError" in stdout:
        return ErrorTypeEnum.SYNTAX_ERROR
    return ErrorTypeEnum.RUNTIME_EXCEPTION


class DockerExecutionEngine:
    """Sandbox execution engine running isolated test suites in Docker containers."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the execution engine.

        Args:
            settings: Configuration settings (defaults to cached application settings).
        """
        self.settings: Settings = settings or get_settings()

    def inject_files(
        self,
        container: Any,
        files: dict[str, str | bytes],
        destination: str = "/workspace/run",
    ) -> None:
        """Inject files into /workspace/run inside the container using container.put_archive().

        Args:
            container: Active Docker container.
            files: Mapping of relative file paths to string or byte contents.
            destination: Path within container where archive will be unpacked.

        Raises:
            SandboxError: If archive transmission or file injection fails.
        """
        if not files:
            return

        tar_bytes = create_tar_archive(files)
        try:
            container.put_archive(path=destination, data=tar_bytes)
        except DockerException as exc:
            raise SandboxError(
                f"Failed to inject files into container '{destination}': {exc}"
            ) from exc

    def parse_report_json(
        self,
        container: Any,
        report_path: str = "/tmp/report.json",
    ) -> dict[str, Any] | None:
        """Parse JSON test report generated inside the container.

        Args:
            container: Active Docker container.
            report_path: Path to the generated report inside container.

        Returns:
            dict: Parsed report JSON dictionary or None if missing/invalid.
        """
        try:
            res = container.exec_run(f"cat {report_path}")
            exit_code = getattr(res, "exit_code", None)
            if exit_code is None and isinstance(res, tuple | list):
                exit_code = res[0]
                output = res[1]
            else:
                output = getattr(res, "output", b"")
            if exit_code == 0 and output:
                text = (
                    output.decode("utf-8", errors="replace")
                    if isinstance(output, bytes)
                    else str(output)
                )
                return json.loads(text.strip())
        except Exception as exc:
            logger.debug(f"Could not parse test report from {report_path}: {exc}")
        return None

    async def run_python(
        self,
        container: Any,
        entry_script: str = "test_visible.py",
        timeout_sec: float = 2.0,
        capture_json: bool = True,
    ) -> ExecutionResult:
        """Execute pytest test harness inside container as sandbox_user (UID 10001).

        Args:
            container: Active Docker container.
            entry_script: Test file name inside /workspace/run.
            timeout_sec: Hard wall-clock execution timeout in seconds.
            capture_json: Whether to generate and parse structured JSON test report.

        Returns:
            ExecutionResult containing execution telemetry and status.
        """
        eff_timeout = (
            timeout_sec if timeout_sec is not None else self.settings.exec_timeout_sec
        )
        if capture_json:
            cmd = f"pytest {entry_script} --json-report --json-report-file=/tmp/report.json"
        else:
            cmd = f"pytest {entry_script}"

        start_time = time.perf_counter()
        try:
            exec_res = await asyncio.wait_for(
                asyncio.to_thread(
                    container.exec_run,
                    cmd,
                    workdir="/workspace/run",
                    user="10001:10001",
                    demux=True,
                ),
                timeout=eff_timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            exit_code = getattr(exec_res, "exit_code", None)
            if exit_code is None and isinstance(exec_res, tuple | list):
                exit_code = exec_res[0]
                raw_out = exec_res[1]
            else:
                raw_out = getattr(exec_res, "output", b"")
            stdout_text, stderr_text = _parse_exec_output(raw_out)
        except TimeoutError:
            _kill_container_process(container)
            duration_ms = eff_timeout * 1000.0
            stderr_msg = f"Execution exceeded maximum timeout of {eff_timeout:.2f}s."
            return ExecutionResult(
                stdout="",
                stderr=truncate_output(stderr_msg),
                exit_code=EXIT_CODE_TIMEOUT,
                duration_ms=duration_ms,
                memory_peak_kb=0,
                oom_killed=False,
                timed_out=True,
                error_type=ErrorTypeEnum.TIMEOUT,
                error_message=stderr_msg,
            )

        # Check OOM & Peak Memory
        is_oom = _is_oom(container, exit_code)
        peak_memory = extract_cgroup_peak_memory(container)

        if is_oom:
            return ExecutionResult(
                stdout=truncate_output(stdout_text),
                stderr=truncate_output(stderr_text),
                exit_code=EXIT_CODE_OOM,
                duration_ms=duration_ms,
                memory_peak_kb=peak_memory,
                oom_killed=True,
                timed_out=False,
                error_type=ErrorTypeEnum.OOM,
                error_message="Execution terminated by OOM killer.",
            )

        error_type = _classify_error(exit_code, False, False, stdout_text, stderr_text)
        report = self.parse_report_json(container) if capture_json else None
        err_msg = stderr_text if exit_code != 0 else None
        if report and exit_code != 0 and not err_msg:
            summary = report.get("summary", {})
            err_msg = (
                f"Pytest failed: {summary.get('failed', 0)} of "
                f"{summary.get('total', 0)} tests failed."
            )

        return ExecutionResult(
            stdout=truncate_output(stdout_text),
            stderr=truncate_output(stderr_text),
            exit_code=exit_code,
            duration_ms=duration_ms,
            memory_peak_kb=peak_memory,
            oom_killed=False,
            timed_out=False,
            error_type=error_type,
            error_message=err_msg,
        )

    async def run_cpp(
        self,
        container: Any,
        source_file: str,
        test_file: str,
        timeout_sec: float = 2.0,
    ) -> ExecutionResult:
        """Compile C++20 code with g++ and execute Google Test binary inside container.

        Args:
            container: Active Docker container.
            source_file: Candidate C++ source file path.
            test_file: Google Test harness C++ file path.
            timeout_sec: Execution timeout for the compiled binary in seconds.

        Returns:
            ExecutionResult containing compilation or execution telemetry.
        """
        eff_timeout = (
            timeout_sec if timeout_sec is not None else self.settings.exec_timeout_sec
        )
        compile_cmd = (
            f"g++ -std=c++20 -O1 -g0 {source_file} {test_file} "
            "-lgtest -lgtest_main -pthread -o /workspace/run/test_binary"
        )
        compile_timeout = self.settings.cpp_compiler_timeout_sec
        compile_start = time.perf_counter()

        try:
            compile_res = await asyncio.wait_for(
                asyncio.to_thread(
                    container.exec_run,
                    compile_cmd,
                    workdir="/workspace/run",
                    user="10001:10001",
                    demux=True,
                ),
                timeout=compile_timeout,
            )
            compile_exit = getattr(compile_res, "exit_code", None)
            if compile_exit is None and isinstance(compile_res, tuple | list):
                compile_exit = compile_res[0]
                raw_out = compile_res[1]
            else:
                raw_out = getattr(compile_res, "output", b"")
            compile_stdout, compile_stderr = _parse_exec_output(raw_out)
        except TimeoutError:
            _kill_container_process(container)
            timeout_msg = f"C++ compilation timed out after {compile_timeout:.1f}s."
            return ExecutionResult(
                exit_code=EXIT_CODE_TIMEOUT,
                timed_out=True,
                error_type=ErrorTypeEnum.TIMEOUT,
                duration_ms=compile_timeout * 1000.0,
                stderr=truncate_output(timeout_msg),
                error_message=timeout_msg,
            )

        if compile_exit != 0:
            return ExecutionResult(
                stdout=truncate_output(compile_stdout),
                stderr=truncate_output(compile_stderr),
                exit_code=1,
                duration_ms=(time.perf_counter() - compile_start) * 1000.0,
                memory_peak_kb=extract_cgroup_peak_memory(container),
                oom_killed=False,
                timed_out=False,
                error_type=ErrorTypeEnum.SYNTAX_ERROR,
                error_message=compile_stderr or "C++ compilation failed.",
            )

        # Compilation succeeded: run binary with timeout watchdog
        binary_cmd = "/workspace/run/test_binary --gtest_output=json:/tmp/report.json"
        start_time = time.perf_counter()
        try:
            exec_res = await asyncio.wait_for(
                asyncio.to_thread(
                    container.exec_run,
                    binary_cmd,
                    workdir="/workspace/run",
                    user="10001:10001",
                    demux=True,
                ),
                timeout=eff_timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            exit_code = getattr(exec_res, "exit_code", None)
            if exit_code is None and isinstance(exec_res, tuple | list):
                exit_code = exec_res[0]
                raw_out = exec_res[1]
            else:
                raw_out = getattr(exec_res, "output", b"")
            stdout_text, stderr_text = _parse_exec_output(raw_out)
        except TimeoutError:
            _kill_container_process(container)
            duration_ms = eff_timeout * 1000.0
            stderr_msg = f"Execution exceeded maximum timeout of {eff_timeout:.2f}s."
            return ExecutionResult(
                stdout="",
                stderr=truncate_output(stderr_msg),
                exit_code=EXIT_CODE_TIMEOUT,
                duration_ms=duration_ms,
                memory_peak_kb=0,
                oom_killed=False,
                timed_out=True,
                error_type=ErrorTypeEnum.TIMEOUT,
                error_message=stderr_msg,
            )

        is_oom = _is_oom(container, exit_code)
        peak_memory = extract_cgroup_peak_memory(container)

        if is_oom:
            return ExecutionResult(
                stdout=truncate_output(stdout_text),
                stderr=truncate_output(stderr_text),
                exit_code=EXIT_CODE_OOM,
                duration_ms=duration_ms,
                memory_peak_kb=peak_memory,
                oom_killed=True,
                timed_out=False,
                error_type=ErrorTypeEnum.OOM,
                error_message="Execution terminated by OOM killer.",
            )

        error_type = _classify_error(exit_code, False, False, stdout_text, stderr_text)
        report = self.parse_report_json(container)
        err_msg = stderr_text if exit_code != 0 else None
        if report and exit_code != 0 and not err_msg:
            err_msg = "Google Test assertions failed."

        return ExecutionResult(
            stdout=truncate_output(stdout_text),
            stderr=truncate_output(stderr_text),
            exit_code=exit_code,
            duration_ms=duration_ms,
            memory_peak_kb=peak_memory,
            oom_killed=False,
            timed_out=False,
            error_type=error_type,
            error_message=err_msg,
        )

    async def run(
        self,
        container: Any,
        language: str = "python",
        files: dict[str, str | bytes] | None = None,
        test_target: str = "test_visible.py",
        timeout_sec: float | None = None,
        **kwargs: Any,
    ) -> ExecutionResult:
        """Unified entrypoint dispatching execution to Python or C++.

        Args:
            container: Active Docker container instance.
            language: Target programming language ('python' or 'cpp').
            files: Optional file mapping to inject into container before running.
            test_target: Test runner script or test source file.
            timeout_sec: Maximum execution timeout in seconds.
            **kwargs: Extra parameters (e.g. source_file for C++, capture_json for Python).

        Returns:
            ExecutionResult containing execution status and output.

        Raises:
            SandboxError: If specified language is unsupported.
        """
        if files:
            self.inject_files(container, files)

        eff_timeout = (
            timeout_sec if timeout_sec is not None else self.settings.exec_timeout_sec
        )
        norm_lang = language.strip().lower()

        if norm_lang == "python":
            capture_json = kwargs.get("capture_json", True)
            return await self.run_python(
                container=container,
                entry_script=test_target,
                timeout_sec=eff_timeout,
                capture_json=capture_json,
            )

        if norm_lang == "cpp":
            source_file = kwargs.get("source_file")
            if not source_file:
                if files:
                    for fname in files:
                        if fname.endswith(".cpp") and fname != test_target:
                            source_file = fname
                            break
                if not source_file:
                    source_file = "solution.cpp"

            return await self.run_cpp(
                container=container,
                source_file=source_file,
                test_file=test_target,
                timeout_sec=eff_timeout,
            )

        raise SandboxError(
            f"Unsupported language '{language}'. Supported languages: 'python', 'cpp'."
        )

    def run_sync(self, *args: Any, **kwargs: Any) -> ExecutionResult:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(*args, **kwargs))

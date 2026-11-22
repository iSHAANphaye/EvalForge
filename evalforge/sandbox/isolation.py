"""Sandbox isolation, cgroup metrics, output truncation, and file injection helpers."""

import io
import tarfile
import time
from typing import Any

from evalforge.core.constants import DEFAULT_STDOUT_MAX_BYTES
from evalforge.core.logging import get_logger

logger = get_logger("sandbox.isolation")


def create_tar_archive(files: dict[str, str | bytes]) -> bytes:
    """Create an in-memory tar archive of source and test files.

    Args:
        files: Mapping of relative file paths to their string or byte contents.

    Returns:
        bytes: Raw tar archive bytes for container.put_archive().
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for file_path, content in files.items():
            if isinstance(content, str):
                encoded = content.encode("utf-8")
            else:
                encoded = content
            info = tarfile.TarInfo(name=file_path)
            info.size = len(encoded)
            info.mtime = int(time.time())
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(encoded))
    return buf.getvalue()


def extract_cgroup_peak_memory(container: Any) -> int:
    """Extract peak memory in KB from cgroup v2 (or v1 fallback).

    Reads memory.peak from cgroup v2 (/sys/fs/cgroup/memory.peak) via
    container.exec_run("cat /sys/fs/cgroup/memory.peak"), with fallback
    to cgroup v1 (/sys/fs/cgroup/memory/memory.max_usage_in_bytes).

    Args:
        container: Docker container instance.

    Returns:
        int: Peak memory in KB, or 0 if unreadable.
    """
    commands = [
        "cat /sys/fs/cgroup/memory.peak",
        "cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes",
    ]
    for cmd in commands:
        try:
            res = container.exec_run(cmd)
            exit_code = getattr(res, "exit_code", None)
            if exit_code is None and isinstance(res, tuple | list):
                exit_code = res[0]
                output = res[1]
            else:
                output = getattr(res, "output", b"")

            if exit_code == 0 and output:
                text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
                text = text.strip()
                if text.isdigit():
                    return int(text) // 1024
        except Exception as exc:
            logger.debug(f"Failed to read cgroup memory with '{cmd}': {exc}")

    return 0


def truncate_output(text: str, max_bytes: int = DEFAULT_STDOUT_MAX_BYTES) -> str:
    """Truncate long stdout/stderr with head and tail preservation.

    Args:
        text: String output to truncate.
        max_bytes: Maximum allowed byte size (default: 16384 bytes).

    Returns:
        str: Truncated text within max_bytes limit.
    """
    if not text:
        return ""

    raw_bytes = text.encode("utf-8", errors="replace")
    if len(raw_bytes) <= max_bytes:
        return text

    marker = f"\n\n... [output truncated: {len(raw_bytes)} bytes exceeded {max_bytes} limit] ...\n\n"
    marker_bytes = marker.encode("utf-8")

    if len(marker_bytes) >= max_bytes:
        return raw_bytes[:max_bytes].decode("utf-8", errors="ignore")

    budget = max_bytes - len(marker_bytes)
    head_len = budget // 2
    tail_len = budget - head_len

    head = raw_bytes[:head_len].decode("utf-8", errors="ignore")
    tail = raw_bytes[-tail_len:].decode("utf-8", errors="ignore") if tail_len > 0 else ""

    return f"{head}{marker}{tail}"

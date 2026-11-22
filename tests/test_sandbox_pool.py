"""Unit tests for EvalForge Docker sandbox pool manager and cleaner."""

import uuid
from unittest.mock import MagicMock

import pytest
from docker.errors import APIError, DockerException, NotFound

from evalforge.core.config import Settings
from evalforge.core.exceptions import SandboxError, SandboxTimeoutError
from evalforge.sandbox import (
    SandboxPoolManager,
    cleanup_orphans,
    force_destroy_container,
)


@pytest.fixture
def mock_docker_client():
    """Create a mock DockerClient returning distinct container instances."""
    client = MagicMock()
    client.ping.return_value = True

    def create_mock_container(**kwargs):
        container = MagicMock()
        container.id = str(uuid.uuid4())
        container.labels = kwargs.get("labels", {})
        return container

    client.containers.run.side_effect = create_mock_container
    return client


@pytest.fixture
def test_settings():
    """Return test Settings with small pool size."""
    return Settings(
        docker_pool_size=2,
        ram_limit_mb=256,
        docker_image_python="evalforge-sandbox-python:latest",
        docker_image_cpp="evalforge-sandbox-cpp:latest",
    )


# =============================================================================
# SandboxPoolManager Pre-warming & Security Options Tests
# =============================================================================


async def test_start_prewarms_containers_with_security_options(mock_docker_client, test_settings):
    """Verify start() pre-warms K containers per language with exact security invariants."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    # Pre-warmed 2 Python + 2 C++ containers
    assert manager.get_warm_count("python") == 2
    assert manager.get_warm_count("cpp") == 2
    assert mock_docker_client.containers.run.call_count == 4

    # Verify security constraints on every container creation call
    expected_tmpfs = {
        "/workspace/run": "rw,noexec,nosuid,size=64m,mode=0755,uid=10001,gid=10001",
        "/tmp": "rw,noexec,nosuid,nodev,size=64m,mode=0700,uid=10001,gid=10001",
    }

    for call in mock_docker_client.containers.run.call_args_list:
        kwargs = call.kwargs
        assert kwargs["detach"] is True
        assert kwargs["network_mode"] == "none"
        assert kwargs["mem_limit"] == "256m"
        assert kwargs["memswap_limit"] == "256m"
        assert kwargs["cpu_period"] == 100000
        assert kwargs["cpu_quota"] == 100000
        assert kwargs["pids_limit"] == 64
        assert kwargs["cap_drop"] == ["ALL"]
        assert kwargs["security_opt"] == ["no-new-privileges:true"]
        assert kwargs["read_only"] is True
        assert kwargs["user"] == "10001:10001"
        assert kwargs["tmpfs"] == expected_tmpfs

        # Labels
        labels = kwargs["labels"]
        assert labels["evalforge.managed"] == "true"
        assert labels["evalforge.language"] in ("python", "cpp")
        assert labels["evalforge.pool_id"] == manager.pool_id

        # Image check
        if labels["evalforge.language"] == "python":
            assert kwargs["image"] == "evalforge-sandbox-python:latest"
        else:
            assert kwargs["image"] == "evalforge-sandbox-cpp:latest"

    await manager.stop()


async def test_start_is_idempotent(mock_docker_client, test_settings):
    """Verify calling start() multiple times does not recreate warm pool."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()
    assert mock_docker_client.containers.run.call_count == 4

    # Second start call should be a no-op
    await manager.start()
    assert mock_docker_client.containers.run.call_count == 4

    await manager.stop()


# =============================================================================
# Acquire & Release Tests (SLA and Ephemeral Lifecycle)
# =============================================================================


async def test_acquire_latency_and_decrement_count(mock_docker_client, test_settings):
    """Verify acquire() retrieves container in <150ms and decrements available warm count."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    assert manager.get_warm_count("python") == 2

    # Checkout container 1
    c1, latency1 = await manager.acquire("python")
    assert c1 is not None
    assert latency1 < 150.0
    assert manager.get_warm_count("python") == 1

    # Checkout container 2
    c2, latency2 = await manager.acquire("python")
    assert c2 is not None
    assert latency2 < 150.0
    assert manager.get_warm_count("python") == 0

    await manager.stop()


async def test_acquire_cpp_container(mock_docker_client, test_settings):
    """Verify acquire() supports C++ sandbox containers."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    c_cpp, latency = await manager.acquire("cpp")
    assert c_cpp is not None
    assert latency < 150.0
    assert manager.get_warm_count("cpp") == 1

    await manager.stop()


async def test_release_removes_container_and_replenishes_pool(mock_docker_client, test_settings):
    """Verify release() executes container.remove(force=True) and asynchronously replenishes."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    initial_run_count = mock_docker_client.containers.run.call_count
    container, _ = await manager.acquire("python")
    assert manager.get_warm_count("python") == 1

    # Release container
    await manager.release(container, language="python")
    container.remove.assert_called_once_with(force=True)

    # Wait for asynchronous replenishment background task
    await manager.wait_replenishment()

    # Pool replenished back to capacity K
    assert manager.get_warm_count("python") == 2
    assert mock_docker_client.containers.run.call_count == initial_run_count + 1

    await manager.stop()


# =============================================================================
# Context Manager Tests (acquire_sandbox)
# =============================================================================


async def test_acquire_sandbox_context_manager_normal(mock_docker_client, test_settings):
    """Verify acquire_sandbox checks out container and releases it upon exit."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    active_container = None
    async with manager.acquire_sandbox("python") as (container, latency):
        active_container = container
        assert latency < 150.0
        assert manager.get_warm_count("python") == 1
        container.remove.assert_not_called()

    # After exiting block, container is destroyed and pool replenished
    active_container.remove.assert_called_once_with(force=True)
    await manager.wait_replenishment()
    assert manager.get_warm_count("python") == 2

    await manager.stop()


async def test_acquire_sandbox_context_manager_on_exception(mock_docker_client, test_settings):
    """Verify acquire_sandbox destroys container even when an exception is raised."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    captured_container = None
    with pytest.raises(RuntimeError, match="Evaluation execution crash"):
        async with manager.acquire_sandbox("python") as (container, _):
            captured_container = container
            raise RuntimeError("Evaluation execution crash")

    assert captured_container is not None
    captured_container.remove.assert_called_once_with(force=True)
    await manager.wait_replenishment()
    assert manager.get_warm_count("python") == 2

    await manager.stop()


# =============================================================================
# Queue Timeout & Exhaustion Tests
# =============================================================================


async def test_acquire_timeout_when_pool_exhausted(mock_docker_client, test_settings):
    """Verify queue timeout raises SandboxTimeoutError when warm pool is depleted."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    # Exhaust both warm python containers
    await manager.acquire("python")
    await manager.acquire("python")
    assert manager.get_warm_count("python") == 0

    # Next acquire with timeout should raise SandboxTimeoutError
    with pytest.raises(SandboxTimeoutError) as exc_info:
        await manager.acquire("python", timeout_sec=0.05)

    # Invariants: inherits from both TimeoutError and SandboxError
    assert isinstance(exc_info.value, TimeoutError)
    assert isinstance(exc_info.value, SandboxError)
    assert "Timed out acquiring sandbox container" in str(exc_info.value)

    await manager.stop()


async def test_acquire_unsupported_language(mock_docker_client, test_settings):
    """Verify acquiring an unsupported language raises SandboxError."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    with pytest.raises(SandboxError, match="Unsupported language 'rust'"):
        await manager.acquire("rust")


async def test_acquire_unstarted_empty_pool(mock_docker_client, test_settings):
    """Verify acquiring from an unstarted empty pool raises SandboxError."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    with pytest.raises(SandboxError, match="Sandbox pool has not been started"):
        await manager.acquire("python")


# =============================================================================
# Stop & Shutdown Tests
# =============================================================================


async def test_stop_destroys_all_warm_containers(mock_docker_client, test_settings):
    """Verify stop() force-removes all warm containers and clears queues."""
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)
    await manager.start()

    all_containers = list(manager._all_containers)
    assert len(all_containers) == 4

    await manager.stop()

    for c in all_containers:
        c.remove.assert_called_with(force=True)

    assert manager.get_warm_count("python") == 0
    assert manager.get_warm_count("cpp") == 0


# =============================================================================
# Cleaner & Orphan Tests
# =============================================================================


def test_cleanup_orphans_filters_and_removes(mock_docker_client):
    """Verify cleanup_orphans() queries evalforge.managed=true and destroys containers."""
    c1 = MagicMock(id="c1")
    c2 = MagicMock(id="c2")
    c3 = MagicMock(id="c3")
    mock_docker_client.containers.list.return_value = [c1, c2, c3]

    removed_count = cleanup_orphans(mock_docker_client)

    mock_docker_client.containers.list.assert_called_once_with(
        all=True,
        filters={"label": "evalforge.managed=true"},
    )
    c1.remove.assert_called_once_with(force=True)
    c2.remove.assert_called_once_with(force=True)
    c3.remove.assert_called_once_with(force=True)
    assert removed_count == 3


def test_cleanup_orphans_handles_not_found(mock_docker_client):
    """Verify cleanup_orphans() handles containers already removed without crashing."""
    c1 = MagicMock(id="c1")
    c1.remove.side_effect = NotFound("Container already gone")
    mock_docker_client.containers.list.return_value = [c1]

    removed_count = cleanup_orphans(mock_docker_client)
    assert removed_count == 1
    c1.remove.assert_called_once_with(force=True)


def test_cleanup_orphans_docker_offline(mock_docker_client):
    """Verify cleanup_orphans() wraps DockerException in SandboxError."""
    mock_docker_client.containers.list.side_effect = DockerException("Daemon socket error")

    with pytest.raises(SandboxError, match="Failed to list orphan containers"):
        cleanup_orphans(mock_docker_client)


def test_force_destroy_container_safe_handling():
    """Verify force_destroy_container() safely handles None, APIError, and NotFound."""
    # None container does not fail
    force_destroy_container(None)

    # APIError is caught safely
    c_api_error = MagicMock()
    c_api_error.remove.side_effect = APIError("500 Server Error")
    force_destroy_container(c_api_error)
    c_api_error.remove.assert_called_once_with(force=True)

    # NotFound is caught safely
    c_not_found = MagicMock()
    c_not_found.remove.side_effect = NotFound("404 Not Found")
    force_destroy_container(c_not_found)
    c_not_found.remove.assert_called_once_with(force=True)


# =============================================================================
# Docker Daemon Offline Handling Tests
# =============================================================================


def test_docker_daemon_offline_from_env(mocker):
    """Verify SandboxPoolManager raises SandboxError when docker.from_env() fails."""
    mocker.patch("docker.from_env", side_effect=DockerException("daemon connection failed"))

    with pytest.raises(SandboxError, match="Cannot connect to the Docker daemon"):
        SandboxPoolManager()


async def test_docker_daemon_offline_on_start():
    """Verify start() raises SandboxError when client ping fails."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = DockerException("Ping timeout")

    manager = SandboxPoolManager(docker_client=mock_client)
    with pytest.raises(SandboxError, match="Docker daemon is offline or unreachable"):
        await manager.start()


async def test_start_handles_spawn_failure(mock_docker_client, test_settings):
    """Verify start() cleans up and raises SandboxError if container creation fails."""
    mock_docker_client.containers.run.side_effect = DockerException("No space left on device")
    manager = SandboxPoolManager(settings=test_settings, docker_client=mock_docker_client)

    with pytest.raises(SandboxError, match="Failed to pre-warm sandbox pool"):
        await manager.start()

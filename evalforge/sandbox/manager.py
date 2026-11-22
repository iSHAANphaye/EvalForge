"""Sandbox pool manager for pre-warmed, ephemeral Docker execution environments."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import docker
from docker.errors import DockerException

from evalforge.core.config import Settings, get_settings
from evalforge.core.exceptions import SandboxError, SandboxTimeoutError
from evalforge.core.logging import get_logger
from evalforge.sandbox.cleaner import force_destroy_container

logger = get_logger("sandbox.manager")


class SandboxPoolManager:
    """Manages pre-warmed, ephemeral Docker sandbox containers with strict security constraints."""

    def __init__(
        self,
        settings: Settings | None = None,
        docker_client: docker.DockerClient | None = None,
    ) -> None:
        """Initialize the SandboxPoolManager.

        Args:
            settings: Configuration settings (defaults to cached application settings).
            docker_client: Optional Docker client instance for dependency injection/testing.

        Raises:
            SandboxError: If docker_client is None and the Docker daemon cannot be reached.
        """
        self.settings: Settings = settings or get_settings()
        self.pool_id: str = str(uuid.uuid4())

        self._pool_python: asyncio.Queue[docker.models.containers.Container] = asyncio.Queue()
        self._pool_cpp: asyncio.Queue[docker.models.containers.Container] = asyncio.Queue()
        self._pools: dict[str, asyncio.Queue[docker.models.containers.Container]] = {
            "python": self._pool_python,
            "cpp": self._pool_cpp,
        }

        self._all_containers: set[docker.models.containers.Container] = set()
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._started: bool = False

        if docker_client is not None:
            self._client = docker_client
        else:
            try:
                self._client = docker.from_env()
            except DockerException as exc:
                raise SandboxError(
                    f"Cannot connect to the Docker daemon. Is Docker running? ({exc})"
                ) from exc

    @property
    def client(self) -> docker.DockerClient:
        """Return the underlying Docker client instance."""
        return self._client

    def get_warm_count(self, language: str = "python") -> int:
        """Return the count of warm containers currently available for the given language."""
        norm_lang = language.strip().lower()
        if norm_lang not in self._pools:
            raise SandboxError(f"Unsupported language '{language}'. Supported languages: 'python', 'cpp'.")
        return self._pools[norm_lang].qsize()

    def _resolve_image(self, language: str) -> str:
        """Resolve docker image name for the specified language."""
        if language == "python":
            return self.settings.docker_image_python
        if language == "cpp":
            return self.settings.docker_image_cpp
        raise SandboxError(f"Unsupported language '{language}'. Supported languages: 'python', 'cpp'.")

    def _create_container(self, language: str) -> docker.models.containers.Container:
        """Create and start a hardened container with strict cgroups, capabilities, and tmpfs mounts."""
        norm_lang = language.strip().lower()
        image = self._resolve_image(norm_lang)

        try:
            container = self._client.containers.run(
                image=image,
                detach=True,
                network_mode="none",
                mem_limit=f"{self.settings.ram_limit_mb}m",
                memswap_limit=f"{self.settings.ram_limit_mb}m",
                cpu_period=100000,
                cpu_quota=100000,
                pids_limit=64,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                read_only=True,
                user="10001:10001",
                tmpfs={
                    "/workspace/run": "rw,noexec,nosuid,size=64m,mode=0755,uid=10001,gid=10001",
                    "/tmp": "rw,noexec,nosuid,nodev,size=64m,mode=0700,uid=10001,gid=10001",
                },
                labels={
                    "evalforge.managed": "true",
                    "evalforge.language": norm_lang,
                    "evalforge.pool_id": self.pool_id,
                },
            )
            self._all_containers.add(container)
            return container
        except DockerException as exc:
            raise SandboxError(
                f"Failed to create Docker sandbox container for '{norm_lang}': {exc}"
            ) from exc

    async def _spawn_and_enqueue(self, language: str) -> docker.models.containers.Container:
        """Spawn a container in a worker thread and place it in the warm queue."""
        container = await asyncio.to_thread(self._create_container, language)
        await self._pools[language].put(container)
        return container

    async def _replenish(self, language: str) -> docker.models.containers.Container | None:
        """Background worker to replenish a destroyed container in the pool."""
        try:
            return await self._spawn_and_enqueue(language)
        except Exception as exc:
            logger.error(f"Failed to replenish sandbox container for '{language}': {exc}")
            return None

    async def wait_replenishment(self) -> None:
        """Wait for any currently scheduled background replenishment tasks to complete."""
        while self._background_tasks:
            tasks = list(self._background_tasks)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self, languages: tuple[str, ...] | list[str] | None = None) -> None:
        """Pre-warm target capacity K containers for each configured language.

        Args:
            languages: Sequence of language identifiers to pre-warm (defaults to 'python' and 'cpp').

        Raises:
            SandboxError: If the Docker daemon is unreachable or pre-warming fails.
        """
        if self._started:
            return

        try:
            self._client.ping()
        except DockerException as exc:
            raise SandboxError(f"Docker daemon is offline or unreachable: {exc}") from exc

        target_languages = languages or ("python", "cpp")
        k = self.settings.docker_pool_size

        spawn_tasks = []
        for lang in target_languages:
            norm_lang = lang.strip().lower()
            if norm_lang not in self._pools:
                raise SandboxError(
                    f"Unsupported language '{lang}'. Supported languages: 'python', 'cpp'."
                )
            for _ in range(k):
                spawn_tasks.append(self._spawn_and_enqueue(norm_lang))

        try:
            await asyncio.gather(*spawn_tasks)
        except Exception as exc:
            await self.stop()
            raise SandboxError(f"Failed to pre-warm sandbox pool: {exc}") from exc

        self._started = True
        logger.info(
            f"Pre-warmed {k} sandbox container(s) for languages: {list(target_languages)}."
        )

    async def stop(self) -> None:
        """Shut down all idle warm containers and cancel background tasks."""
        self._started = False

        # Cancel any active replenishment tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        # Gather warm containers from queues
        containers_to_destroy: list[docker.models.containers.Container] = []
        for queue in self._pools.values():
            while not queue.empty():
                try:
                    c = queue.get_nowait()
                    containers_to_destroy.append(c)
                except asyncio.QueueEmpty:
                    break

        # Also include any remaining tracked containers
        for c in list(self._all_containers):
            if c not in containers_to_destroy:
                containers_to_destroy.append(c)

        # Force-remove all containers
        if containers_to_destroy:
            await asyncio.gather(
                *[asyncio.to_thread(force_destroy_container, c) for c in containers_to_destroy],
                return_exceptions=True,
            )

        self._all_containers.clear()
        logger.info("Sandbox pool stopped and warm containers cleaned up.")

    async def acquire(
        self,
        language: str = "python",
        timeout_sec: float | None = None,
    ) -> tuple[docker.models.containers.Container, float]:
        """Check out a warm container from the pool, measuring checkout latency.

        Args:
            language: Target programming language ('python' or 'cpp').
            timeout_sec: Maximum wait deadline in seconds.

        Returns:
            tuple: (container, checkout_latency_ms)

        Raises:
            SandboxTimeoutError: If timeout elapses waiting for an available container.
            SandboxError: If language is unsupported or pool is not started.
        """
        norm_lang = language.strip().lower()
        if norm_lang not in self._pools:
            raise SandboxError(
                f"Unsupported language '{language}'. Supported languages: 'python', 'cpp'."
            )

        queue = self._pools[norm_lang]
        if not self._started and queue.empty():
            raise SandboxError(
                "Sandbox pool has not been started and has no warm containers available."
            )

        start_time = time.perf_counter()
        try:
            if timeout_sec is not None:
                container = await asyncio.wait_for(queue.get(), timeout=timeout_sec)
            else:
                container = await queue.get()
        except TimeoutError as exc:
            raise SandboxTimeoutError(
                f"Timed out acquiring sandbox container for '{norm_lang}' after {timeout_sec}s.",
                timeout_sec=timeout_sec,
            ) from exc

        checkout_latency_ms = (time.perf_counter() - start_time) * 1000.0
        return container, checkout_latency_ms

    async def release(
        self,
        container: docker.models.containers.Container,
        language: str = "python",
    ) -> None:
        """Release a used container by forcefully destroying it and scheduling pool replenishment.

        Enforces the Single-Use Ephemeral Guarantee: Used containers are never reused,
        eliminating cross-run state pollution.

        Args:
            container: The used Docker container instance.
            language: Programming language of the container.
        """
        norm_lang = language.strip().lower()
        if norm_lang not in self._pools:
            raise SandboxError(
                f"Unsupported language '{language}'. Supported languages: 'python', 'cpp'."
            )

        self._all_containers.discard(container)
        await asyncio.to_thread(force_destroy_container, container)

        # Immediately schedule background task to replenish fresh container
        task = asyncio.create_task(self._replenish(norm_lang))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    @asynccontextmanager
    async def acquire_sandbox(
        self,
        language: str = "python",
        timeout_sec: float | None = None,
    ) -> AsyncIterator[tuple[docker.models.containers.Container, float]]:
        """Context manager to check out a warm sandbox container and guarantee single-use destruction.

        Yields:
            tuple: (container, checkout_latency_ms)
        """
        container, latency_ms = await self.acquire(language=language, timeout_sec=timeout_sec)
        try:
            yield container, latency_ms
        finally:
            await self.release(container, language=language)

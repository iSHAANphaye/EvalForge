"""Sandbox container cleanup utilities for orphan detection and safe destruction."""

from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound

from evalforge.core.exceptions import SandboxError
from evalforge.core.logging import get_logger

logger = get_logger("sandbox.cleaner")


def force_destroy_container(container: Any) -> None:
    """Safely execute container.remove(force=True), catching NotFound or APIError.

    Args:
        container: Docker container instance to destroy.
    """
    if container is None:
        return
    try:
        container.remove(force=True)
    except (NotFound, APIError, DockerException) as exc:
        container_id = getattr(container, "id", "unknown")
        logger.warning(f"Error force destroying container '{container_id}': {exc}")


def cleanup_orphans(client: docker.DockerClient) -> int:
    """Search for containers with label evalforge.managed="true" and force-remove them.

    Args:
        client: Initialized Docker client.

    Returns:
        Number of orphan containers successfully removed.

    Raises:
        SandboxError: If Docker client raises DockerException when listing containers.
    """
    try:
        orphans = client.containers.list(
            all=True,
            filters={"label": "evalforge.managed=true"},
        )
    except DockerException as exc:
        logger.error(f"Failed to query orphan containers from Docker: {exc}")
        raise SandboxError(f"Failed to list orphan containers: {exc}") from exc

    removed_count = 0
    for container in orphans:
        force_destroy_container(container)
        removed_count += 1

    logger.info(f"Cleaned up {removed_count} orphan sandbox container(s).")
    return removed_count

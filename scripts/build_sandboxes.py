"""EvalForge sandbox container image builder and inspector script.

Provides utility functions and CLI commands to inspect and build hardened
evaluation sandbox Docker images for Python and C++ targets.
"""

from pathlib import Path
from typing import Any

import docker
import typer
from docker.errors import DockerException, ImageNotFound

app = typer.Typer(
    help="Build and inspect EvalForge evaluation sandbox Docker images.",
    add_completion=False,
)

SANDBOX_IMAGES: dict[str, dict[str, str]] = {
    "python": {
        "tag": "evalforge-sandbox-python:latest",
        "dockerfile": "Dockerfile.sandbox.python",
    },
    "cpp": {
        "tag": "evalforge-sandbox-cpp:latest",
        "dockerfile": "Dockerfile.sandbox.cpp",
    },
}


def resolve_targets(target: str) -> dict[str, dict[str, str]]:
    """Resolve target name to a dictionary of sandbox image specifications.

    Args:
        target: Target identifier ('python', 'cpp', or 'all').

    Returns:
        Mapping of target name to image specifications.

    Raises:
        ValueError: If target is not supported.
    """
    normalized = target.strip().lower()
    if normalized == "all":
        return SANDBOX_IMAGES
    if normalized in SANDBOX_IMAGES:
        return {normalized: SANDBOX_IMAGES[normalized]}

    valid_targets = ", ".join(repr(t) for t in list(SANDBOX_IMAGES.keys()) + ["all"])
    raise ValueError(f"Invalid target '{target}'. Must be one of: {valid_targets}.")


def get_docker_client() -> docker.DockerClient:
    """Initialize and verify Docker client connection.

    Returns:
        Connected docker.DockerClient instance.

    Raises:
        DockerException: If Docker daemon is offline or unreachable.
    """
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as exc:
        raise DockerException(
            f"Cannot connect to the Docker daemon. Is Docker running? ({exc})"
        ) from exc


def check_images(
    client: docker.DockerClient,
    target: str = "all",
) -> dict[str, bool]:
    """Check whether sandbox images exist in the local Docker registry.

    Args:
        client: Initialized Docker client.
        target: Target image to check ('python', 'cpp', or 'all'). Defaults to 'all'.

    Returns:
        Mapping from image tag to existence status (True if found, False otherwise).
    """
    targets = resolve_targets(target)
    status: dict[str, bool] = {}

    for spec in targets.values():
        tag = spec["tag"]
        try:
            client.images.get(tag)
            status[tag] = True
        except ImageNotFound:
            status[tag] = False

    return status


def build_images(
    client: docker.DockerClient,
    target: str = "all",
    context_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build sandbox Docker images using the local Docker daemon.

    Args:
        client: Initialized Docker client.
        target: Target image to build ('python', 'cpp', or 'all'). Defaults to 'all'.
        context_path: Root directory containing Dockerfiles (defaults to project root).

    Returns:
        Mapping from image tag to built Image object.

    Raises:
        FileNotFoundError: If a required Dockerfile is missing.
        DockerException: If Docker build fails.
    """
    if context_path is None:
        context_path = Path(__file__).resolve().parent.parent
    else:
        context_path = Path(context_path)

    targets = resolve_targets(target)
    built_images: dict[str, Any] = {}

    for spec in targets.values():
        tag = spec["tag"]
        dockerfile_name = spec["dockerfile"]
        dockerfile_path = context_path / dockerfile_name

        if not dockerfile_path.exists():
            raise FileNotFoundError(
                f"Dockerfile '{dockerfile_name}' not found at {dockerfile_path}"
            )

        image, _ = client.images.build(
            path=str(context_path),
            dockerfile=dockerfile_name,
            tag=tag,
            rm=True,
        )
        built_images[tag] = image

    return built_images


@app.command()
def main(
    build: bool = typer.Option(
        False,
        "--build",
        "-b",
        help="Build sandbox Docker images.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        "-c",
        help="Check if sandbox Docker images exist in local Docker registry.",
    ),
    image: str = typer.Option(
        "all",
        "--image",
        "-i",
        help="Image target to check or build: 'python', 'cpp', or 'all'.",
    ),
) -> None:
    """Manage and inspect EvalForge Docker sandbox environments."""
    if not build and not check:
        typer.echo("No action specified. Please provide --check, --build, or both.")
        raise typer.Exit(code=0)

    try:
        client = get_docker_client()
    except DockerException as exc:
        error_msg = str(exc)
        if "Cannot connect to the Docker daemon" not in error_msg:
            error_msg = f"Cannot connect to the Docker daemon. ({error_msg})"
        typer.secho(f"Error: {error_msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        if build:
            typer.echo(f"Building sandbox image(s) for target '{image}'...")
            built = build_images(client, target=image)
            for tag in built:
                typer.secho(f"Successfully built: {tag}", fg=typer.colors.GREEN)

        if check:
            typer.echo(f"Checking sandbox image(s) for target '{image}'...")
            status = check_images(client, target=image)
            for tag, exists in status.items():
                if exists:
                    typer.secho(f"Image {tag}: PRESENT", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"Image {tag}: MISSING", fg=typer.colors.YELLOW)
    except ValueError as exc:
        typer.secho(f"Configuration Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as exc:
        typer.secho(f"File Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except DockerException as exc:
        typer.secho(f"Docker Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

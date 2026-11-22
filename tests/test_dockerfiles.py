"""Unit and integration tests for EvalForge sandbox Dockerfiles and build script."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docker.errors import DockerException, ImageNotFound
from typer.testing import CliRunner

from scripts.build_sandboxes import (
    app,
    build_images,
    check_images,
    get_docker_client,
    resolve_targets,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_DOCKERFILE = PROJECT_ROOT / "Dockerfile.sandbox.python"
CPP_DOCKERFILE = PROJECT_ROOT / "Dockerfile.sandbox.cpp"

runner = CliRunner()


# =============================================================================
# Dockerfile Static Directive & Content Tests
# =============================================================================


def test_dockerfiles_exist():
    """Verify both sandbox Dockerfile assets exist in the project root."""
    assert PYTHON_DOCKERFILE.exists(), f"Missing {PYTHON_DOCKERFILE}"
    assert CPP_DOCKERFILE.exists(), f"Missing {CPP_DOCKERFILE}"


@pytest.mark.parametrize(
    "dockerfile_path",
    [PYTHON_DOCKERFILE, CPP_DOCKERFILE],
)
def test_dockerfile_security_invariants(dockerfile_path: Path):
    """Enforce security directives across all sandbox Dockerfiles."""
    content = dockerfile_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    # 1. Non-root user creation with UID 10001
    assert "10001" in content, f"{dockerfile_path.name} must specify UID/GID 10001"
    assert "sandbox_user" in content, f"{dockerfile_path.name} must name sandbox_user"

    # 2. USER directive must be non-root
    user_directives = [line for line in lines if line.startswith("USER")]
    assert len(user_directives) >= 1, f"{dockerfile_path.name} missing USER directive"
    last_user_directive = user_directives[-1]
    assert (
        "10001:10001" in last_user_directive or "sandbox_user" in last_user_directive
    ), f"Last USER directive must be non-root (found {last_user_directive})"
    assert "root" not in last_user_directive.lower()

    # 3. No sudo or root escalation allowed
    assert "sudo" not in content.lower(), f"{dockerfile_path.name} must not grant or install sudo"
    assert "nopasswd" not in content.lower(), f"{dockerfile_path.name} must not grant nopasswd"
    assert "sudoers" not in content.lower(), f"{dockerfile_path.name} must not touch sudoers"

    # 4. WORKDIR must be /workspace/run
    workdir_directives = [line for line in lines if line.startswith("WORKDIR")]
    assert len(workdir_directives) >= 1, f"{dockerfile_path.name} missing WORKDIR directive"
    assert workdir_directives[-1] == "WORKDIR /workspace/run"

    # 5. Default command must keep container alive
    cmd_directives = [line for line in lines if line.startswith("CMD")]
    assert len(cmd_directives) >= 1, f"{dockerfile_path.name} missing CMD directive"
    assert '["tail", "-f", "/dev/null"]' in cmd_directives[-1]


def test_python_dockerfile_specifics():
    """Verify Python-specific requirements in Dockerfile.sandbox.python."""
    content = PYTHON_DOCKERFILE.read_text(encoding="utf-8")

    # Base image
    assert "FROM python:3.11-slim-bookworm" in content

    # Environment variables
    assert "PYTHONDONTWRITEBYTECODE=1" in content
    assert "PYTHONUNBUFFERED=1" in content
    assert "/home/sandbox_user/.local/bin" in content

    # Test harness dependencies
    assert "pytest>=8.0.0" in content
    assert "pytest-json-report>=1.5.0" in content

    # Workspace directory setup with 0755 permissions
    assert "mkdir -p /workspace/run" in content
    assert "chown -R sandbox_user:sandbox_user /workspace/run" in content
    assert "chmod 0755 /workspace/run" in content


def test_cpp_dockerfile_specifics():
    """Verify C++-specific requirements in Dockerfile.sandbox.cpp."""
    content = CPP_DOCKERFILE.read_text(encoding="utf-8")

    # Base image
    assert "FROM gcc:13-bookworm" in content or "FROM debian:bookworm-slim" in content

    # Google Test pre-installation & build
    assert "libgtest-dev" in content
    assert "cmake" in content
    assert "/usr/src/googletest" in content
    assert "ldconfig" in content

    # Minimal Python 3.11 runtime for reporting
    assert "python3" in content

    # Workspace directory setup with 0755 permissions
    assert "mkdir -p /workspace/run" in content
    assert "chown -R sandbox_user:sandbox_user /workspace/run" in content
    assert "chmod 0755 /workspace/run" in content


# =============================================================================
# scripts/build_sandboxes.py Unit Tests
# =============================================================================


def test_resolve_targets():
    """Verify target identifier parsing and validation."""
    all_targets = resolve_targets("all")
    assert "python" in all_targets
    assert "cpp" in all_targets

    py_target = resolve_targets("python")
    assert list(py_target.keys()) == ["python"]
    assert py_target["python"]["tag"] == "evalforge-sandbox-python:latest"

    cpp_target = resolve_targets("cpp")
    assert list(cpp_target.keys()) == ["cpp"]
    assert cpp_target["cpp"]["tag"] == "evalforge-sandbox-cpp:latest"

    # Case-insensitive
    assert resolve_targets("PYTHON") == py_target
    assert resolve_targets("ALL") == all_targets

    with pytest.raises(ValueError, match="Invalid target 'rust'"):
        resolve_targets("rust")


def test_check_images_all_present():
    """Verify check_images returns True for all existing images."""
    mock_client = MagicMock()
    mock_client.images.get.return_value = MagicMock()

    status = check_images(mock_client, target="all")
    assert status == {
        "evalforge-sandbox-python:latest": True,
        "evalforge-sandbox-cpp:latest": True,
    }
    assert mock_client.images.get.call_count == 2


def test_check_images_some_missing():
    """Verify check_images marks missing images as False when ImageNotFound is raised."""
    mock_client = MagicMock()

    def mock_get(tag: str):
        if "python" in tag:
            return MagicMock()
        raise ImageNotFound(f"No such image: {tag}")

    mock_client.images.get.side_effect = mock_get

    status = check_images(mock_client, target="all")
    assert status["evalforge-sandbox-python:latest"] is True
    assert status["evalforge-sandbox-cpp:latest"] is False


def test_check_images_single_target():
    """Verify check_images checks only the requested target."""
    mock_client = MagicMock()
    mock_client.images.get.return_value = MagicMock()

    status = check_images(mock_client, target="python")
    assert status == {"evalforge-sandbox-python:latest": True}
    assert mock_client.images.get.call_count == 1
    mock_client.images.get.assert_called_once_with("evalforge-sandbox-python:latest")


def test_build_images_success(tmp_path: Path):
    """Verify build_images invokes client.images.build with proper parameters."""
    mock_client = MagicMock()
    mock_img_py = MagicMock()
    mock_img_cpp = MagicMock()
    mock_client.images.build.side_effect = [
        (mock_img_py, iter([])),
        (mock_img_cpp, iter([])),
    ]

    # Create dummy Dockerfile files in tmp_path
    (tmp_path / "Dockerfile.sandbox.python").write_text("FROM python\n", encoding="utf-8")
    (tmp_path / "Dockerfile.sandbox.cpp").write_text("FROM gcc\n", encoding="utf-8")

    built = build_images(mock_client, target="all", context_path=tmp_path)
    assert built["evalforge-sandbox-python:latest"] == mock_img_py
    assert built["evalforge-sandbox-cpp:latest"] == mock_img_cpp
    assert mock_client.images.build.call_count == 2


def test_build_images_single_target(tmp_path: Path):
    """Verify build_images handles a single image build."""
    mock_client = MagicMock()
    mock_img_cpp = MagicMock()
    mock_client.images.build.return_value = (mock_img_cpp, iter([]))

    (tmp_path / "Dockerfile.sandbox.cpp").write_text("FROM gcc\n", encoding="utf-8")

    built = build_images(mock_client, target="cpp", context_path=tmp_path)
    assert built == {"evalforge-sandbox-cpp:latest": mock_img_cpp}
    mock_client.images.build.assert_called_once_with(
        path=str(tmp_path),
        dockerfile="Dockerfile.sandbox.cpp",
        tag="evalforge-sandbox-cpp:latest",
        rm=True,
    )


def test_build_images_missing_dockerfile(tmp_path: Path):
    """Verify build_images raises FileNotFoundError if Dockerfile is missing."""
    mock_client = MagicMock()
    with pytest.raises(FileNotFoundError, match="Dockerfile 'Dockerfile.sandbox.python' not found"):
        build_images(mock_client, target="python", context_path=tmp_path)


def test_get_docker_client_success(mocker):
    """Verify get_docker_client pings daemon and returns client."""
    mock_client = MagicMock()
    mock_from_env = mocker.patch("docker.from_env", return_value=mock_client)

    client = get_docker_client()
    assert client == mock_client
    mock_from_env.assert_called_once()
    mock_client.ping.assert_called_once()


def test_get_docker_client_daemon_offline(mocker):
    """Verify get_docker_client wraps DockerException with helpful message."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = DockerException("Connection refused")
    mocker.patch("docker.from_env", return_value=mock_client)

    with pytest.raises(DockerException, match="Cannot connect to the Docker daemon"):
        get_docker_client()


# =============================================================================
# CLI Interface Tests (Typer Runner)
# =============================================================================


def test_cli_no_args():
    """Verify CLI exits cleanly with help note when neither --check nor --build is passed."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "No action specified" in result.output


def test_cli_check_command(mocker):
    """Verify CLI --check executes check_images and prints status."""
    mock_client = MagicMock()
    mock_client.images.get.return_value = MagicMock()
    mocker.patch("scripts.build_sandboxes.get_docker_client", return_value=mock_client)

    result = runner.invoke(app, ["--check", "--image", "all"])
    assert result.exit_code == 0
    assert "PRESENT" in result.output
    assert "evalforge-sandbox-python:latest" in result.output
    assert "evalforge-sandbox-cpp:latest" in result.output


def test_cli_build_command(mocker):
    """Verify CLI --build executes build_images and prints success."""
    mock_client = MagicMock()
    mocker.patch("scripts.build_sandboxes.get_docker_client", return_value=mock_client)
    mocker.patch(
        "scripts.build_sandboxes.build_images",
        return_value={"evalforge-sandbox-python:latest": MagicMock()},
    )

    result = runner.invoke(app, ["--build", "--image", "python"])
    assert result.exit_code == 0
    assert "Successfully built: evalforge-sandbox-python:latest" in result.output


def test_cli_daemon_failure_graceful_exit(mocker):
    """Verify CLI catches DockerException and exits with code 1 without traceback."""
    mocker.patch(
        "scripts.build_sandboxes.get_docker_client",
        side_effect=DockerException("Error while fetching server API version: daemon offline"),
    )

    result = runner.invoke(app, ["--check"])
    assert result.exit_code == 1
    assert "Error: Cannot connect to the Docker daemon" in result.output
    assert "Traceback (most recent call last)" not in result.output


def test_cli_invalid_target_error(mocker):
    """Verify CLI exits with code 1 on unsupported image target."""
    mock_client = MagicMock()
    mocker.patch("scripts.build_sandboxes.get_docker_client", return_value=mock_client)

    result = runner.invoke(app, ["--check", "--image", "unsupported_lang"])
    assert result.exit_code == 1
    assert "Configuration Error" in result.output
    assert "Invalid target 'unsupported_lang'" in result.output

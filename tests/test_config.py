"""Unit tests for EvalForge configuration management and environment parsing."""

import pytest
from pydantic import ValidationError

from evalforge.core.config import Settings, get_settings
from evalforge.core.constants import (
    DEFAULT_CPP_COMPILER_RAM_LIMIT_MB,
    DEFAULT_CPP_COMPILER_TIMEOUT_SEC,
    DEFAULT_DOCKER_IMAGE_CPP,
    DEFAULT_DOCKER_IMAGE_PYTHON,
    DEFAULT_EXEC_TIMEOUT_SEC,
    DEFAULT_POOL_SIZE,
    DEFAULT_RAM_LIMIT_MB,
)


def test_default_settings():
    """Verify that default settings match architectural constants."""
    settings = Settings()
    assert settings.docker_pool_size == DEFAULT_POOL_SIZE
    assert settings.ram_limit_mb == DEFAULT_RAM_LIMIT_MB
    assert settings.exec_timeout_sec == DEFAULT_EXEC_TIMEOUT_SEC
    assert settings.db_path == "evalforge.db"
    assert settings.log_level == "INFO"
    assert settings.audit_log_dir == "logs"
    assert settings.cpp_compiler_ram_limit_mb == DEFAULT_CPP_COMPILER_RAM_LIMIT_MB
    assert settings.cpp_compiler_timeout_sec == DEFAULT_CPP_COMPILER_TIMEOUT_SEC
    assert settings.docker_image_python == DEFAULT_DOCKER_IMAGE_PYTHON
    assert settings.docker_image_cpp == DEFAULT_DOCKER_IMAGE_CPP


def test_env_override(monkeypatch):
    """Verify that environment variables with EVALFORGE_ prefix override defaults."""
    monkeypatch.setenv("EVALFORGE_DOCKER_POOL_SIZE", "8")
    monkeypatch.setenv("EVALFORGE_RAM_LIMIT_MB", "512")
    monkeypatch.setenv("EVALFORGE_EXEC_TIMEOUT_SEC", "4.5")
    monkeypatch.setenv("EVALFORGE_DB_PATH", "/tmp/test_evalforge.db")
    monkeypatch.setenv("EVALFORGE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("EVALFORGE_AUDIT_LOG_DIR", "/tmp/audit_logs")
    monkeypatch.setenv("EVALFORGE_CPP_COMPILER_RAM_LIMIT_MB", "1024")
    monkeypatch.setenv("EVALFORGE_CPP_COMPILER_TIMEOUT_SEC", "15.0")
    monkeypatch.setenv("EVALFORGE_DOCKER_IMAGE_PYTHON", "custom-python:1.0")
    monkeypatch.setenv("EVALFORGE_DOCKER_IMAGE_CPP", "custom-cpp:1.0")

    settings = Settings()
    assert settings.docker_pool_size == 8
    assert settings.ram_limit_mb == 512
    assert settings.exec_timeout_sec == 4.5
    assert settings.db_path == "/tmp/test_evalforge.db"
    assert settings.log_level == "DEBUG"
    assert settings.audit_log_dir == "/tmp/audit_logs"
    assert settings.cpp_compiler_ram_limit_mb == 1024
    assert settings.cpp_compiler_timeout_sec == 15.0
    assert settings.docker_image_python == "custom-python:1.0"
    assert settings.docker_image_cpp == "custom-cpp:1.0"


def test_case_insensitive_env(monkeypatch):
    """Verify case-insensitivity of environment variable prefix."""
    monkeypatch.setenv("evalforge_ram_limit_mb", "1024")
    settings = Settings()
    assert settings.ram_limit_mb == 1024


def test_invalid_settings_validation():
    """Verify that invalid configurations raise Pydantic validation errors."""
    with pytest.raises(ValidationError):
        Settings(docker_pool_size=0)

    with pytest.raises(ValidationError):
        Settings(ram_limit_mb=8)  # Must be >= 16 MB

    with pytest.raises(ValidationError):
        Settings(exec_timeout_sec=-1.0)  # Must be > 0.0

    with pytest.raises(ValidationError):
        Settings(cpp_compiler_ram_limit_mb=16)  # Must be >= 64 MB

    with pytest.raises(ValidationError):
        Settings(cpp_compiler_timeout_sec=0.0)  # Must be > 0.0


def test_get_settings_cached():
    """Verify get_settings returns a singleton cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

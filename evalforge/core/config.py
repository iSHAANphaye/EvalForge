"""Configuration management using Pydantic Settings for EvalForge."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from evalforge.core.constants import (
    DEFAULT_CPP_COMPILER_RAM_LIMIT_MB,
    DEFAULT_CPP_COMPILER_TIMEOUT_SEC,
    DEFAULT_DOCKER_IMAGE_CPP,
    DEFAULT_DOCKER_IMAGE_PYTHON,
    DEFAULT_EXEC_TIMEOUT_SEC,
    DEFAULT_POOL_SIZE,
    DEFAULT_RAM_LIMIT_MB,
)


class Settings(BaseSettings):
    """Central configuration for EvalForge runtime, sandboxing, and storage."""

    model_config = SettingsConfigDict(
        env_prefix="EVALFORGE_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    docker_pool_size: int = Field(
        default=DEFAULT_POOL_SIZE,
        ge=1,
        description="Number of pre-warmed sandbox containers to maintain.",
    )
    ram_limit_mb: int = Field(
        default=DEFAULT_RAM_LIMIT_MB,
        ge=16,
        description="Default RAM memory limit for sandbox container in MB.",
    )
    exec_timeout_sec: float = Field(
        default=DEFAULT_EXEC_TIMEOUT_SEC,
        gt=0.0,
        description="Default execution timeout watchdog in seconds.",
    )
    db_path: str = Field(
        default="evalforge.db",
        description="File path for the SQLite database.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    audit_log_dir: str = Field(
        default="logs",
        description="Directory path for JSONL event telemetry audit logs.",
    )
    cpp_compiler_ram_limit_mb: int = Field(
        default=DEFAULT_CPP_COMPILER_RAM_LIMIT_MB,
        ge=64,
        description="Memory limit for C++ compilation in MB.",
    )
    cpp_compiler_timeout_sec: float = Field(
        default=DEFAULT_CPP_COMPILER_TIMEOUT_SEC,
        gt=0.0,
        description="Timeout for C++ compilation in seconds.",
    )
    docker_image_python: str = Field(
        default=DEFAULT_DOCKER_IMAGE_PYTHON,
        description="Docker image tag for Python sandbox.",
    )
    docker_image_cpp: str = Field(
        default=DEFAULT_DOCKER_IMAGE_CPP,
        description="Docker image tag for C++ sandbox.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton application settings instance."""
    return Settings()

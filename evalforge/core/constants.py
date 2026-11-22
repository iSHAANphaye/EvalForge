"""Constants, rubric weights, limits, and enumeration types for EvalForge."""

from enum import StrEnum

# -------------------------------------------------------------------------
# Rubric Weights (Axis 1 to 4)
# -------------------------------------------------------------------------
WEIGHT_FUNCTIONAL: float = 0.40
WEIGHT_EDGE_SCALE: float = 0.30
WEIGHT_ANTI_CHEAT: float = 0.20
WEIGHT_CODE_HYGIENE: float = 0.10

# Maximum possible points per axis
MAX_POINTS_FUNCTIONAL: float = 40.0
MAX_POINTS_EDGE_SCALE: float = 30.0
MAX_POINTS_ANTI_CHEAT: float = 20.0
MAX_POINTS_CODE_HYGIENE: float = 10.0
MAX_POINTS_COMPOSITE: float = 100.0

# -------------------------------------------------------------------------
# Default SLAs and Sandbox Limits
# -------------------------------------------------------------------------
DEFAULT_RAM_LIMIT_MB: int = 256
DEFAULT_EXEC_TIMEOUT_SEC: float = 2.0
DEFAULT_CPU_QUOTA: int = 100000  # 1 vCPU (100,000 microseconds per 100ms period)
DEFAULT_PID_LIMIT: int = 64
DEFAULT_POOL_SIZE: int = 4
DEFAULT_STDOUT_MAX_BYTES: int = 16384  # 16 KB

# C++ Compilation Defaults
DEFAULT_CPP_COMPILER_RAM_LIMIT_MB: int = 768
DEFAULT_CPP_COMPILER_TIMEOUT_SEC: float = 10.0

# -------------------------------------------------------------------------
# Sandbox Docker Images
# -------------------------------------------------------------------------
DEFAULT_DOCKER_IMAGE_PYTHON: str = "evalforge-sandbox-python:latest"
DEFAULT_DOCKER_IMAGE_CPP: str = "evalforge-sandbox-cpp:latest"

# -------------------------------------------------------------------------
# CLI & Execution Exit Codes
# -------------------------------------------------------------------------
EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_EVAL_FAILED: int = 1
EXIT_CODE_CONFIG_ERROR: int = 2
EXIT_CODE_TIMEOUT: int = 124
EXIT_CODE_OOM: int = 137

# -------------------------------------------------------------------------
# ErrorTypeEnum
# -------------------------------------------------------------------------
class ErrorTypeEnum(StrEnum):
    """Standardized error classifications for sandbox execution and grading."""

    NONE = "NONE"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    TIMEOUT = "TIMEOUT"
    OOM = "OOM"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    CHEAT_DETECTED = "CHEAT_DETECTED"
    PATCH_APPLICATION_ERROR = "PATCH_APPLICATION_ERROR"
    SANDBOX_ERROR = "SANDBOX_ERROR"

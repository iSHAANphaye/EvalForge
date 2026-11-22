"""Unit tests for EvalForge typed exception hierarchy and error formatting."""


from evalforge.core.exceptions import (
    CheatDetectedError,
    DatabaseError,
    EvalForgeError,
    ExecutionTimeoutError,
    ForkBombError,
    MemoryExhaustionError,
    PatchApplicationError,
    SandboxError,
    SandboxTimeoutError,
    TaskNotFoundError,
)


def test_base_exception():
    """Verify base EvalForgeError inherits from Exception and preserves message."""
    err = EvalForgeError("Custom base error message")
    assert isinstance(err, Exception)
    assert str(err) == "Custom base error message"
    assert err.message == "Custom base error message"


def test_sandbox_exceptions_inheritance():
    """Verify sandbox exceptions inherit from SandboxError and EvalForgeError."""
    # Base SandboxError
    s_err = SandboxError("Sandbox failed to initialize")
    assert isinstance(s_err, EvalForgeError)

    # SandboxTimeoutError
    st_err = SandboxTimeoutError(timeout_sec=1.5)
    assert isinstance(st_err, SandboxError)
    assert isinstance(st_err, TimeoutError)
    assert isinstance(st_err, EvalForgeError)
    assert st_err.timeout_sec == 1.5

    # ExecutionTimeoutError
    t_err = ExecutionTimeoutError(timeout_sec=2.5)
    assert isinstance(t_err, SandboxError)
    assert isinstance(t_err, EvalForgeError)
    assert t_err.timeout_sec == 2.5
    assert "2.50s" in str(t_err)

    # MemoryExhaustionError
    m_err = MemoryExhaustionError(limit_mb=256)
    assert isinstance(m_err, SandboxError)
    assert m_err.limit_mb == 256
    assert "256MB" in str(m_err)

    # ForkBombError
    f_err = ForkBombError(pid_limit=64)
    assert isinstance(f_err, SandboxError)
    assert f_err.pid_limit == 64
    assert "64" in str(f_err)


def test_cheat_detected_error():
    """Verify CheatDetectedError captures rule violations and metadata dictionary."""
    details = {"banned_import": "os", "lineno": 12}
    err = CheatDetectedError(
        message="Banned module import detected.",
        rule_violated="NO_SYSTEM_IMPORTS",
        details=details,
    )
    assert isinstance(err, EvalForgeError)
    assert err.rule_violated == "NO_SYSTEM_IMPORTS"
    assert err.details == details
    assert str(err) == "Banned module import detected."


def test_task_not_found_error():
    """Verify TaskNotFoundError stores task_id and produces descriptive error."""
    err = TaskNotFoundError(task_id="EF-PY-999")
    assert isinstance(err, EvalForgeError)
    assert err.task_id == "EF-PY-999"
    assert "EF-PY-999" in str(err)

    # Custom message override
    custom_err = TaskNotFoundError(task_id="EF-PY-999", message="Cannot load benchmark file")
    assert str(custom_err) == "Cannot load benchmark file"


def test_patch_and_database_errors():
    """Verify PatchApplicationError and DatabaseError hierarchy."""
    p_err = PatchApplicationError("Failed to apply git diff")
    assert isinstance(p_err, EvalForgeError)
    assert str(p_err) == "Failed to apply git diff"

    db_err = DatabaseError("SQLite lock timeout")
    assert isinstance(db_err, EvalForgeError)
    assert str(db_err) == "SQLite lock timeout"

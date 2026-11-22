"""FastAPI REST application for EvalForge evaluation harness."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evalforge.api.routes import router
from evalforge.core.config import Settings, get_settings
from evalforge.core.logging import get_logger
from evalforge.sandbox.manager import SandboxPoolManager
from evalforge.storage.db import init_db
from evalforge.storage.jsonl_logger import JSONLEventLogger
from evalforge.tasks.loader import TaskRegistry, get_global_registry

logger = get_logger("api.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup initialization and graceful shutdown."""
    settings: Settings = getattr(app.state, "settings", None) or get_settings()

    # 1. Initialize SQLite Database
    try:
        await init_db(settings.db_path)
        logger.info(f"Database initialized at {settings.db_path}")
    except Exception as exc:
        logger.warning(f"Failed to initialize database during startup: {exc}")

    # 2. Discover and register benchmark tasks
    if not getattr(app.state, "task_registry", None):
        registry = TaskRegistry()
        tasks_dir = Path("evalforge/tasks/bank")
        if tasks_dir.exists():
            loaded = registry.load_tasks_from_directory(tasks_dir)
            logger.info(f"Loaded {loaded} tasks from {tasks_dir}")
        else:
            global_reg = get_global_registry()
            for task in global_reg.list_tasks():
                registry.register(task)
        app.state.task_registry = registry

    # 3. Initialize Pre-Warmed Container Pool
    if not getattr(app.state, "pool_manager", None):
        pool_manager = None
        try:
            pool_manager = SandboxPoolManager(settings=settings)
            if pool_manager.is_docker_available():
                await pool_manager.warmup()
                logger.info("Sandbox pool warmed up successfully.")
            else:
                logger.warning("Docker daemon is offline; pool manager initialized in degraded mode.")
        except Exception as exc:
            logger.warning(f"Sandbox pool initialization failed: {exc}")

        app.state.pool_manager = pool_manager

    # 4. Initialize JSONL Event Logger
    app.state.jsonl_logger = JSONLEventLogger(log_dir=settings.audit_log_dir)

    yield

    # Shutdown: Clean up containers
    try:
        pool_mgr = getattr(app.state, "pool_manager", None)
        if pool_mgr is not None and pool_mgr.is_docker_available():
            await pool_mgr.cleanup()
            logger.info("Sandbox pool cleaned up successfully.")
    except Exception as exc:
        logger.warning(f"Error during sandbox pool cleanup: {exc}")



def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title="EvalForge REST API",
        version="1.0.0",
        description="High-throughput container-isolated LLM code evaluation and rubric grading harness.",
        lifespan=lifespan,
    )

    app.state.settings = app_settings

    # Configure CORS for dashboard and UI integrations
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/")
    async def root():
        """Root endpoint returning service identity."""
        return {
            "service": "EvalForge",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()

__all__ = ["create_app", "app"]

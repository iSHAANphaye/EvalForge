"""FastAPI REST service package for EvalForge."""

from evalforge.api.app import app, create_app
from evalforge.api.routes import router

__all__ = ["app", "create_app", "router"]

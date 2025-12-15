"""
API module for PlanMod.

FastAPI-based REST API for the processing pipeline.
"""

from backend.api.server import app, create_app

__all__ = ["app", "create_app"]



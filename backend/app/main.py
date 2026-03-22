"""FastAPI application entrypoint for the backend."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_application()

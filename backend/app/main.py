"""FastAPI application entrypoint for the backend."""

from time import perf_counter
import logging

from fastapi import Request
from fastapi import FastAPI

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

request_logger = logging.getLogger("app.request")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    @application.middleware("http")
    async def log_request_flow(request: Request, call_next):
        start_time = perf_counter()
        request_logger.info(
            "request.start method=%s path=%s query=%s client=%s",
            request.method,
            request.url.path,
            request.url.query,
            request.client.host if request.client else "unknown",
        )
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            request_logger.exception(
                "request.error method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = round((perf_counter() - start_time) * 1000, 2)
        request_logger.info(
            "request.end method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_application()

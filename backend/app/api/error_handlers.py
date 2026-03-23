"""Exception handlers for API responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.data_service.exceptions import (
    DataNotFoundError,
    DataServiceError,
    InvalidRequestError,
    ProviderError,
)


def register_exception_handlers(application: FastAPI) -> None:
    """Register application-wide exception handlers."""

    @application.exception_handler(InvalidRequestError)
    async def handle_invalid_request(
        request: Request,
        exc: InvalidRequestError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(DataNotFoundError)
    async def handle_not_found(
        request: Request,
        exc: DataNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(ProviderError)
    async def handle_provider_error(
        request: Request,
        exc: ProviderError,
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @application.exception_handler(DataServiceError)
    async def handle_data_service_error(
        request: Request,
        exc: DataServiceError,
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

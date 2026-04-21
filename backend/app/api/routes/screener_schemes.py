"""Routes for factor-first screener schemes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_screener_scheme_service
from app.schemas.screener_scheme import (
    CreateScreenerSchemeRequest,
    CreateScreenerSchemeVersionRequest,
    ScreenerSchemeDetailResponse,
    ScreenerSchemeListResponse,
    ScreenerSchemeSummary,
    ScreenerSchemeVersion,
    ScreenerSchemeVersionListResponse,
    ScreenerSchemeVersionSummary,
    UpdateScreenerSchemeRequest,
)
from app.services.screener_service.scheme_service import (
    ScreenerSchemeNotFoundError,
    ScreenerSchemeService,
    ScreenerSchemeVersionNotFoundError,
)

router = APIRouter(prefix="/screener/schemes", tags=["screener-schemes"])


@router.get("", response_model=ScreenerSchemeListResponse)
def list_schemes(
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeListResponse:
    items = [_build_scheme_summary(item, service) for item in service.list_schemes()]
    return ScreenerSchemeListResponse(items=items, total=len(items))


@router.post("", response_model=ScreenerSchemeDetailResponse)
def create_scheme(
    request: CreateScreenerSchemeRequest,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeDetailResponse:
    scheme = service.create_scheme(request)
    return ScreenerSchemeDetailResponse(scheme=scheme)


@router.get("/{scheme_id}", response_model=ScreenerSchemeDetailResponse)
def get_scheme(
    scheme_id: str,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeDetailResponse:
    try:
        scheme = service.get_scheme(scheme_id)
    except ScreenerSchemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Screener scheme not found.") from exc
    current_version = service.get_current_version(scheme_id)
    recent_versions = [
        _build_version_summary(item) for item in service.list_versions(scheme_id)[:5]
    ]
    return ScreenerSchemeDetailResponse(
        scheme=scheme,
        current_version_detail=current_version,
        recent_versions=recent_versions,
    )


@router.patch("/{scheme_id}", response_model=ScreenerSchemeDetailResponse)
def update_scheme(
    scheme_id: str,
    request: UpdateScreenerSchemeRequest,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeDetailResponse:
    try:
        scheme = service.update_scheme(scheme_id, request)
    except ScreenerSchemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Screener scheme not found.") from exc
    current_version = service.get_current_version(scheme_id)
    recent_versions = [
        _build_version_summary(item) for item in service.list_versions(scheme_id)[:5]
    ]
    return ScreenerSchemeDetailResponse(
        scheme=scheme,
        current_version_detail=current_version,
        recent_versions=recent_versions,
    )


@router.get(
    "/{scheme_id}/versions",
    response_model=ScreenerSchemeVersionListResponse,
)
def list_scheme_versions(
    scheme_id: str,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeVersionListResponse:
    try:
        versions = service.list_versions(scheme_id)
    except ScreenerSchemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Screener scheme not found.") from exc
    items = [_build_version_summary(item) for item in versions]
    return ScreenerSchemeVersionListResponse(
        scheme_id=scheme_id,
        items=items,
        total=len(items),
    )


@router.post(
    "/{scheme_id}/versions",
    response_model=ScreenerSchemeVersion,
)
def create_scheme_version(
    scheme_id: str,
    request: CreateScreenerSchemeVersionRequest,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeVersion:
    try:
        return service.create_version(scheme_id, request)
    except ScreenerSchemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Screener scheme not found.") from exc


@router.get(
    "/{scheme_id}/versions/{scheme_version}",
    response_model=ScreenerSchemeVersion,
)
def get_scheme_version(
    scheme_id: str,
    scheme_version: str,
    service: ScreenerSchemeService = Depends(get_screener_scheme_service),
) -> ScreenerSchemeVersion:
    try:
        service.get_scheme(scheme_id)
        return service.get_version(scheme_id, scheme_version)
    except ScreenerSchemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Screener scheme not found.") from exc
    except ScreenerSchemeVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Screener scheme version not found.",
        ) from exc


def _build_scheme_summary(
    scheme,
    service: ScreenerSchemeService,
) -> ScreenerSchemeSummary:
    current_version = service.get_current_version(scheme.scheme_id)
    return ScreenerSchemeSummary(
        scheme_id=scheme.scheme_id,
        name=scheme.name,
        description=scheme.description,
        status=scheme.status,
        current_version=scheme.current_version,
        is_builtin=scheme.is_builtin,
        is_default=scheme.is_default,
        updated_at=scheme.updated_at,
        current_version_summary=(
            _build_version_summary(current_version) if current_version is not None else None
        ),
    )


def _build_version_summary(
    version: ScreenerSchemeVersion,
) -> ScreenerSchemeVersionSummary:
    return ScreenerSchemeVersionSummary(
        scheme_version=version.scheme_version,
        version_label=version.version_label,
        created_at=version.created_at,
        change_note=version.change_note,
        snapshot_hash=version.snapshot_hash,
    )

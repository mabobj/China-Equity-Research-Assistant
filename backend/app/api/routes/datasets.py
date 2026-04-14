"""数据集相关路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_dataset_service, get_label_service
from app.schemas.dataset import (
    FeatureDatasetBuildRequest,
    FeatureDatasetResponse,
    LabelDatasetBuildRequest,
    LabelDatasetResponse,
)
from app.schemas.lineage import LineageMetadata

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/features/{dataset_version}", response_model=FeatureDatasetResponse)
def get_feature_dataset(
    dataset_version: str,
    service: Any = Depends(get_dataset_service),
) -> FeatureDatasetResponse:
    try:
        return service.get_feature_dataset(dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/features/{dataset_version}/lineage", response_model=LineageMetadata)
def get_feature_dataset_lineage(
    dataset_version: str,
    service: Any = Depends(get_dataset_service),
) -> LineageMetadata:
    try:
        response = service.get_feature_dataset(dataset_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if response.summary.lineage_metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"lineage metadata is unavailable: {dataset_version}",
        )
    return response.summary.lineage_metadata


@router.post("/features/build", response_model=FeatureDatasetResponse)
def build_feature_dataset(
    request: FeatureDatasetBuildRequest,
    service: Any = Depends(get_dataset_service),
) -> FeatureDatasetResponse:
    try:
        return service.build_feature_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/labels/{label_version}", response_model=LabelDatasetResponse)
def get_label_dataset(
    label_version: str,
    service: Any = Depends(get_label_service),
) -> LabelDatasetResponse:
    try:
        return service.get_label_dataset(label_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/labels/{label_version}/lineage", response_model=LineageMetadata)
def get_label_dataset_lineage(
    label_version: str,
    service: Any = Depends(get_label_service),
) -> LineageMetadata:
    try:
        response = service.get_label_dataset(label_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if response.summary.lineage_metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"lineage metadata is unavailable: {label_version}",
        )
    return response.summary.lineage_metadata


@router.post("/labels/build", response_model=LabelDatasetResponse)
def build_label_dataset(
    request: LabelDatasetBuildRequest,
    service: Any = Depends(get_label_service),
) -> LabelDatasetResponse:
    try:
        return service.build_label_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

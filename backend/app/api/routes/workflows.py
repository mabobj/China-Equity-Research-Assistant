"""Workflow runtime routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_workflow_runtime_service
from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
    ScreenerWorkflowRunRequest,
    SingleStockWorkflowRunRequest,
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/single-stock/run", response_model=WorkflowRunResponse)
def run_single_stock_workflow(
    request: SingleStockWorkflowRunRequest,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunResponse:
    try:
        return service.run_single_stock_workflow(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/deep-review/run", response_model=WorkflowRunResponse)
def run_deep_review_workflow(
    request: DeepReviewWorkflowRunRequest,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunResponse:
    try:
        return service.run_deep_review_workflow(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/screener/run", response_model=WorkflowRunResponse)
def run_screener_workflow(
    request: ScreenerWorkflowRunRequest,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunResponse:
    try:
        return service.run_screener_workflow(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=WorkflowRunDetailResponse)
def get_workflow_run_detail(
    run_id: str,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunDetailResponse:
    try:
        return service.get_run_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found.") from exc

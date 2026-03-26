"""Workflow 运行相关路由。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_workflow_runtime_service
from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
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
    """运行单票完整研判 workflow。"""
    try:
        return service.run_single_stock_workflow(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/deep-review/run", response_model=WorkflowRunResponse)
def run_deep_review_workflow(
    request: DeepReviewWorkflowRunRequest,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunResponse:
    """运行深筛复核 workflow。"""
    try:
        return service.run_deep_review_workflow(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=WorkflowRunDetailResponse)
def get_workflow_run_detail(
    run_id: str,
    service: Any = Depends(get_workflow_runtime_service),
) -> WorkflowRunDetailResponse:
    """读取 workflow 运行详情。"""
    try:
        return service.get_run_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found.") from exc

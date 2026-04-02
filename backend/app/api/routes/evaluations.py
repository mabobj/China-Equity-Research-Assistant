"""评估相关路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_evaluation_service
from app.schemas.evaluation import ModelEvaluationResponse

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/models/{model_version}", response_model=ModelEvaluationResponse)
def get_model_evaluation(
    model_version: str,
    service: Any = Depends(get_evaluation_service),
) -> ModelEvaluationResponse:
    try:
        return service.get_model_evaluation(model_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


"""选股器路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_deep_screener_pipeline, get_screener_pipeline
from app.schemas.screener import DeepScreenerRunResponse, ScreenerRunResponse

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/run", response_model=ScreenerRunResponse)
def run_screener(
    max_symbols: Optional[int] = Query(default=None, ge=1),
    top_n: Optional[int] = Query(default=None, ge=1),
    pipeline: Any = Depends(get_screener_pipeline),
) -> ScreenerRunResponse:
    """运行规则初筛选股器。"""
    return pipeline.run_screener(
        max_symbols=max_symbols,
        top_n=top_n,
    )


@router.get("/deep-run", response_model=DeepScreenerRunResponse)
def run_deep_screener(
    max_symbols: Optional[int] = Query(default=None, ge=1),
    top_n: Optional[int] = Query(default=None, ge=1),
    deep_top_k: Optional[int] = Query(default=None, ge=1),
    pipeline: Any = Depends(get_deep_screener_pipeline),
) -> DeepScreenerRunResponse:
    """运行深筛聚合选股器。"""
    return pipeline.run_deep_screener(
        max_symbols=max_symbols,
        top_n=top_n,
        deep_top_k=deep_top_k,
    )

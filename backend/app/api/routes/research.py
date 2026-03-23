"""单票研究路由。"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_research_manager
from app.schemas.research import ResearchReport

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/{symbol}", response_model=ResearchReport)
def get_research_report(
    symbol: str,
    manager: Any = Depends(get_research_manager),
) -> ResearchReport:
    """返回结构化单票研究报告。"""
    return manager.get_research_report(symbol)

"""数据补全路由。"""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_data_refresh_service
from app.schemas.data_refresh import DataRefreshRequest, DataRefreshStatus

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/refresh", response_model=DataRefreshStatus)
def get_data_refresh_status(
    refresh_service: Any = Depends(get_data_refresh_service),
) -> DataRefreshStatus:
    """读取当前手动数据补全任务状态。"""
    return refresh_service.get_status()


@router.post(
    "/refresh",
    response_model=DataRefreshStatus,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_data_refresh(
    payload: DataRefreshRequest,
    refresh_service: Any = Depends(get_data_refresh_service),
) -> DataRefreshStatus:
    """启动一次手动数据补全任务。"""
    return refresh_service.start_manual_refresh(max_symbols=payload.max_symbols)

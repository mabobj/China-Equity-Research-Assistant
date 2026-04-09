"""Provider 诊断只读路由。"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_market_data_service
from app.schemas.provider import (
    CapabilityHealthReport,
    CapabilityPolicyReport,
)
from app.services.data_service.market_data_service import MarketDataService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/capabilities", response_model=list[CapabilityPolicyReport])
def get_provider_capability_policies(
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> list[CapabilityPolicyReport]:
    """返回当前 capability 级别的 provider 策略矩阵。"""

    return market_data_service.get_capability_policy_reports()


@router.get("/health", response_model=list[CapabilityHealthReport])
def get_provider_capability_health(
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> list[CapabilityHealthReport]:
    """返回全部 capability 的健康与诊断摘要。"""

    return market_data_service.get_capability_health_reports()


@router.get("/health/{capability}", response_model=CapabilityHealthReport)
def get_single_provider_capability_health(
    capability: str,
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> CapabilityHealthReport:
    """返回单个 capability 的健康与诊断摘要。"""

    return market_data_service.get_capability_health_report(capability)

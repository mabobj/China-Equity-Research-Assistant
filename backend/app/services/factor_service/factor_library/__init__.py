"""选股 v2 最小因子库。"""

from app.services.factor_service.factor_library.event_factors import build_event_group
from app.services.factor_service.factor_library.growth_factors import build_growth_group
from app.services.factor_service.factor_library.low_vol_factors import build_low_vol_group
from app.services.factor_service.factor_library.quality_factors import build_quality_group
from app.services.factor_service.factor_library.trend_factors import build_trend_group

__all__ = [
    "build_event_group",
    "build_growth_group",
    "build_low_vol_group",
    "build_quality_group",
    "build_trend_group",
]

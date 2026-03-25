"""Factor snapshot service."""

from __future__ import annotations

from typing import Optional

from app.schemas.factor import FactorSnapshot
from app.schemas.technical import TechnicalSnapshot
from app.services.factor_service.composite import (
    build_alpha_score,
    build_trigger_score,
)
from app.services.feature_service.technical_analysis_service import (
    TechnicalAnalysisService,
)


class FactorSnapshotService:
    """Build minimal factor snapshots from technical inputs."""

    def __init__(self, technical_analysis_service: TechnicalAnalysisService) -> None:
        self._technical_analysis_service = technical_analysis_service

    def get_factor_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FactorSnapshot:
        technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        return self.build_from_technical_snapshot(technical_snapshot)

    def build_from_technical_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
    ) -> FactorSnapshot:
        return FactorSnapshot(
            symbol=technical_snapshot.symbol,
            as_of_date=technical_snapshot.as_of_date,
            latest_close=technical_snapshot.latest_close,
            trend_state=technical_snapshot.trend_state,
            trend_score=technical_snapshot.trend_score,
            support_level=technical_snapshot.support_level,
            resistance_level=technical_snapshot.resistance_level,
            alpha_score=build_alpha_score(technical_snapshot),
            trigger_score=build_trigger_score(technical_snapshot),
        )


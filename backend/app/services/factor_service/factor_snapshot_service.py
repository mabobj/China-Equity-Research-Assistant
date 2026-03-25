"""选股 v2 因子快照服务。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.schemas.factor import FactorGroupScore, FactorSnapshot
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.exceptions import DataServiceError, InsufficientDataError
from app.services.data_service.market_data_service import MarketDataService
from app.services.factor_service.base import FactorBuildInputs, FactorGroupResult
from app.services.factor_service.composite import (
    build_alpha_score,
    build_risk_score,
    build_trigger_score,
)
from app.services.factor_service.factor_library import (
    build_event_group,
    build_growth_group,
    build_low_vol_group,
    build_quality_group,
    build_trend_group,
)
from app.services.factor_service.preprocess import clamp_optional_score
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService


class FactorSnapshotService:
    """构建最小可用的多因子快照。"""

    def __init__(
        self,
        technical_analysis_service: TechnicalAnalysisService,
        market_data_service: MarketDataService,
    ) -> None:
        self._technical_analysis_service = technical_analysis_service
        self._market_data_service = market_data_service

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
        daily_bar_response = self._market_data_service.get_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        return self.build_from_inputs(
            FactorBuildInputs(
                symbol=technical_snapshot.symbol,
                technical_snapshot=technical_snapshot,
                daily_bars=daily_bar_response.bars,
                financial_summary=self._safe_get_financial_summary(symbol),
                announcements=self._safe_get_recent_announcements(
                    symbol=symbol,
                    as_of_date=technical_snapshot.as_of_date,
                ),
            )
        )

    def build_from_inputs(self, inputs: FactorBuildInputs) -> FactorSnapshot:
        """基于结构化输入构建因子快照。"""
        closes = [float(bar.close) for bar in inputs.daily_bars if bar.close is not None]
        if len(closes) < 30:
            raise InsufficientDataError(
                "构建因子快照至少需要 30 条有效日线数据，当前不足。",
            )

        group_results = [
            build_trend_group(closes),
            build_quality_group(inputs.financial_summary),
            build_growth_group(inputs.financial_summary),
            build_low_vol_group(closes, inputs.technical_snapshot),
            build_event_group(inputs.announcements, as_of_date=inputs.technical_snapshot.as_of_date),
        ]
        group_scores = [_to_group_score(item) for item in group_results]
        alpha_score = build_alpha_score(group_scores)
        risk_score = build_risk_score(group_scores, inputs.technical_snapshot)
        trigger_score = build_trigger_score(
            inputs.technical_snapshot,
            alpha_score=alpha_score.total_score,
            risk_score=risk_score.total_score,
        )

        return FactorSnapshot(
            symbol=inputs.symbol,
            as_of_date=inputs.technical_snapshot.as_of_date,
            raw_factors=_build_factor_dict(group_results, field_name="raw_value"),
            normalized_factors=_build_factor_dict(
                group_results,
                field_name="normalized_score",
            ),
            factor_group_scores=group_scores,
            alpha_score=alpha_score,
            trigger_score=trigger_score,
            risk_score=risk_score,
        )

    def build_from_technical_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
    ) -> FactorSnapshot:
        """兼容旧调用方式。"""
        daily_bar_response = self._market_data_service.get_daily_bars(
            technical_snapshot.symbol,
            start_date=(technical_snapshot.as_of_date - timedelta(days=400)).isoformat(),
            end_date=technical_snapshot.as_of_date.isoformat(),
        )
        return self.build_from_inputs(
            FactorBuildInputs(
                symbol=technical_snapshot.symbol,
                technical_snapshot=technical_snapshot,
                daily_bars=daily_bar_response.bars,
                financial_summary=self._safe_get_financial_summary(technical_snapshot.symbol),
                announcements=self._safe_get_recent_announcements(
                    symbol=technical_snapshot.symbol,
                    as_of_date=technical_snapshot.as_of_date,
                ),
            )
        )

    def _safe_get_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        try:
            return self._market_data_service.get_stock_financial_summary(symbol)
        except DataServiceError:
            return None

    def _safe_get_recent_announcements(
        self,
        *,
        symbol: str,
        as_of_date: date,
    ) -> list[AnnouncementItem]:
        start_date = (as_of_date - timedelta(days=30)).isoformat()
        try:
            response = self._market_data_service.get_stock_announcements(
                symbol,
                start_date=start_date,
                end_date=as_of_date.isoformat(),
                limit=50,
            )
        except DataServiceError:
            return []
        return response.items


def _to_group_score(group_result: FactorGroupResult) -> FactorGroupScore:
    positive_signals = [
        metric.positive_signal
        for metric in group_result.metrics
        if metric.normalized_score is not None
        and metric.normalized_score >= 60
        and metric.positive_signal is not None
    ]
    negative_signals = [
        metric.negative_signal
        for metric in group_result.metrics
        if metric.normalized_score is not None
        and metric.normalized_score <= 40
        and metric.negative_signal is not None
    ]

    return FactorGroupScore(
        group_name=group_result.group_name,
        score=clamp_optional_score(group_result.score),
        top_positive_signals=positive_signals[:3],
        top_negative_signals=negative_signals[:3],
    )


def _build_factor_dict(
    group_results: list[FactorGroupResult],
    *,
    field_name: str,
) -> dict[str, Optional[float]]:
    factor_dict: dict[str, Optional[float]] = {}
    for group_result in group_results:
        for metric in group_result.metrics:
            factor_dict[metric.factor_name] = getattr(metric, field_name)
    return factor_dict

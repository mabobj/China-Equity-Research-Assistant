"""个股研判 v2 编排服务。"""

from __future__ import annotations

from datetime import date, timedelta

from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.schemas.review import BullBearCase, StockReviewReport
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.factor_service.factor_snapshot_service import FactorSnapshotService
from app.services.factor_service.trigger_snapshot_service import TriggerSnapshotService
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService
from app.services.research_service.strategy_planner import StrategyPlanner
from app.services.review_service.bull_bear_builder import build_bull_bear_case
from app.services.review_service.chief_judgement_builder import build_chief_judgement
from app.services.review_service.event_view_builder import build_event_view
from app.services.review_service.factor_profile_builder import build_factor_profile_view
from app.services.review_service.fundamental_view_builder import build_fundamental_view
from app.services.review_service.sentiment_view_builder import build_sentiment_view
from app.services.review_service.technical_view_builder import build_technical_view


class StockReviewService:
    """组装个股研判 v2 的六块结构化输出。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        factor_snapshot_service: FactorSnapshotService,
        trigger_snapshot_service: TriggerSnapshotService,
        strategy_planner: StrategyPlanner,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._factor_snapshot_service = factor_snapshot_service
        self._trigger_snapshot_service = trigger_snapshot_service
        self._strategy_planner = strategy_planner

    def get_stock_review_report(self, symbol: str) -> StockReviewReport:
        """返回单票研判 v2 报告。"""
        profile = self._market_data_service.get_stock_profile(symbol)
        technical_snapshot = self._technical_analysis_service.get_technical_snapshot(symbol)
        factor_snapshot = self._factor_snapshot_service.get_factor_snapshot(symbol)
        trigger_snapshot = self._trigger_snapshot_service.get_trigger_snapshot(symbol)
        strategy_plan = self._strategy_planner.get_strategy_plan(symbol)

        financial_summary = self._safe_get_financial_summary(symbol)
        announcements = self._safe_get_announcements(
            symbol=symbol,
            as_of_date=technical_snapshot.as_of_date,
        )

        factor_profile = build_factor_profile_view(factor_snapshot)
        technical_view = build_technical_view(technical_snapshot, trigger_snapshot)
        fundamental_view = build_fundamental_view(financial_summary)
        event_view = build_event_view(announcements, factor_snapshot)
        sentiment_view = build_sentiment_view(
            factor_snapshot=factor_snapshot,
            technical_snapshot=technical_snapshot,
            trigger_snapshot=trigger_snapshot,
        )

        preliminary_chief = build_chief_judgement(
            factor_profile=factor_profile,
            technical_view=technical_view,
            event_view=event_view,
            sentiment_view=sentiment_view,
            bull_case=_placeholder_case("bull"),
            bear_case=_placeholder_case("bear"),
            key_disagreements=[],
            strategy_plan=strategy_plan,
        )
        bull_bear_result = build_bull_bear_case(
            factor_profile=factor_profile,
            technical_view=technical_view,
            fundamental_view=fundamental_view,
            event_view=event_view,
            sentiment_view=sentiment_view,
            strategy_summary=preliminary_chief.strategy_summary,
        )
        chief_result = build_chief_judgement(
            factor_profile=factor_profile,
            technical_view=technical_view,
            event_view=event_view,
            sentiment_view=sentiment_view,
            bull_case=bull_bear_result.bull_case,
            bear_case=bull_bear_result.bear_case,
            key_disagreements=bull_bear_result.key_disagreements,
            strategy_plan=strategy_plan,
        )

        return StockReviewReport(
            symbol=profile.symbol,
            name=profile.name,
            as_of_date=technical_snapshot.as_of_date,
            factor_profile=factor_profile,
            technical_view=technical_view,
            fundamental_view=fundamental_view,
            event_view=event_view,
            sentiment_view=sentiment_view,
            bull_case=bull_bear_result.bull_case,
            bear_case=bull_bear_result.bear_case,
            key_disagreements=bull_bear_result.key_disagreements,
            final_judgement=chief_result.final_judgement,
            strategy_summary=chief_result.strategy_summary,
            confidence=chief_result.confidence,
        )

    def _safe_get_financial_summary(self, symbol: str) -> FinancialSummary | None:
        try:
            return self._market_data_service.get_stock_financial_summary(symbol)
        except DataServiceError:
            return None

    def _safe_get_announcements(
        self,
        *,
        symbol: str,
        as_of_date: date,
    ) -> list[AnnouncementItem]:
        try:
            response = self._market_data_service.get_stock_announcements(
                symbol,
                start_date=(as_of_date - timedelta(days=30)).isoformat(),
                end_date=as_of_date.isoformat(),
                limit=30,
            )
        except DataServiceError:
            return []
        return response.items


def _placeholder_case(stance: str) -> BullBearCase:
    return BullBearCase(stance=stance, summary="", reasons=[])

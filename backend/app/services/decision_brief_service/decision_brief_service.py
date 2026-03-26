"""Decision brief service。"""

from __future__ import annotations

from app.schemas.decision_brief import DecisionBrief
from app.schemas.intraday import TriggerSnapshot
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.decision_brief_service.brief_builder import build_decision_brief
from app.services.factor_service.factor_snapshot_service import FactorSnapshotService
from app.services.factor_service.trigger_snapshot_service import TriggerSnapshotService
from app.services.llm_debate_service.fallback import DebateRuntimeService
from app.services.research_service.strategy_planner import StrategyPlanner
from app.services.review_service.stock_review_service import StockReviewService
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService


class DecisionBriefService:
    """统一的决策简报输出层。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        factor_snapshot_service: FactorSnapshotService,
        stock_review_service: StockReviewService,
        debate_runtime_service: DebateRuntimeService,
        strategy_planner: StrategyPlanner,
        trigger_snapshot_service: TriggerSnapshotService,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._factor_snapshot_service = factor_snapshot_service
        self._stock_review_service = stock_review_service
        self._debate_runtime_service = debate_runtime_service
        self._strategy_planner = strategy_planner
        self._trigger_snapshot_service = trigger_snapshot_service

    def get_decision_brief(
        self,
        symbol: str,
        *,
        use_llm: bool | None = None,
    ) -> DecisionBrief:
        """返回统一的单票决策简报。"""
        profile = self._market_data_service.get_stock_profile(symbol)
        factor_snapshot = self._factor_snapshot_service.get_factor_snapshot(symbol)
        review_report = self._stock_review_service.get_stock_review_report(symbol)
        debate_review = self._debate_runtime_service.get_debate_review_report(
            symbol,
            use_llm=use_llm,
        )
        strategy_plan = self._strategy_planner.get_strategy_plan(symbol)
        trigger_snapshot = self._get_trigger_snapshot_with_fallback(symbol)

        return build_decision_brief(
            profile=profile,
            factor_snapshot=factor_snapshot,
            review_report=review_report,
            debate_review=debate_review,
            strategy_plan=strategy_plan,
            trigger_snapshot=trigger_snapshot,
        )

    def _get_trigger_snapshot_with_fallback(self, symbol: str) -> TriggerSnapshot:
        try:
            return self._trigger_snapshot_service.get_trigger_snapshot(symbol)
        except DataServiceError:
            technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
                symbol
            )
            return self._trigger_snapshot_service.build_daily_fallback_trigger_snapshot(
                technical_snapshot
            )

"""角色化裁决骨架编排器。"""

from __future__ import annotations

from datetime import datetime, time
import logging

from app.schemas.debate import (
    AnalystViewsBuild,
    BullBearDebateBuild,
    ChiefJudgementBuild,
    DebateReviewReport,
    SingleStockResearchInputs,
    StrategyFinalize,
)
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import StrategySummary
from app.services.factor_service.factor_snapshot_service import FactorSnapshotService
from app.services.factor_service.trigger_snapshot_service import TriggerSnapshotService
from app.services.review_service.stock_review_service import StockReviewService
from app.services.research_service.strategy_planner import StrategyPlanner
from app.services.debate_service.analyst_views_builder import build_analyst_views_bundle
from app.services.debate_service.bear_researcher import build_bear_case
from app.services.debate_service.bull_researcher import build_bull_case
from app.services.debate_service.chief_analyst import build_chief_judgement
from app.services.debate_service.risk_reviewer import build_risk_review

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """按节点顺序构建角色化裁决骨架。"""

    def __init__(
        self,
        stock_review_service: StockReviewService,
        factor_snapshot_service: FactorSnapshotService,
        strategy_planner: StrategyPlanner,
        trigger_snapshot_service: TriggerSnapshotService,
    ) -> None:
        self._stock_review_service = stock_review_service
        self._factor_snapshot_service = factor_snapshot_service
        self._strategy_planner = strategy_planner
        self._trigger_snapshot_service = trigger_snapshot_service

    def build_inputs(self, symbol: str) -> SingleStockResearchInputs:
        """构建单票流程输入节点。"""
        logger.debug("debate.rule.build_inputs.start symbol=%s", symbol)
        review_report = self._stock_review_service.get_stock_review_report(symbol)
        factor_snapshot = self._factor_snapshot_service.get_factor_snapshot(symbol)
        strategy_plan = self._strategy_planner.get_strategy_plan(symbol)

        inputs = SingleStockResearchInputs(
            symbol=review_report.symbol,
            review_report=review_report,
            strategy_summary=StrategySummary(
                action=strategy_plan.action,
                strategy_type=strategy_plan.strategy_type,
                entry_window=strategy_plan.entry_window,
                ideal_entry_range=strategy_plan.ideal_entry_range,
                stop_loss_price=strategy_plan.stop_loss_price,
                take_profit_range=strategy_plan.take_profit_range,
                review_timeframe=strategy_plan.review_timeframe,
                concise_summary=review_report.strategy_summary.concise_summary,
            ),
            factor_alpha_score=factor_snapshot.alpha_score.total_score,
            factor_risk_score=factor_snapshot.risk_score.total_score,
            trigger_state=review_report.technical_view.trigger_state,
        )
        logger.debug(
            "debate.rule.build_inputs.done symbol=%s trigger_state=%s alpha_score=%s risk_score=%s strategy_action=%s",
            symbol,
            inputs.trigger_state,
            inputs.factor_alpha_score,
            inputs.factor_risk_score,
            strategy_plan.action,
        )
        return inputs

    def build_analyst_views(
        self,
        inputs: SingleStockResearchInputs,
    ) -> AnalystViewsBuild:
        """构建四类 analyst 节点。"""
        node = AnalystViewsBuild(
            symbol=inputs.symbol,
            analyst_views=build_analyst_views_bundle(
                inputs.review_report,
                self._build_trigger_snapshot_from_review(inputs),
            ),
        )
        logger.debug(
            "debate.rule.analyst_views.done symbol=%s technical_bias=%s fundamental_bias=%s event_bias=%s sentiment_bias=%s",
            inputs.symbol,
            node.analyst_views.technical.action_bias,
            node.analyst_views.fundamental.action_bias,
            node.analyst_views.event.action_bias,
            node.analyst_views.sentiment.action_bias,
        )
        return node

    def build_bull_bear_debate(
        self,
        analyst_views_node: AnalystViewsBuild,
    ) -> BullBearDebateBuild:
        """构建多空观点节点。"""
        bull_case = build_bull_case(analyst_views_node.analyst_views)
        bear_case = build_bear_case(analyst_views_node.analyst_views)
        key_disagreements = self._merge_key_disagreements(
            bull_case=bull_case,
            bear_case=bear_case,
        )
        return BullBearDebateBuild(
            symbol=analyst_views_node.symbol,
            bull_case=bull_case,
            bear_case=bear_case,
            key_disagreements=key_disagreements,
        )

    def build_chief_judgement(
        self,
        inputs: SingleStockResearchInputs,
        debate_node: BullBearDebateBuild,
    ) -> ChiefJudgementBuild:
        """构建首席裁决与风险复核节点。"""
        chief_judgement = build_chief_judgement(
            bull_case=debate_node.bull_case,
            bear_case=debate_node.bear_case,
            factor_profile=inputs.review_report.factor_profile,
            strategy_summary=inputs.review_report.strategy_summary,
        )
        risk_review = build_risk_review(
            factor_profile=inputs.review_report.factor_profile,
            technical_view=inputs.review_report.technical_view,
            strategy_summary=inputs.review_report.strategy_summary,
        )
        return ChiefJudgementBuild(
            symbol=inputs.symbol,
            chief_judgement=chief_judgement,
            risk_review=risk_review,
        )

    def finalize_strategy(
        self,
        inputs: SingleStockResearchInputs,
        chief_node: ChiefJudgementBuild,
    ) -> StrategyFinalize:
        """构建策略收束节点。"""
        confidence = max(
            0,
            min(
                100,
                round(
                    inputs.review_report.confidence * 0.7
                    + (100 - inputs.factor_risk_score) * 0.3
                ),
            ),
        )
        return StrategyFinalize(
            symbol=inputs.symbol,
            final_action=chief_node.chief_judgement.final_action,
            strategy_summary=inputs.strategy_summary,
            confidence=confidence,
        )

    def get_debate_review_report(self, symbol: str) -> DebateReviewReport:
        """返回角色化裁决骨架版报告。"""
        logger.debug("debate.rule.start symbol=%s", symbol)
        inputs = self.build_inputs(symbol)
        analyst_views_node = self.build_analyst_views(inputs)
        debate_node = self.build_bull_bear_debate(analyst_views_node)
        chief_node = self.build_chief_judgement(inputs, debate_node)
        finalize_node = self.finalize_strategy(inputs, chief_node)

        report = DebateReviewReport(
            symbol=inputs.review_report.symbol,
            name=inputs.review_report.name,
            as_of_date=inputs.review_report.as_of_date,
            analyst_views=analyst_views_node.analyst_views,
            bull_case=debate_node.bull_case,
            bear_case=debate_node.bear_case,
            key_disagreements=chief_node.chief_judgement.key_disagreements,
            chief_judgement=chief_node.chief_judgement,
            risk_review=chief_node.risk_review,
            final_action=finalize_node.final_action,
            strategy_summary=finalize_node.strategy_summary,
            confidence=finalize_node.confidence,
            runtime_mode="rule_based",
        )
        logger.debug(
            "debate.rule.done symbol=%s final_action=%s confidence=%s",
            symbol,
            report.final_action,
            report.confidence,
        )
        return report

    def _merge_key_disagreements(self, *, bull_case, bear_case) -> list[str]:
        disagreements: list[str] = []
        if bull_case.reasons and bear_case.reasons:
            disagreements.append(
                "多头与空头都能给出有效证据，核心分歧集中在执行赔率而不是是否值得跟踪。"
            )
        if len(bull_case.reasons) > len(bear_case.reasons):
            disagreements.append("多头证据数量更多，但仍需接受空头对纪律和位置的约束。")
        elif len(bear_case.reasons) > len(bull_case.reasons):
            disagreements.append("空头约束更集中，说明当前时点的反对理由更具体。")
        if not disagreements:
            disagreements.append("当前分歧不大，更多是执行节奏上的保守与激进差异。")
        return disagreements[:3]

    def _build_trigger_snapshot_from_review(
        self,
        inputs: SingleStockResearchInputs,
    ) -> TriggerSnapshot:
        logger.debug(
            "debate.rule.trigger_from_review symbol=%s trigger_state=%s",
            inputs.symbol,
            inputs.review_report.technical_view.trigger_state,
        )
        technical_view = inputs.review_report.technical_view
        latest_price = technical_view.latest_close or 0.0
        support_level = technical_view.support_level
        resistance_level = technical_view.resistance_level

        distance_to_support_pct = None
        if support_level is not None and support_level > 0 and latest_price > 0:
            distance_to_support_pct = float(
                (latest_price - support_level) / support_level * 100
            )

        distance_to_resistance_pct = None
        if resistance_level is not None and latest_price > 0:
            distance_to_resistance_pct = float(
                (resistance_level - latest_price) / latest_price * 100
            )

        return TriggerSnapshot(
            symbol=inputs.symbol,
            as_of_datetime=datetime.combine(
                inputs.review_report.as_of_date,
                time(15, 0, 0),
            ),
            daily_trend_state=technical_view.trend_state,
            daily_support_level=support_level,
            daily_resistance_level=resistance_level,
            latest_intraday_price=latest_price,
            distance_to_support_pct=distance_to_support_pct,
            distance_to_resistance_pct=distance_to_resistance_pct,
            trigger_state=technical_view.trigger_state,
            trigger_note=technical_view.tactical_read,
        )

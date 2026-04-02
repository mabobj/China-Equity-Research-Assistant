"""选股器深筛聚合 pipeline。"""

from typing import Optional

from app.schemas.research import ResearchReport
from app.schemas.screener import (
    DeepScreenerCandidate,
    DeepScreenerRunResponse,
    ScreenerCandidate,
    ScreenerRunResponse,
)
from app.schemas.strategy import StrategyPlan
from app.services.data_service.exceptions import DataServiceError
from app.services.research_service.research_manager import ResearchManager
from app.services.research_service.strategy_planner import StrategyPlanner
from app.services.screener_service.pipeline import ScreenerPipeline


class DeepScreenerPipeline:
    """基于初筛结果聚合研究与策略输出。"""

    def __init__(
        self,
        screener_pipeline: ScreenerPipeline,
        research_manager: ResearchManager,
        strategy_planner: StrategyPlanner,
    ) -> None:
        self._screener_pipeline = screener_pipeline
        self._research_manager = research_manager
        self._strategy_planner = strategy_planner

    def run_deep_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
        deep_top_k: Optional[int] = None,
    ) -> DeepScreenerRunResponse:
        """运行深筛聚合流程。"""
        base_result = self._screener_pipeline.run_screener(
            max_symbols=max_symbols,
            top_n=top_n,
        )
        selected_candidates = _select_candidates_for_deep_review(
            base_result=base_result,
            deep_top_k=deep_top_k,
        )

        deep_candidates: list[DeepScreenerCandidate] = []
        for candidate in selected_candidates:
            deep_candidate = self._build_deep_candidate(candidate)
            if deep_candidate is None:
                continue
            deep_candidates.append(deep_candidate)

        ranked_candidates = _rank_deep_candidates(deep_candidates)
        return DeepScreenerRunResponse(
            as_of_date=base_result.as_of_date,
            total_symbols=base_result.total_symbols,
            scanned_symbols=base_result.scanned_symbols,
            selected_for_deep_review=len(selected_candidates),
            deep_candidates=ranked_candidates,
        )

    def _build_deep_candidate(
        self,
        candidate: ScreenerCandidate,
    ) -> Optional[DeepScreenerCandidate]:
        """聚合单个候选的研究与策略结果。"""
        try:
            research_report = self._research_manager.get_research_report(candidate.symbol)
            strategy_plan = self._strategy_planner.get_strategy_plan(candidate.symbol)
        except DataServiceError:
            return None
        except Exception:
            return None

        priority_score = _calculate_priority_score(
            base_screener_score=candidate.screener_score,
            research_overall_score=research_report.overall_score,
            research_confidence=research_report.confidence,
            strategy_action=strategy_plan.action,
            strategy_type=strategy_plan.strategy_type,
        )
        short_reason = _build_short_reason(
            base_candidate=candidate,
            research_report=research_report,
            strategy_plan=strategy_plan,
        )

        return DeepScreenerCandidate(
            symbol=candidate.symbol,
            name=candidate.name,
            base_list_type=candidate.list_type,
            base_rank=candidate.rank,
            base_screener_score=candidate.screener_score,
            research_action=research_report.action,
            research_overall_score=research_report.overall_score,
            research_confidence=research_report.confidence,
            strategy_action=strategy_plan.action,
            strategy_type=strategy_plan.strategy_type,
            ideal_entry_range=strategy_plan.ideal_entry_range,
            stop_loss_price=strategy_plan.stop_loss_price,
            take_profit_range=strategy_plan.take_profit_range,
            review_timeframe=strategy_plan.review_timeframe,
            thesis=research_report.thesis,
            short_reason=short_reason,
            priority_score=priority_score,
            predictive_score=candidate.predictive_score,
            predictive_confidence=candidate.predictive_confidence,
            predictive_model_version=candidate.predictive_model_version,
        )


def _select_candidates_for_deep_review(
    base_result: ScreenerRunResponse,
    deep_top_k: Optional[int],
) -> list[ScreenerCandidate]:
    """从初筛结果中挑选深筛候选。"""
    candidates = list(base_result.buy_candidates) + list(base_result.watch_candidates)
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            _base_list_priority(item.list_type),
            -item.screener_score,
            item.rank,
            item.symbol,
        ),
    )

    if deep_top_k is not None:
        sorted_candidates = sorted_candidates[: max(deep_top_k, 0)]
    return sorted_candidates


def _rank_deep_candidates(
    candidates: list[DeepScreenerCandidate],
) -> list[DeepScreenerCandidate]:
    """按深筛优先级重新排序。"""
    return sorted(
        candidates,
        key=lambda item: (-item.priority_score, item.base_rank, item.symbol),
    )


def _calculate_priority_score(
    base_screener_score: int,
    research_overall_score: int,
    research_confidence: int,
    strategy_action: str,
    strategy_type: str,
) -> int:
    """计算第一版深筛优先级分数。"""
    score = (
        base_screener_score * 0.35
        + research_overall_score * 0.45
        + research_confidence * 0.20
    )
    score += _strategy_action_bonus(strategy_action)
    score += _strategy_type_bonus(strategy_type)
    return _clamp_score(score)


def _build_short_reason(
    base_candidate: ScreenerCandidate,
    research_report: ResearchReport,
    strategy_plan: StrategyPlan,
) -> str:
    """生成深筛候选的简短说明。"""
    if (
        research_report.action == "BUY"
        and strategy_plan.action == "BUY"
        and strategy_plan.strategy_type in {"pullback", "breakout"}
    ):
        return "初筛强度较高，研究与策略同时支持继续跟踪买点。"
    if research_report.action == "WATCH" or strategy_plan.strategy_type == "wait":
        return "初筛通过，但更适合继续观察确认信号。"
    if base_candidate.list_type == "BUY_CANDIDATE":
        return "初筛靠前，但研究或策略提示先控制节奏。"
    return "进入深筛观察池，等待研究与策略信号进一步收敛。"


def _base_list_priority(list_type: str) -> int:
    """定义深筛前的基础列表优先级。"""
    priority_map = {
        "BUY_CANDIDATE": 0,
        "WATCHLIST": 1,
        "AVOID": 2,
    }
    return priority_map.get(list_type, 9)


def _strategy_action_bonus(action: str) -> int:
    """根据策略动作给出小幅加减分。"""
    bonus_map = {
        "BUY": 6,
        "WATCH": 0,
        "AVOID": -10,
    }
    return bonus_map.get(action, 0)


def _strategy_type_bonus(strategy_type: str) -> int:
    """根据策略类型给出小幅加减分。"""
    bonus_map = {
        "pullback": 3,
        "breakout": 5,
        "wait": 0,
        "no_trade": -8,
    }
    return bonus_map.get(strategy_type, 0)


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))

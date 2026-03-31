"""研究流程编排与报告聚合。"""

from dataclasses import dataclass
from typing import Optional

from app.schemas.market_data import DailyBarResponse, StockProfile
from app.schemas.research import (
    EventResearchResult,
    FundamentalResearchResult,
    ResearchDataQualitySummary,
    ResearchReport,
    TechnicalResearchResult,
)
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.exceptions import DataServiceError, ProviderError
from app.services.data_service.market_data_service import MarketDataService
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService
from app.services.research_service.event_researcher import EventResearcher
from app.services.research_service.fundamental_researcher import FundamentalResearcher
from app.services.research_service.technical_researcher import TechnicalResearcher


@dataclass(frozen=True)
class ResearchInputs:
    """研究报告所需的结构化输入。"""

    profile: StockProfile
    technical_snapshot: TechnicalSnapshot
    daily_bars_response: DailyBarResponse
    financial_summary: FinancialSummary
    announcements: list[AnnouncementItem]
    announcements_quality_status: Optional[str]
    announcements_cleaning_warnings: list[str]


@dataclass(frozen=True)
class _QualityConsumptionResult:
    """研究链路质量消费结果。"""

    summary: ResearchDataQualitySummary
    confidence_reasons: list[str]
    risk_hints: list[str]


_QUALITY_ORDER = ("ok", "warning", "degraded", "failed")
_TECHNICAL_QUALITY_MODIFIER = {
    "ok": 1.00,
    "warning": 0.90,
    "degraded": 0.70,
    "failed": 0.30,
}
_FUNDAMENTAL_QUALITY_MODIFIER = {
    "ok": 1.00,
    "warning": 0.85,
    "degraded": 0.60,
    "failed": 0.20,
}
_EVENT_QUALITY_MODIFIER = {
    "ok": 1.00,
    "warning": 0.85,
    "degraded": 0.60,
    "failed": 0.20,
}


class ResearchManager:
    """负责协调输入数据与各 researcher，输出统一研究报告。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        technical_researcher: Optional[TechnicalResearcher] = None,
        fundamental_researcher: Optional[FundamentalResearcher] = None,
        event_researcher: Optional[EventResearcher] = None,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._technical_researcher = technical_researcher or TechnicalResearcher()
        self._fundamental_researcher = fundamental_researcher or FundamentalResearcher()
        self._event_researcher = event_researcher or EventResearcher()

    def get_research_report(self, symbol: str) -> ResearchReport:
        """生成结构化单票研究报告。"""
        return self.build_research_report(self.collect_research_inputs(symbol))

    def collect_research_inputs(self, symbol: str) -> ResearchInputs:
        """集中拉取研究报告所需输入，便于其他服务复用。"""
        try:
            profile = self._market_data_service.get_stock_profile(symbol)
            daily_bars_response = self._market_data_service.get_daily_bars(
                symbol=symbol,
            )
            technical_snapshot = self._technical_analysis_service.build_snapshot_from_bars(
                symbol=symbol,
                bars=daily_bars_response.bars,
            )
            financial_summary = self._market_data_service.get_stock_financial_summary(
                symbol,
            )
            announcements_response = self._market_data_service.get_stock_announcements(
                symbol=symbol,
                limit=10,
            )
        except DataServiceError:
            raise
        except Exception as exc:
            raise ProviderError("Failed to collect research inputs.") from exc

        return ResearchInputs(
            profile=profile,
            technical_snapshot=technical_snapshot,
            daily_bars_response=daily_bars_response,
            financial_summary=financial_summary,
            announcements=announcements_response.items,
            announcements_quality_status=announcements_response.quality_status,
            announcements_cleaning_warnings=list(announcements_response.cleaning_warnings),
        )

    def build_research_report(self, inputs: ResearchInputs) -> ResearchReport:
        """基于已拉取输入构建研究报告。"""
        technical_result = self._technical_researcher.analyze(
            inputs.technical_snapshot,
        )
        fundamental_result = self._fundamental_researcher.analyze(
            inputs.financial_summary,
        )
        event_result = self._event_researcher.analyze(
            announcements=inputs.announcements,
            as_of_date=inputs.technical_snapshot.as_of_date,
        )

        risk_score = _calculate_risk_score(
            technical_snapshot=inputs.technical_snapshot,
            financial_summary=inputs.financial_summary,
            announcements=inputs.announcements,
            technical_result=technical_result,
            fundamental_result=fundamental_result,
            event_result=event_result,
        )
        overall_score = _calculate_overall_score(
            technical_score=technical_result.score,
            fundamental_score=fundamental_result.score,
            event_score=event_result.score,
        )
        action = _determine_action(overall_score=overall_score, risk_score=risk_score)
        confidence = _calculate_confidence(
            overall_score=overall_score,
            technical_result=technical_result,
            fundamental_result=fundamental_result,
            event_result=event_result,
        )
        quality_consumption = _consume_data_quality(
            daily_bars_response=inputs.daily_bars_response,
            financial_summary=inputs.financial_summary,
            announcements_quality_status=inputs.announcements_quality_status,
            announcements_cleaning_warnings=inputs.announcements_cleaning_warnings,
        )
        confidence = _clamp_score(
            confidence * quality_consumption.summary.overall_quality_modifier,
        )
        thesis = _build_thesis(
            name=inputs.profile.name,
            technical_result=technical_result,
            fundamental_result=fundamental_result,
            event_result=event_result,
            action=action,
        )

        return ResearchReport(
            symbol=inputs.technical_snapshot.symbol,
            name=inputs.profile.name,
            as_of_date=inputs.technical_snapshot.as_of_date,
            technical_score=technical_result.score,
            fundamental_score=fundamental_result.score,
            event_score=event_result.score,
            risk_score=risk_score,
            overall_score=overall_score,
            action=action,
            confidence=confidence,
            thesis=thesis,
            key_reasons=_merge_lists(
                technical_result.key_reasons,
                fundamental_result.key_reasons,
                event_result.key_reasons,
            ),
            risks=_merge_lists(
                quality_consumption.risk_hints,
                technical_result.risks,
                fundamental_result.risks,
                event_result.risks,
            ),
            triggers=_merge_lists(
                technical_result.triggers,
                fundamental_result.triggers,
                event_result.triggers,
            ),
            invalidations=_merge_lists(
                technical_result.invalidations,
                fundamental_result.invalidations,
                event_result.invalidations,
            ),
            data_quality_summary=quality_consumption.summary,
            confidence_reasons=quality_consumption.confidence_reasons,
        )


def _calculate_overall_score(
    technical_score: int,
    fundamental_score: int,
    event_score: int,
) -> int:
    """按清晰权重聚合总体评分。"""
    weighted_score = (
        technical_score * 0.45
        + fundamental_score * 0.35
        + event_score * 0.20
    )
    return _clamp_score(weighted_score)


def _calculate_risk_score(
    technical_snapshot: TechnicalSnapshot,
    financial_summary: FinancialSummary,
    announcements: list[AnnouncementItem],
    technical_result: TechnicalResearchResult,
    fundamental_result: FundamentalResearchResult,
    event_result: EventResearchResult,
) -> int:
    """根据技术、财务和事件信号生成第一版风险评分。"""
    risk_score = 30.0

    if technical_snapshot.trend_state == "down":
        risk_score += 18
    elif technical_snapshot.trend_state == "neutral":
        risk_score += 6

    if technical_snapshot.volatility_state == "high":
        risk_score += 15
    elif technical_snapshot.volatility_state == "low":
        risk_score -= 4

    if (
        technical_snapshot.support_level is not None
        and technical_snapshot.latest_close < technical_snapshot.support_level
    ):
        risk_score += 15

    if financial_summary.net_profit is not None and financial_summary.net_profit <= 0:
        risk_score += 18
    if financial_summary.net_profit_yoy is not None and financial_summary.net_profit_yoy < 0:
        risk_score += 10
    if financial_summary.debt_ratio is not None and financial_summary.debt_ratio >= 70:
        risk_score += 12
    if financial_summary.roe is not None and financial_summary.roe < 5:
        risk_score += 8

    negative_event_titles = 0
    for item in announcements[:10]:
        if any(
            keyword in item.title
            for keyword in ("减持", "问询", "监管", "诉讼", "仲裁", "立案", "风险")
        ):
            negative_event_titles += 1
    risk_score += negative_event_titles * 6

    if technical_result.score < 40:
        risk_score += 10
    if fundamental_result.score < 40:
        risk_score += 12
    if event_result.score < 40:
        risk_score += 8

    return _clamp_score(risk_score)


def _determine_action(overall_score: int, risk_score: int) -> str:
    """根据总分和风险分生成第一版动作建议。"""
    if overall_score >= 70 and risk_score <= 45:
        return "BUY"
    if overall_score >= 45 and risk_score <= 70:
        return "WATCH"
    return "AVOID"


def _calculate_confidence(
    overall_score: int,
    technical_result: TechnicalResearchResult,
    fundamental_result: FundamentalResearchResult,
    event_result: EventResearchResult,
) -> int:
    """根据分数一致性生成置信度。"""
    scores = [
        technical_result.score,
        fundamental_result.score,
        event_result.score,
    ]
    spread = max(scores) - min(scores)
    confidence = 55 + (overall_score - 50) * 0.4 - spread * 0.25
    return _clamp_score(confidence)


def _consume_data_quality(
    *,
    daily_bars_response: DailyBarResponse,
    financial_summary: FinancialSummary,
    announcements_quality_status: Optional[str],
    announcements_cleaning_warnings: list[str],
) -> _QualityConsumptionResult:
    """消费清洗质量状态，生成置信度修正与解释信息。"""
    bars_quality = _normalize_quality_status(daily_bars_response.quality_status)
    financial_quality = _normalize_quality_status(financial_summary.quality_status)
    announcement_quality = _normalize_quality_status(announcements_quality_status)

    technical_modifier = _TECHNICAL_QUALITY_MODIFIER[bars_quality]
    fundamental_modifier = _FUNDAMENTAL_QUALITY_MODIFIER[financial_quality]
    event_modifier = _EVENT_QUALITY_MODIFIER[announcement_quality]
    overall_quality_modifier = (
        0.4 * technical_modifier
        + 0.35 * fundamental_modifier
        + 0.25 * event_modifier
    )

    confidence_reasons: list[str] = []
    risk_hints: list[str] = []

    if bars_quality == "ok":
        confidence_reasons.append("行情数据质量正常，技术结论可正常参考。")
    else:
        confidence_reasons.append(
            "行情数据质量为 {quality}，技术结论置信度已下调。".format(
                quality=bars_quality,
            )
        )
        risk_hints.append("技术结论受行情数据质量影响，需谨慎解读。")
        if daily_bars_response.cleaning_warnings:
            risk_hints.append(
                "行情数据告警：{warnings}".format(
                    warnings="；".join(daily_bars_response.cleaning_warnings[:2]),
                )
            )

    if financial_quality == "ok":
        confidence_reasons.append("财务摘要质量正常，基本面结论可正常参考。")
    else:
        confidence_reasons.append(
            "财务摘要质量为 {quality}，基本面结论置信度已下调。".format(
                quality=financial_quality,
            )
        )
        missing_fields = list(financial_summary.missing_fields)
        if missing_fields:
            risk_hints.append(
                "财务摘要缺失核心字段：{fields}。".format(
                    fields=" / ".join(missing_fields[:5]),
                )
            )
        risk_hints.append("财务输入质量不足，当前基本面判断应以谨慎口径解读。")

    if announcement_quality == "ok":
        confidence_reasons.append("公告索引质量正常，事件结论可正常参考。")
    else:
        confidence_reasons.append(
            "公告索引质量为 {quality}，事件结论置信度已下调。".format(
                quality=announcement_quality,
            )
        )
        risk_hints.append("公告输入存在不确定性，事件结论可能存在遗漏。")
        if announcements_cleaning_warnings:
            risk_hints.append(
                "公告数据告警：{warnings}".format(
                    warnings="；".join(announcements_cleaning_warnings[:2]),
                )
            )

    return _QualityConsumptionResult(
        summary=ResearchDataQualitySummary(
            bars_quality=bars_quality,  # type: ignore[arg-type]
            financial_quality=financial_quality,  # type: ignore[arg-type]
            announcement_quality=announcement_quality,  # type: ignore[arg-type]
            technical_modifier=round(technical_modifier, 2),
            fundamental_modifier=round(fundamental_modifier, 2),
            event_modifier=round(event_modifier, 2),
            overall_quality_modifier=round(overall_quality_modifier, 4),
        ),
        confidence_reasons=confidence_reasons,
        risk_hints=_limit_items(
            items=risk_hints,
            fallback="",
            limit=3,
        ),
    )


def _build_thesis(
    name: str,
    technical_result: TechnicalResearchResult,
    fundamental_result: FundamentalResearchResult,
    event_result: EventResearchResult,
    action: str,
) -> str:
    """生成简洁 thesis。"""
    return (
        "{name} 当前综合判断为 {action}，技术面 {technical}，基本面 {fundamental}。"
        "事件面 {event}"
    ).format(
        name=name,
        action=action,
        technical=technical_result.summary,
        fundamental=fundamental_result.summary,
        event=event_result.summary,
    )


def _merge_lists(*groups: list[str]) -> list[str]:
    """合并多个列表并限制返回 3 条。"""
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return merged[:3]


def _normalize_quality_status(status: Optional[str]) -> str:
    """归一化质量状态，未知值按 warning 处理。"""
    if status in _QUALITY_ORDER:
        return status
    return "warning"


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))


def _limit_items(items: list[str], fallback: str, limit: int = 3) -> list[str]:
    """去重并限制数量。"""
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        if normalized not in deduped:
            deduped.append(normalized)
    if not deduped and fallback:
        deduped.append(fallback)
    return deduped[:limit]

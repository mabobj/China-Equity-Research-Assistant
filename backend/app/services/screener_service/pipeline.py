"""选股器 pipeline。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
from time import perf_counter
from typing import TYPE_CHECKING, Literal, Optional

from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem
from app.schemas.research_inputs import FinancialSummary
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.factor_service.base import FactorBuildInputs
from app.services.screener_service.filters import (
    has_abnormal_price_data,
    has_acceptable_liquidity,
    has_sufficient_daily_bars,
)
from app.services.screener_service.scoring import (
    score_factor_snapshot,
    score_technical_snapshot,
)
from app.services.screener_service.texts import normalize_candidate_display_fields
from app.services.screener_service.universe import load_scan_universe

if TYPE_CHECKING:
    from app.services.factor_service.snapshot import FactorSnapshotService
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )

logger = logging.getLogger(__name__)
_RULE_VERSION = "screener_workflow_v1"
_RULE_SUMMARY = "基于趋势评分、因子快照与风险约束的规则初筛。"
_QUALITY_STATUS = Literal["ok", "warning", "degraded", "failed"]
_QUALITY_WEIGHT = {
    "ok": 1.00,
    "warning": 0.95,
    "degraded": 0.85,
    "failed": 0.70,
}


class ScreenerPipeline:
    """执行全市场规则初筛。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        factor_snapshot_service: Optional[FactorSnapshotService] = None,
        lookback_days: int = 400,
        progress_log_interval: int = 100,
        batch_daily_bar_provider_priority: tuple[str, ...] = (
            "mootdx",
            "baostock",
            "akshare",
        ),
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._factor_snapshot_service = factor_snapshot_service
        self._lookback_days = max(lookback_days, 180)
        self._progress_log_interval = max(progress_log_interval, 1)
        self._batch_daily_bar_provider_priority = batch_daily_bar_provider_priority

    def run_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
        force_refresh: bool = False,
        scan_items: Optional[list[UniverseItem]] = None,
        total_symbols_override: Optional[int] = None,
    ) -> ScreenerRunResponse:
        started_at = perf_counter()

        with self._market_data_service.session_scope():
            if scan_items is None:
                total_symbols, scan_items = load_scan_universe(
                    market_data_service=self._market_data_service,
                    max_symbols=max_symbols,
                )
            else:
                total_symbols = (
                    total_symbols_override
                    if total_symbols_override is not None
                    else len(scan_items)
                )
            scanned_symbols = len(scan_items)
            candidates: list[ScreenerCandidate] = []
            failed_placeholders: list[ScreenerCandidate] = []
            latest_as_of_date: Optional[date] = None
            skipped_symbols = 0
            lookback_start_date = (
                date.today() - timedelta(days=self._lookback_days)
            ).isoformat()

            logger.info(
                "初筛开始：股票池总数=%s，实际扫描=%s，top_n=%s，lookback_start_date=%s",
                total_symbols,
                scanned_symbols,
                top_n,
                lookback_start_date,
            )

            for index, item in enumerate(scan_items, start=1):
                scan_result = self._scan_one_symbol(
                    item=item,
                    start_date=lookback_start_date,
                    force_refresh=force_refresh,
                )
                if scan_result is None:
                    skipped_symbols += 1
                    self._log_progress(
                        index=index,
                        total=scanned_symbols,
                        item=item,
                        candidates=candidates,
                        skipped_symbols=skipped_symbols,
                        started_at=started_at,
                    )
                    continue
                if scan_result.failed_placeholder is not None:
                    failed_placeholders.append(scan_result.failed_placeholder)
                if scan_result.candidate is not None:
                    candidates.append(scan_result.candidate)

                if latest_as_of_date is None or scan_result.as_of_date > latest_as_of_date:
                    latest_as_of_date = scan_result.as_of_date
                self._log_progress(
                    index=index,
                    total=scanned_symbols,
                    item=item,
                    candidates=candidates,
                    skipped_symbols=skipped_symbols,
                    started_at=started_at,
                )

        ready_to_buy_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "READY_TO_BUY"],
            top_n=top_n,
        )
        watch_pullback_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "WATCH_PULLBACK"],
            top_n=top_n,
        )
        watch_breakout_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "WATCH_BREAKOUT"],
            top_n=top_n,
        )
        research_only_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "RESEARCH_ONLY"],
            top_n=top_n,
        )
        buy_candidates = list(ready_to_buy_candidates)
        watch_candidates = _rank_candidates(
            [
                item
                for item in candidates
                if item.v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}
            ],
            top_n=top_n,
        )
        avoid_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "AVOID"],
            top_n=top_n,
        )
        avoid_candidates = _append_failed_placeholders(
            ranked_avoid_candidates=avoid_candidates,
            failed_placeholders=failed_placeholders,
        )

        logger.info(
            "初筛完成：实际扫描=%s，产出=%s，跳过=%s，READY=%s，WATCH=%s，AVOID=%s，耗时=%.1fs",
            scanned_symbols,
            len(candidates),
            skipped_symbols,
            len(ready_to_buy_candidates),
            len(watch_candidates),
            len(avoid_candidates),
            perf_counter() - started_at,
        )

        return ScreenerRunResponse(
            as_of_date=latest_as_of_date or date.today(),
            freshness_mode="force_refreshed" if force_refresh else "cache_preferred",
            source_mode="pipeline",
            total_symbols=total_symbols,
            scanned_symbols=scanned_symbols,
            buy_candidates=buy_candidates,
            watch_candidates=watch_candidates,
            avoid_candidates=avoid_candidates,
            ready_to_buy_candidates=ready_to_buy_candidates,
            watch_pullback_candidates=watch_pullback_candidates,
            watch_breakout_candidates=watch_breakout_candidates,
            research_only_candidates=research_only_candidates,
        )

    def _scan_one_symbol(
        self,
        item: UniverseItem,
        start_date: str,
        force_refresh: bool,
    ) -> Optional["_ScanResult"]:
        try:
            daily_bars_response = self._load_daily_bars_for_scan(
                symbol=item.symbol,
                start_date=start_date,
                force_refresh=force_refresh,
            )
        except DataServiceError:
            return None

        bars_quality = _normalize_quality_status(daily_bars_response.quality_status)
        if bars_quality == "failed":
            return _ScanResult(
                as_of_date=_resolve_as_of_date(daily_bars_response),
                candidate=None,
                failed_placeholder=_build_failed_placeholder_for_bars(
                    item=item,
                    response=daily_bars_response,
                    quality_note="行情数据质量失败，未纳入候选排序。",
                ),
            )

        daily_bars = daily_bars_response.bars
        if not has_sufficient_daily_bars(daily_bars_response):
            return None
        if not has_acceptable_liquidity(daily_bars_response):
            return None
        if has_abnormal_price_data(daily_bars_response):
            return None

        try:
            build_snapshot = getattr(
                self._technical_analysis_service,
                "build_snapshot_from_bars",
                None,
            )
            if callable(build_snapshot):
                technical_snapshot = build_snapshot(
                    symbol=item.symbol,
                    bars=daily_bars,
                )
            else:
                technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
                    item.symbol,
                )
        except DataServiceError:
            return None

        financial_summary, financial_quality = _safe_get_financial_summary(
            self._market_data_service,
            item.symbol,
        )
        recent_announcements, announcement_quality = _safe_get_recent_announcements(
            self._market_data_service,
            item.symbol,
            technical_snapshot.as_of_date,
        )
        if self._factor_snapshot_service is not None:
            factor_snapshot = self._factor_snapshot_service.build_from_inputs(
                FactorBuildInputs(
                    symbol=item.symbol,
                    technical_snapshot=technical_snapshot,
                    daily_bars=daily_bars,
                    financial_summary=financial_summary,
                    announcements=recent_announcements,
                )
            )
            score_result = score_factor_snapshot(
                factor_snapshot=factor_snapshot,
                technical_snapshot=technical_snapshot,
            )
        else:
            score_result = score_technical_snapshot(technical_snapshot)

        quality_gate = _apply_quality_gate(
            origin_v2_list_type=score_result.v2_list_type,
            origin_screener_score=score_result.screener_score,
            bars_quality=bars_quality,
            financial_quality=financial_quality,
            announcement_quality=announcement_quality,
        )

        return _ScanResult(
            as_of_date=technical_snapshot.as_of_date,
            candidate=_build_candidate(
                item=item,
                technical_snapshot=technical_snapshot,
                score_result=score_result,
                target_v2_list_type=quality_gate.target_v2_list_type,
                target_screener_score=quality_gate.target_screener_score,
                bars_quality=bars_quality,
                financial_quality=financial_quality,
                announcement_quality=announcement_quality,
                quality_penalty_applied=quality_gate.quality_penalty_applied,
                quality_note=quality_gate.quality_note,
            ),
            failed_placeholder=None,
        )

    def _load_daily_bars_for_scan(
        self,
        *,
        symbol: str,
        start_date: str,
        force_refresh: bool,
    ) -> DailyBarResponse:
        try:
            return self._market_data_service.get_daily_bars(
                symbol,
                start_date=start_date,
                force_refresh=force_refresh,
                provider_names=self._batch_daily_bar_provider_priority,
            )
        except TypeError:
            return self._market_data_service.get_daily_bars(
                symbol,
                start_date=start_date,
            )

    def _log_progress(
        self,
        index: int,
        total: int,
        item: UniverseItem,
        candidates: list[ScreenerCandidate],
        skipped_symbols: int,
        started_at: float,
    ) -> None:
        if total <= 0:
            return
        if index != total and index % self._progress_log_interval != 0:
            return

        logger.info(
            "初筛进度：%s/%s，当前=%s，已产出=%s，已跳过=%s，耗时=%.1fs",
            index,
            total,
            item.symbol,
            len(candidates),
            skipped_symbols,
            perf_counter() - started_at,
        )


@dataclass(frozen=True)
class _ScanResult:
    """内部扫描结果。"""

    as_of_date: date
    candidate: Optional[ScreenerCandidate]
    failed_placeholder: Optional[ScreenerCandidate]


@dataclass(frozen=True)
class _QualityGateResult:
    """质量门控结果。"""

    target_v2_list_type: str
    target_screener_score: int
    quality_penalty_applied: bool
    quality_note: Optional[str]


def _rank_candidates(
    candidates: list[ScreenerCandidate],
    top_n: Optional[int] = None,
) -> list[ScreenerCandidate]:
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            item.screener_score,
            item.alpha_score,
            -item.risk_score,
            item.trend_score,
            item.symbol,
        ),
        reverse=True,
    )
    if top_n is not None:
        sorted_candidates = sorted_candidates[: max(top_n, 0)]

    ranked_candidates: list[ScreenerCandidate] = []
    for index, candidate in enumerate(sorted_candidates, start=1):
        ranked_candidates.append(candidate.model_copy(update={"rank": index}))
    return ranked_candidates


def _build_candidate(
    *,
    item: UniverseItem,
    technical_snapshot,
    score_result,
    target_v2_list_type: str,
    target_screener_score: int,
    bars_quality: _QUALITY_STATUS,
    financial_quality: _QUALITY_STATUS,
    announcement_quality: _QUALITY_STATUS,
    quality_penalty_applied: bool,
    quality_note: Optional[str],
) -> ScreenerCandidate:
    v2_list_type = target_v2_list_type
    display_fields = normalize_candidate_display_fields(
        name=item.name,
        list_type=v2_list_type,
        short_reason=score_result.short_reason,
        headline_verdict=None,
        top_positive_factors=score_result.top_positive_factors,
        top_negative_factors=score_result.top_negative_factors,
        risk_notes=score_result.risk_notes,
        evidence_hints=[
            *score_result.top_positive_factors[:2],
            *score_result.risk_notes[:1],
        ],
    )
    evidence_hints = [
        *score_result.top_positive_factors[:2],
        *score_result.risk_notes[:1],
    ]
    return ScreenerCandidate(
        symbol=item.symbol,
        name=str(display_fields["name"]),
        list_type=_to_legacy_list_type(v2_list_type),
        v2_list_type=v2_list_type,
        rank=1,
        screener_score=target_screener_score,
        alpha_score=score_result.alpha_score,
        trigger_score=score_result.trigger_score,
        risk_score=score_result.risk_score,
        trend_state=technical_snapshot.trend_state,
        trend_score=technical_snapshot.trend_score,
        latest_close=technical_snapshot.latest_close,
        support_level=technical_snapshot.support_level,
        resistance_level=technical_snapshot.resistance_level,
        top_positive_factors=list(display_fields["top_positive_factors"]),
        top_negative_factors=list(display_fields["top_negative_factors"]),
        risk_notes=list(display_fields["risk_notes"]),
        short_reason=str(display_fields["short_reason"]),
        calculated_at=datetime.now(timezone.utc),
        rule_version=_RULE_VERSION,
        rule_summary=_RULE_SUMMARY,
        headline_verdict=str(display_fields["headline_verdict"]),
        action_now=_build_action_now(v2_list_type),
        evidence_hints=list(display_fields["evidence_hints"])[:3] or evidence_hints[:3],
        bars_quality=bars_quality,
        financial_quality=financial_quality,
        announcement_quality=announcement_quality,
        quality_penalty_applied=quality_penalty_applied,
        quality_note=quality_note,
        fail_reason=None,
    )


def _build_action_now(v2_list_type: str) -> str:
    mapping = {
        "READY_TO_BUY": "BUY_NOW",
        "WATCH_PULLBACK": "WAIT_PULLBACK",
        "WATCH_BREAKOUT": "WAIT_BREAKOUT",
        "RESEARCH_ONLY": "RESEARCH_ONLY",
        "AVOID": "AVOID",
    }
    return mapping.get(v2_list_type, "RESEARCH_ONLY")


def _to_legacy_list_type(v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "BUY_CANDIDATE"
    if v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}:
        return "WATCHLIST"
    return "AVOID"


def _normalize_quality_status(raw_status: Optional[str]) -> _QUALITY_STATUS:
    if raw_status in _QUALITY_WEIGHT:
        return raw_status  # type: ignore[return-value]
    return "warning"


def _resolve_as_of_date(response: DailyBarResponse) -> date:
    if response.bars:
        return response.bars[-1].trade_date
    return date.today()


def _build_failed_placeholder_for_bars(
    *,
    item: UniverseItem,
    response: DailyBarResponse,
    quality_note: str,
) -> ScreenerCandidate:
    latest_close = response.bars[-1].close if response.bars else None
    fail_reason = "行情数据清洗质量为 failed，当前股票仅保留失败占位。"
    if response.cleaning_warnings:
        fail_reason = "{reason} 告警：{warnings}".format(
            reason=fail_reason,
            warnings="；".join(response.cleaning_warnings[:2]),
        )
    display_fields = normalize_candidate_display_fields(
        name=item.name,
        list_type="AVOID",
        short_reason="行情数据质量失败，未纳入候选排序。",
        headline_verdict="行情数据质量失败，本轮仅保留失败占位。",
        evidence_hints=response.cleaning_warnings[:2],
    )
    return ScreenerCandidate(
        symbol=item.symbol,
        name=str(display_fields["name"]),
        list_type="AVOID",
        v2_list_type="AVOID",
        rank=1,
        screener_score=0,
        alpha_score=0,
        trigger_score=0,
        risk_score=100,
        trend_state="down",
        trend_score=0,
        latest_close=latest_close if latest_close is not None else 0.0,
        support_level=None,
        resistance_level=None,
        top_positive_factors=[],
        top_negative_factors=["行情数据质量 failed"],
        risk_notes=["该股票未参与本轮候选排序"],
        short_reason=str(display_fields["short_reason"]),
        calculated_at=datetime.now(timezone.utc),
        rule_version=_RULE_VERSION,
        rule_summary=_RULE_SUMMARY,
        headline_verdict=str(display_fields["headline_verdict"]),
        action_now="AVOID",
        evidence_hints=list(display_fields["evidence_hints"]),
        bars_quality="failed",
        financial_quality=None,
        announcement_quality=None,
        quality_penalty_applied=True,
        quality_note=quality_note,
        fail_reason=fail_reason,
    )


def _apply_quality_gate(
    *,
    origin_v2_list_type: str,
    origin_screener_score: int,
    bars_quality: _QUALITY_STATUS,
    financial_quality: _QUALITY_STATUS,
    announcement_quality: _QUALITY_STATUS,
) -> _QualityGateResult:
    target_v2_list_type = origin_v2_list_type
    quality_notes: list[str] = []
    quality_penalty_applied = False

    if bars_quality == "degraded" and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("行情数据质量降级，候选已下调为研究观察。")
        quality_penalty_applied = True

    if financial_quality in {"degraded", "failed"} and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("财务摘要质量不足，候选已下调为研究观察。")
        quality_penalty_applied = True

    if announcement_quality == "failed" and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("公告输入质量不足，事件驱动不提升优先级。")
        quality_penalty_applied = True

    if target_v2_list_type == "READY_TO_BUY" and (
        bars_quality != "ok"
        or financial_quality == "failed"
        or announcement_quality == "failed"
    ):
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("质量门槛未满足，已从交易候选降级为研究观察。")
        quality_penalty_applied = True

    combined_weight = (
        0.5 * _QUALITY_WEIGHT[bars_quality]
        + 0.3 * _QUALITY_WEIGHT[financial_quality]
        + 0.2 * _QUALITY_WEIGHT[announcement_quality]
    )
    adjusted_score = max(0, min(100, int(round(origin_screener_score * combined_weight))))
    if adjusted_score != origin_screener_score:
        quality_penalty_applied = True
        quality_notes.append("数据质量折损已应用于候选评分。")

    quality_note = "；".join(dict.fromkeys(quality_notes)) if quality_notes else None
    return _QualityGateResult(
        target_v2_list_type=target_v2_list_type,
        target_screener_score=adjusted_score,
        quality_penalty_applied=quality_penalty_applied,
        quality_note=quality_note,
    )


def _append_failed_placeholders(
    *,
    ranked_avoid_candidates: list[ScreenerCandidate],
    failed_placeholders: list[ScreenerCandidate],
) -> list[ScreenerCandidate]:
    if not failed_placeholders:
        return ranked_avoid_candidates
    merged = list(ranked_avoid_candidates)
    for index, item in enumerate(failed_placeholders, start=len(merged) + 1):
        merged.append(item.model_copy(update={"rank": index}))
    return merged


def _safe_get_financial_summary(
    market_data_service: MarketDataService,
    symbol: str,
) -> tuple[Optional[FinancialSummary], _QUALITY_STATUS]:
    try:
        summary = market_data_service.get_stock_financial_summary(symbol)
        return summary, _normalize_quality_status(summary.quality_status)
    except DataServiceError:
        return None, "warning"


def _safe_get_recent_announcements(
    market_data_service: MarketDataService,
    symbol: str,
    as_of_date: date,
) -> tuple[list, _QUALITY_STATUS]:
    try:
        response = market_data_service.get_stock_announcements(
            symbol,
            start_date=(as_of_date - timedelta(days=30)).isoformat(),
            end_date=as_of_date.isoformat(),
            limit=50,
        )
    except DataServiceError:
        return [], "warning"
    return response.items, _normalize_quality_status(response.quality_status)

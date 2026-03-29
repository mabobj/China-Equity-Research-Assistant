"""选股器 pipeline。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
from time import perf_counter
from typing import TYPE_CHECKING, Optional

from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem
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
from app.services.screener_service.universe import load_scan_universe

if TYPE_CHECKING:
    from app.services.factor_service.snapshot import FactorSnapshotService
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )

logger = logging.getLogger(__name__)
_RULE_VERSION = "screener_workflow_v1"
_RULE_SUMMARY = "基于趋势评分、因子快照与风险约束的规则初筛。"


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
            "baostock",
            "mootdx",
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
    ) -> ScreenerRunResponse:
        started_at = perf_counter()

        with self._market_data_service.session_scope():
            total_symbols, scan_items = load_scan_universe(
                market_data_service=self._market_data_service,
                max_symbols=max_symbols,
            )
            scanned_symbols = len(scan_items)
            candidates: list[ScreenerCandidate] = []
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

        if self._factor_snapshot_service is not None:
            factor_snapshot = self._factor_snapshot_service.build_from_inputs(
                FactorBuildInputs(
                    symbol=item.symbol,
                    technical_snapshot=technical_snapshot,
                    daily_bars=daily_bars,
                    financial_summary=_safe_get_financial_summary(
                        self._market_data_service,
                        item.symbol,
                    ),
                    announcements=_safe_get_recent_announcements(
                        self._market_data_service,
                        item.symbol,
                        technical_snapshot.as_of_date,
                    ),
                )
            )
            score_result = score_factor_snapshot(
                factor_snapshot=factor_snapshot,
                technical_snapshot=technical_snapshot,
            )
        else:
            score_result = score_technical_snapshot(technical_snapshot)

        return _ScanResult(
            as_of_date=technical_snapshot.as_of_date,
            candidate=_build_candidate(
                item=item,
                technical_snapshot=technical_snapshot,
                score_result=score_result,
            ),
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
    candidate: ScreenerCandidate


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
) -> ScreenerCandidate:
    v2_list_type = score_result.v2_list_type
    evidence_hints = [
        *score_result.top_positive_factors[:2],
        *score_result.risk_notes[:1],
    ]
    return ScreenerCandidate(
        symbol=item.symbol,
        name=item.name,
        list_type=score_result.list_type,
        v2_list_type=v2_list_type,
        rank=1,
        screener_score=score_result.screener_score,
        alpha_score=score_result.alpha_score,
        trigger_score=score_result.trigger_score,
        risk_score=score_result.risk_score,
        trend_state=technical_snapshot.trend_state,
        trend_score=technical_snapshot.trend_score,
        latest_close=technical_snapshot.latest_close,
        support_level=technical_snapshot.support_level,
        resistance_level=technical_snapshot.resistance_level,
        top_positive_factors=score_result.top_positive_factors,
        top_negative_factors=score_result.top_negative_factors,
        risk_notes=score_result.risk_notes,
        short_reason=score_result.short_reason,
        calculated_at=datetime.now(timezone.utc),
        rule_version=_RULE_VERSION,
        rule_summary=_RULE_SUMMARY,
        headline_verdict=_build_headline_verdict(item.name, v2_list_type, score_result.short_reason),
        action_now=_build_action_now(v2_list_type),
        evidence_hints=evidence_hints[:3],
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


def _build_headline_verdict(name: str, v2_list_type: str, short_reason: str) -> str:
    prefix_map = {
        "READY_TO_BUY": f"{name} is actionable now, but still needs execution discipline.",
        "WATCH_PULLBACK": f"{name} is worth tracking, but the better setup is a pullback.",
        "WATCH_BREAKOUT": f"{name} is worth tracking, but breakout confirmation is still needed.",
        "RESEARCH_ONLY": f"{name} made the research list, but not the trading list yet.",
        "AVOID": f"{name} stays on the avoid side for now.",
    }
    prefix = prefix_map.get(v2_list_type, f"{name} needs more confirmation.")
    return f"{prefix} {short_reason}".strip()


def _safe_get_financial_summary(
    market_data_service: MarketDataService,
    symbol: str,
):
    try:
        return market_data_service.get_stock_financial_summary(symbol)
    except DataServiceError:
        return None


def _safe_get_recent_announcements(
    market_data_service: MarketDataService,
    symbol: str,
    as_of_date: date,
):
    try:
        response = market_data_service.get_stock_announcements(
            symbol,
            start_date=(as_of_date - timedelta(days=30)).isoformat(),
            end_date=as_of_date.isoformat(),
            limit=50,
        )
    except DataServiceError:
        return []
    return response.items

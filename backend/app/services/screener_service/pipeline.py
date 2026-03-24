"""选股器 pipeline。"""

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from time import perf_counter
from typing import Optional

from app.schemas.market_data import UniverseItem
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.feature_service.technical_analysis_service import (
    TechnicalAnalysisService,
)
from app.services.screener_service.filters import (
    has_abnormal_price_data,
    has_acceptable_liquidity,
    has_sufficient_daily_bars,
)
from app.services.screener_service.scoring import score_technical_snapshot
from app.services.screener_service.universe import load_scan_universe

logger = logging.getLogger(__name__)


class ScreenerPipeline:
    """执行全市场规则初筛。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        lookback_days: int = 400,
        progress_log_interval: int = 100,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._lookback_days = max(lookback_days, 180)
        self._progress_log_interval = max(progress_log_interval, 1)

    def run_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> ScreenerRunResponse:
        """运行规则初筛选股器。"""
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

        buy_candidates = _rank_candidates(
            [item for item in candidates if item.list_type == "BUY_CANDIDATE"],
            top_n=top_n,
        )
        watch_candidates = _rank_candidates(
            [item for item in candidates if item.list_type == "WATCHLIST"],
            top_n=top_n,
        )
        avoid_candidates = _rank_candidates(
            [item for item in candidates if item.list_type == "AVOID"],
            top_n=top_n,
        )

        logger.info(
            "初筛完成：实际扫描=%s，产出=%s，跳过=%s，BUY=%s，WATCH=%s，AVOID=%s，耗时=%.1fs",
            scanned_symbols,
            len(candidates),
            skipped_symbols,
            len(buy_candidates),
            len(watch_candidates),
            len(avoid_candidates),
            perf_counter() - started_at,
        )

        return ScreenerRunResponse(
            as_of_date=latest_as_of_date or date.today(),
            total_symbols=total_symbols,
            scanned_symbols=scanned_symbols,
            buy_candidates=buy_candidates,
            watch_candidates=watch_candidates,
            avoid_candidates=avoid_candidates,
        )

    def _scan_one_symbol(
        self,
        item: UniverseItem,
        start_date: str,
    ) -> Optional["_ScanResult"]:
        """扫描单个 symbol。"""
        try:
            daily_bars = self._market_data_service.get_daily_bars(
                item.symbol,
                start_date=start_date,
            )
        except DataServiceError:
            return None

        if not has_sufficient_daily_bars(daily_bars):
            return None
        if not has_acceptable_liquidity(daily_bars):
            return None
        if has_abnormal_price_data(daily_bars):
            return None

        try:
            build_snapshot = getattr(
                self._technical_analysis_service,
                "build_snapshot_from_bars",
                None,
            )
            if callable(build_snapshot):
                snapshot = build_snapshot(
                    symbol=item.symbol,
                    bars=daily_bars.bars,
                )
            else:
                snapshot = self._technical_analysis_service.get_technical_snapshot(
                    item.symbol,
                )
        except DataServiceError:
            return None

        score_result = score_technical_snapshot(snapshot)
        return _ScanResult(
            as_of_date=snapshot.as_of_date,
            candidate=ScreenerCandidate(
                symbol=item.symbol,
                name=item.name,
                list_type=score_result.list_type,
                rank=1,
                screener_score=score_result.screener_score,
                trend_state=snapshot.trend_state,
                trend_score=snapshot.trend_score,
                latest_close=snapshot.latest_close,
                support_level=snapshot.support_level,
                resistance_level=snapshot.resistance_level,
                short_reason=score_result.short_reason,
            ),
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
        """按固定间隔输出初筛进度日志。"""
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
    """按分数排序并重新编号。"""
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (item.screener_score, item.trend_score, item.symbol),
        reverse=True,
    )
    if top_n is not None:
        sorted_candidates = sorted_candidates[: max(top_n, 0)]

    ranked_candidates: list[ScreenerCandidate] = []
    for index, candidate in enumerate(sorted_candidates, start=1):
        ranked_candidates.append(candidate.model_copy(update={"rank": index}))
    return ranked_candidates

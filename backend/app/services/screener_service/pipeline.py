"""选股器 pipeline。"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.schemas.market_data import UniverseItem
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService
from app.services.screener_service.filters import (
    has_abnormal_price_data,
    has_acceptable_liquidity,
    has_sufficient_daily_bars,
)
from app.services.screener_service.scoring import score_technical_snapshot
from app.services.screener_service.universe import load_scan_universe


class ScreenerPipeline:
    """执行全市场规则初筛。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service

    def run_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> ScreenerRunResponse:
        """运行规则初筛选股器。"""
        total_symbols, scan_items = load_scan_universe(
            market_data_service=self._market_data_service,
            max_symbols=max_symbols,
        )
        scanned_symbols = len(scan_items)
        candidates: list[ScreenerCandidate] = []
        latest_as_of_date: Optional[date] = None

        for item in scan_items:
            scan_result = self._scan_one_symbol(item)
            if scan_result is None:
                continue
            candidates.append(scan_result.candidate)
            if latest_as_of_date is None or scan_result.as_of_date > latest_as_of_date:
                latest_as_of_date = scan_result.as_of_date

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

        return ScreenerRunResponse(
            as_of_date=latest_as_of_date or date.today(),
            total_symbols=total_symbols,
            scanned_symbols=scanned_symbols,
            buy_candidates=buy_candidates,
            watch_candidates=watch_candidates,
            avoid_candidates=avoid_candidates,
        )

    def _scan_one_symbol(self, item: UniverseItem) -> Optional["_ScanResult"]:
        """扫描单个 symbol。"""
        try:
            daily_bars = self._market_data_service.get_daily_bars(item.symbol)
        except DataServiceError:
            return None

        if not has_sufficient_daily_bars(daily_bars):
            return None
        if not has_acceptable_liquidity(daily_bars):
            return None
        if has_abnormal_price_data(daily_bars):
            return None

        try:
            snapshot = self._technical_analysis_service.get_technical_snapshot(item.symbol)
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


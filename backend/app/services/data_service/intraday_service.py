"""盘中数据快照 service。"""

from __future__ import annotations

from typing import Optional

from app.schemas.intraday import IntradaySnapshot
from app.schemas.market_data import IntradayBar, IntradayBarResponse
from app.services.data_service.exceptions import DataNotFoundError, InsufficientDataError
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.normalize import normalize_symbol


class IntradayService:
    """基于分钟线数据构建盘中快照。"""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: Optional[int] = None,
    ) -> IntradayBarResponse:
        """透传分钟线查询，供上层复用。"""
        return self._market_data_service.get_intraday_bars(
            symbol=symbol,
            frequency=frequency,
            limit=limit,
        )

    def get_intraday_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> IntradaySnapshot:
        """基于最近一段分钟线生成盘中快照。"""
        canonical_symbol = normalize_symbol(symbol)
        response = self._market_data_service.get_intraday_bars(
            symbol=canonical_symbol,
            frequency=frequency,
            limit=limit,
        )
        return self.build_snapshot_from_bars(
            symbol=canonical_symbol,
            frequency=frequency,
            bars=response.bars,
        )

    def build_snapshot_from_bars(
        self,
        symbol: str,
        frequency: str,
        bars: list[IntradayBar],
    ) -> IntradaySnapshot:
        """基于已加载分钟线生成盘中快照。"""
        canonical_symbol = normalize_symbol(symbol)
        if not bars:
            raise DataNotFoundError(
                "No intraday bars found for symbol {symbol}.".format(
                    symbol=canonical_symbol,
                ),
            )

        sorted_bars = sorted(bars, key=lambda item: item.trade_datetime)
        latest_bar = sorted_bars[-1]
        latest_price = _first_valid_number(latest_bar.close, latest_bar.open)
        session_open = _first_valid_number(sorted_bars[0].open, sorted_bars[0].close)
        if latest_price is None or session_open is None:
            raise InsufficientDataError("Intraday bars are missing open/close values.")

        high_values = [
            value
            for bar in sorted_bars
            if (value := _first_valid_number(bar.high, bar.close, bar.open)) is not None
        ]
        low_values = [
            value
            for bar in sorted_bars
            if (value := _first_valid_number(bar.low, bar.close, bar.open)) is not None
        ]
        if not high_values or not low_values:
            raise InsufficientDataError("Intraday bars are missing high/low values.")
        session_high = max(high_values)
        session_low = min(low_values)

        volume_values = [bar.volume for bar in sorted_bars if bar.volume is not None]
        volume_sum = float(sum(volume_values)) if volume_values else None
        intraday_return_pct = _safe_pct_change(session_open, latest_price)
        range_pct = _safe_pct_change(session_open, session_high - session_low, base_is_delta=True)

        return IntradaySnapshot(
            symbol=canonical_symbol,
            frequency=frequency,
            latest_price=float(latest_price),
            latest_datetime=latest_bar.trade_datetime,
            session_high=float(session_high),
            session_low=float(session_low),
            session_open=float(session_open),
            volume_sum=volume_sum,
            intraday_return_pct=intraday_return_pct,
            range_pct=range_pct,
            source=latest_bar.source,
        )


def _first_valid_number(*values: Optional[float]) -> Optional[float]:
    for value in values:
        if value is not None:
            return float(value)
    return None


def _safe_pct_change(
    base: float,
    value: float,
    *,
    base_is_delta: bool = False,
) -> Optional[float]:
    if base == 0:
        return None
    if base_is_delta:
        return float(value / base * 100)
    return float((value - base) / base * 100)

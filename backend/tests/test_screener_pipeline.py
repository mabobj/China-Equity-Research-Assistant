"""选股器 pipeline 测试。"""

from contextlib import contextmanager
from datetime import date, timedelta
import logging
from typing import Iterator, Optional

from app.schemas.factor import (
    AlphaScore,
    FactorGroupScore,
    FactorSnapshot,
    RiskScore,
    TriggerScore,
)
from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem, UniverseResponse
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary
from app.schemas.screener import ScreenerRunResponse
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.screener_service.pipeline import ScreenerPipeline


class FakeMarketDataService:
    """用于选股器测试的假市场数据服务。"""

    def __init__(self) -> None:
        self.session_scope_entered = 0
        self.requested_start_dates: list[str] = []
        self.financial_allow_remote_sync_seen: list[bool] = []
        self.announcement_allow_remote_sync_seen: list[bool] = []

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        self.session_scope_entered += 1
        yield

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=4,
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    code="600519",
                    exchange="SH",
                    name="贵州茅台",
                    source="fake",
                ),
                UniverseItem(
                    symbol="000001.SZ",
                    code="000001",
                    exchange="SZ",
                    name="平安银行",
                    source="fake",
                ),
                UniverseItem(
                    symbol="300750.SZ",
                    code="300750",
                    exchange="SZ",
                    name="*ST测试",
                    source="fake",
                ),
                UniverseItem(
                    symbol="688001.SH",
                    code="688001",
                    exchange="SH",
                    name="华兴股份",
                    source="fake",
                ),
            ],
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        if start_date is not None:
            self.requested_start_dates.append(start_date)

        if symbol == "688001.SH":
            return DailyBarResponse(
                symbol=symbol,
                count=20,
                bars=_build_bars(symbol=symbol, length=20, close_start=10.0),
                quality_status="ok",
            )

        if symbol == "000001.SZ":
            return DailyBarResponse(
                symbol=symbol,
                count=40,
                bars=_build_bars(
                    symbol=symbol,
                    length=40,
                    close_start=8.0,
                    amount=25_000_000.0,
                ),
                quality_status="ok",
            )

        return DailyBarResponse(
            symbol=symbol,
            count=40,
            bars=_build_bars(
                symbol=symbol,
                length=40,
                close_start=100.0,
                amount=60_000_000.0,
            ),
            quality_status="ok",
        )

    def get_stock_financial_summary(
        self,
        symbol: str,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
    ) -> FinancialSummary:
        self.financial_allow_remote_sync_seen.append(allow_remote_sync)
        return FinancialSummary(
            symbol=symbol,
            name="测试股票",
            revenue=100.0,
            revenue_yoy=15.0,
            net_profit=20.0,
            net_profit_yoy=18.0,
            roe=16.0,
            debt_ratio=35.0,
            eps=2.0,
            source="fake",
            quality_status="ok",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
    ) -> AnnouncementListResponse:
        self.announcement_allow_remote_sync_seen.append(allow_remote_sync)
        return AnnouncementListResponse(
            symbol=symbol,
            count=1,
            items=[],
            quality_status="ok",
            cleaning_warnings=[],
        )


class FakeMarketDataServiceWithProviderNames(FakeMarketDataService):
    """支持 provider_names 参数，用于验证批量优先级透传。"""

    def __init__(self) -> None:
        super().__init__()
        self.provider_names_seen: list[tuple[str, ...]] = []

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
        provider_names: Optional[tuple[str, ...]] = None,
    ) -> DailyBarResponse:
        if provider_names is not None:
            self.provider_names_seen.append(provider_names)
        return super().get_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )


class FakeTechnicalAnalysisService:
    """用于选股器测试的假技术分析服务。"""

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TechnicalSnapshot:
        if symbol == "600519.SH":
            return _build_snapshot(
                symbol=symbol,
                trend_state="up",
                trend_score=80,
                latest_close=120.0,
                support_level=115.0,
                resistance_level=122.0,
                volume_ratio_to_ma20=1.15,
            )

        return _build_snapshot(
            symbol=symbol,
            trend_state="neutral",
            trend_score=58,
            latest_close=20.0,
            support_level=19.0,
            resistance_level=22.0,
            volume_ratio_to_ma20=0.95,
        )

    def build_snapshot_from_bars(self, symbol: str, bars: list[DailyBar]) -> TechnicalSnapshot:
        return self.get_technical_snapshot(symbol)


class FakeFactorSnapshotService:
    """用于选股器测试的假因子服务。"""

    def build_from_inputs(self, inputs) -> FactorSnapshot:
        if inputs.symbol == "600519.SH":
            return FactorSnapshot(
                symbol=inputs.symbol,
                as_of_date=date(2024, 3, 25),
                raw_factors={"return_20d": 0.12},
                normalized_factors={"return_20d": 82.0},
                factor_group_scores=[
                    FactorGroupScore(
                        group_name="trend",
                        score=82.0,
                        top_positive_signals=["20日收益率保持正向，短期相对强弱仍在改善"],
                        top_negative_signals=[],
                    ),
                    FactorGroupScore(
                        group_name="quality",
                        score=75.0,
                        top_positive_signals=["ROE 高于常见阈值，资本回报质量较好"],
                        top_negative_signals=[],
                    ),
                ],
                alpha_score=AlphaScore(total_score=80, breakdown=[]),
                trigger_score=TriggerScore(
                    total_score=74,
                    trigger_state="pullback",
                    breakdown=[],
                ),
                risk_score=RiskScore(total_score=32, breakdown=[]),
            )

        return FactorSnapshot(
            symbol=inputs.symbol,
            as_of_date=date(2024, 3, 25),
            raw_factors={"return_20d": 0.02},
            normalized_factors={"return_20d": 55.0},
            factor_group_scores=[
                FactorGroupScore(
                    group_name="trend",
                    score=55.0,
                    top_positive_signals=[],
                    top_negative_signals=["20日收益率偏弱，短期相对强弱不足"],
                ),
            ],
            alpha_score=AlphaScore(total_score=56, breakdown=[]),
            trigger_score=TriggerScore(
                total_score=52,
                trigger_state="neutral",
                breakdown=[],
            ),
            risk_score=RiskScore(total_score=58, breakdown=[]),
        )


def test_run_screener_returns_compatible_and_v2_candidates() -> None:
    """pipeline 应同时返回兼容字段与 v2 分桶。"""
    market_data_service = FakeMarketDataService()
    pipeline = ScreenerPipeline(
        market_data_service=market_data_service,
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
    )

    response = pipeline.run_screener()

    assert isinstance(response, ScreenerRunResponse)
    assert response.total_symbols == 4
    assert response.scanned_symbols == 3
    assert len(response.buy_candidates) == 1
    assert response.buy_candidates[0].symbol == "600519.SH"
    assert response.buy_candidates[0].list_type == "BUY_CANDIDATE"
    assert response.buy_candidates[0].v2_list_type == "READY_TO_BUY"
    assert response.buy_candidates[0].alpha_score == 80
    assert len(response.ready_to_buy_candidates) == 1
    assert len(response.research_only_candidates) == 1
    assert len(response.watch_candidates) == 1
    assert len(response.avoid_candidates) == 0
    all_candidates = (
        response.buy_candidates
        + response.watch_candidates
        + response.avoid_candidates
    )
    for candidate in all_candidates:
        assert "is worth tracking" not in candidate.short_reason.lower()
        assert "is worth tracking" not in candidate.headline_verdict.lower()
    assert market_data_service.session_scope_entered == 1
    assert len(market_data_service.requested_start_dates) == 3


def test_run_screener_uses_mootdx_first_provider_priority() -> None:
    """批量日线查询应优先 mootdx。"""
    market_data_service = FakeMarketDataServiceWithProviderNames()
    pipeline = ScreenerPipeline(
        market_data_service=market_data_service,
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
    )

    _ = pipeline.run_screener(max_symbols=2)

    assert market_data_service.provider_names_seen
    assert market_data_service.provider_names_seen[0] == (
        "mootdx",
        "baostock",
        "akshare",
    )
    assert market_data_service.financial_allow_remote_sync_seen
    assert set(market_data_service.financial_allow_remote_sync_seen) == {False}
    assert market_data_service.announcement_allow_remote_sync_seen
    assert set(market_data_service.announcement_allow_remote_sync_seen) == {False}


def test_run_screener_generates_failed_placeholder_when_bars_quality_failed() -> None:
    """bars_quality=failed 时应生成失败占位且不进入高优先级候选。"""

    class FailedBarsMarketDataService(FakeMarketDataService):
        def get_daily_bars(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
        ) -> DailyBarResponse:
            base = super().get_daily_bars(symbol, start_date=start_date, end_date=end_date)
            return base.model_copy(
                update={
                    "quality_status": "failed",
                    "cleaning_warnings": ["ohlc_relation_invalid"],
                }
            )

    pipeline = ScreenerPipeline(
        market_data_service=FailedBarsMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
    )
    response = pipeline.run_screener(
        scan_items=[
            UniverseItem(
                symbol="600519.SH",
                code="600519",
                exchange="SH",
                name="贵州茅台",
                source="fake",
            )
        ],
    )

    assert len(response.buy_candidates) == 0
    assert len(response.watch_candidates) == 0
    assert len(response.avoid_candidates) == 1
    placeholder = response.avoid_candidates[0]
    assert placeholder.v2_list_type == "AVOID"
    assert placeholder.fail_reason is not None
    assert placeholder.bars_quality == "failed"
    assert placeholder.quality_penalty_applied is True


def test_run_screener_downgrades_candidate_when_financial_quality_degraded() -> None:
    """financial_quality=degraded 时应降级到 RESEARCH_ONLY。"""

    class DegradedFinancialMarketDataService(FakeMarketDataService):
        def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
            payload = super().get_stock_financial_summary(symbol)
            return payload.model_copy(
                update={
                    "quality_status": "degraded",
                    "missing_fields": ["revenue", "net_profit", "roe"],
                }
            )

    pipeline = ScreenerPipeline(
        market_data_service=DegradedFinancialMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
    )
    response = pipeline.run_screener(
        scan_items=[
            UniverseItem(
                symbol="600519.SH",
                code="600519",
                exchange="SH",
                name="贵州茅台",
                source="fake",
            )
        ],
    )

    assert len(response.ready_to_buy_candidates) == 0
    assert len(response.research_only_candidates) == 1
    candidate = response.research_only_candidates[0]
    assert candidate.financial_quality == "degraded"
    assert candidate.quality_penalty_applied is True
    assert candidate.quality_note is not None


def test_run_screener_downgrades_candidate_when_announcement_quality_failed() -> None:
    """announcement_quality=failed 时不允许事件驱动升级。"""

    class FailedAnnouncementMarketDataService(FakeMarketDataService):
        def get_stock_announcements(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            limit: int = 20,
        ) -> AnnouncementListResponse:
            response = super().get_stock_announcements(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            return response.model_copy(update={"quality_status": "failed"})

    pipeline = ScreenerPipeline(
        market_data_service=FailedAnnouncementMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
    )
    response = pipeline.run_screener(
        scan_items=[
            UniverseItem(
                symbol="600519.SH",
                code="600519",
                exchange="SH",
                name="贵州茅台",
                source="fake",
            )
        ],
    )

    assert len(response.ready_to_buy_candidates) == 0
    assert len(response.research_only_candidates) == 1
    candidate = response.research_only_candidates[0]
    assert candidate.announcement_quality == "failed"
    assert candidate.quality_penalty_applied is True
    assert candidate.quality_note is not None


def _build_bars(
    symbol: str,
    length: int,
    close_start: float,
    amount: float = 50_000_000.0,
) -> list[DailyBar]:
    """构造测试用日线数据。"""
    start = date(2024, 1, 1)
    bars: list[DailyBar] = []
    for index in range(length):
        close_value = close_start + index * 0.5
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start + timedelta(days=index),
                open=close_value - 0.2,
                high=close_value + 0.5,
                low=close_value - 0.5,
                close=close_value,
                volume=500000.0 + index * 1000.0,
                amount=amount,
                source="fake",
            ),
        )
    return bars


def _build_snapshot(
    symbol: str,
    trend_state: str,
    trend_score: int,
    latest_close: float,
    support_level: float,
    resistance_level: float,
    volume_ratio_to_ma20: float,
) -> TechnicalSnapshot:
    """构造测试用技术快照。"""
    return TechnicalSnapshot(
        symbol=symbol,
        as_of_date=date(2024, 3, 25),
        latest_close=latest_close,
        latest_volume=600000.0,
        moving_averages=MovingAverageSnapshot(
            ma5=latest_close - 1.0,
            ma10=latest_close - 1.5,
            ma20=latest_close - 2.0,
            ma60=latest_close - 4.0,
            ma120=latest_close - 6.0,
        ),
        ema=EmaSnapshot(
            ema12=latest_close - 1.2,
            ema26=latest_close - 2.1,
        ),
        macd=MacdSnapshot(
            macd=2.0,
            signal=1.4,
            histogram=0.6,
        ),
        rsi14=58.0,
        atr14=1.5,
        bollinger=BollingerSnapshot(
            middle=latest_close - 2.0,
            upper=latest_close + 3.0,
            lower=latest_close - 5.0,
        ),
        volume_metrics=VolumeMetricsSnapshot(
            volume_ma5=580000.0,
            volume_ma20=550000.0,
            volume_ratio_to_ma5=1.03,
            volume_ratio_to_ma20=volume_ratio_to_ma20,
        ),
        trend_state=trend_state,
        trend_score=trend_score,
        volatility_state="normal",
        support_level=support_level,
        resistance_level=resistance_level,
    )


def test_run_screener_emits_structured_runtime_logs(caplog) -> None:
    market_data_service = FakeMarketDataService()
    pipeline = ScreenerPipeline(
        market_data_service=market_data_service,
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
        progress_log_interval=1,
    )

    with caplog.at_level(logging.INFO):
        pipeline.run_screener(
            max_symbols=2,
            run_context={
                "run_id": "run-log-001",
                "workflow_name": "screener_run",
                "batch_size": 2,
                "cursor_start_symbol": "000001.SZ",
                "cursor_start_index": 0,
            },
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any("event=screener.pipeline.started" in message for message in messages)
    assert any("event=screener.symbol.completed" in message for message in messages)
    assert any("event=screener.run.heartbeat" in message for message in messages)
    assert any("event=screener.pipeline.completed" in message for message in messages)
    assert any("run_id=run-log-001" in message for message in messages)


def test_run_screener_keeps_contract_under_controlled_parallel_scan() -> None:
    market_data_service = FakeMarketDataService()
    pipeline = ScreenerPipeline(
        market_data_service=market_data_service,
        technical_analysis_service=FakeTechnicalAnalysisService(),
        factor_snapshot_service=FakeFactorSnapshotService(),
        batch_scan_max_workers=3,
    )

    response = pipeline.run_screener(max_symbols=3)

    assert response.scanned_symbols == 3
    assert len(response.buy_candidates) == 1
    assert len(response.watch_candidates) == 1
    assert len(response.avoid_candidates) == 0
    assert market_data_service.session_scope_entered == 1

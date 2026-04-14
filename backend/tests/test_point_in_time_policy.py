"""点时一致性策略测试。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.schemas.backtest import ScreenerBacktestRunRequest
from app.schemas.dataset import FeatureDatasetBuildRequest, LabelDatasetBuildRequest
from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem, UniverseResponse
from app.services.backtest_service import backtest_service as backtest_service_module
from app.services.backtest_service.backtest_service import BacktestService
from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset
from app.services.data_products.freshness import (
    resolve_daily_analysis_context,
    resolve_label_analysis_context,
)
from app.services.dataset_service import dataset_service as dataset_service_module
from app.services.dataset_service.dataset_service import DatasetService
from app.services.experiment_service.experiment_service import ExperimentService
from app.services.label_service import label_service as label_service_module
from app.services.label_service.label_service import LabelService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.repository import LineageRepository
from app.services.prediction_service.prediction_service import PredictionService


class _StubMarketDataService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._symbols = ["600519.SH", "000001.SZ"]
        self._bars: dict[str, list[DailyBar]] = {}
        start = date(2026, 1, 2)
        for symbol in self._symbols:
            close = 100.0 if symbol == "600519.SH" else 80.0
            volume = 1_000_000.0 if symbol == "600519.SH" else 700_000.0
            current = start
            bars: list[DailyBar] = []
            while len(bars) < 80:
                if current.weekday() < 5:
                    close += 0.5 if symbol == "600519.SH" else 0.2
                    volume += 10_000.0
                    bars.append(
                        DailyBar(
                            symbol=symbol,
                            trade_date=current,
                            open=close - 0.4,
                            high=close + 0.6,
                            low=close - 0.7,
                            close=round(close, 2),
                            volume=round(volume, 2),
                            amount=round(close * volume, 2),
                            source="stub",
                        )
                    )
                current += timedelta(days=1)
            self._bars[symbol] = bars

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=len(self._symbols),
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    code="600519",
                    exchange="SH",
                    name="贵州茅台",
                    source="stub",
                ),
                UniverseItem(
                    symbol="000001.SZ",
                    code="000001",
                    exchange="SZ",
                    name="平安银行",
                    source="stub",
                ),
            ],
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
        provider_names=None,
    ) -> DailyBarResponse:
        self.calls.append(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "force_refresh": force_refresh,
                "allow_remote_sync": allow_remote_sync,
                "provider_names": provider_names,
            }
        )
        bars = list(self._bars[symbol])
        if start_date is not None:
            start_value = date.fromisoformat(start_date)
            bars = [bar for bar in bars if bar.trade_date >= start_value]
        if end_date is not None:
            end_value = date.fromisoformat(end_date)
            bars = [bar for bar in bars if bar.trade_date <= end_value]
        return DailyBarResponse(
            symbol=symbol,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            count=len(bars),
            bars=bars,
            quality_status="ok",
            cleaning_warnings=[],
            dropped_rows=0,
            dropped_duplicate_rows=0,
        )


class _StubExperimentService:
    def get_default_model_version(self) -> str:
        return "baseline-rule-v1"


class _StubLabelService:
    def __init__(self) -> None:
        self.request_dates: list[date] = []

    def build_label_dataset(self, request) -> object:
        self.request_dates.append(request.as_of_date)
        return type(
            "_LabelDataset",
            (),
            {
                "summary": type(
                    "_Summary",
                    (),
                    {"label_version": f"labels-{request.as_of_date.isoformat()}-v1"},
                )()
            },
        )()

    def load_label_records(self, _label_version: str) -> list[dict[str, float]]:
        return [{"symbol": "600519.SH", "forward_return_5d": 0.03}]


class _StubPredictionService:
    def __init__(self) -> None:
        self.request_dates: list[date] = []

    def run_cross_section_prediction(self, request) -> object:
        self.request_dates.append(request.as_of_date)
        return type(
            "_PredictionRun",
            (),
            {"candidates": [type("_Candidate", (), {"symbol": "600519.SH"})()]},
        )()


def test_resolve_daily_analysis_context_uses_last_closed_day() -> None:
    context = resolve_daily_analysis_context(today=date(2026, 4, 6))
    assert context.effective_as_of_date == date(2026, 4, 3)
    assert context.policy_name == "last_closed_trading_day"


def test_resolve_label_analysis_context_uses_safe_buffer() -> None:
    context = resolve_label_analysis_context(today=date(2026, 4, 6))
    assert context.effective_as_of_date == date(2026, 3, 20)
    assert context.policy_name == "last_closed_trading_day_minus_14_days"


def test_daily_bars_daily_dataset_accepts_explicit_as_of_date() -> None:
    market_data_service = _StubMarketDataService()
    dataset = DailyBarsDailyDataset(market_data_service=market_data_service)

    result = dataset.get("600519.SH", as_of_date=date(2026, 3, 20))

    assert result.as_of_date == date(2026, 3, 20)
    assert market_data_service.calls[0]["end_date"] == "2026-03-20"


def test_dataset_service_uses_central_daily_policy_when_as_of_date_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        dataset_service_module,
        "resolve_daily_analysis_as_of_date",
        lambda _as_of_date=None: date(2026, 3, 27),
    )
    market_data_service = _StubMarketDataService()
    service = DatasetService(
        root_dir=tmp_path / "datasets",
        default_feature_version="features-v0-baseline",
        market_data_service=market_data_service,
        daily_bars_daily=DailyBarsDailyDataset(market_data_service=market_data_service),
        lineage_service=LineageService(
            repository=LineageRepository(tmp_path / "lineage-dataset.sqlite3")
        ),
    )

    response = service.build_feature_dataset(
        FeatureDatasetBuildRequest(
            max_symbols=2,
            force_refresh=True,
        )
    )

    assert response.summary.as_of_date == date(2026, 3, 27)
    assert response.summary.dataset_version == "features-2026-03-27-v1"


def test_label_service_uses_central_label_policy_when_as_of_date_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        label_service_module,
        "resolve_label_analysis_as_of_date",
        lambda _as_of_date=None: date(2026, 3, 20),
    )
    market_data_service = _StubMarketDataService()
    dataset_service = DatasetService(
        root_dir=tmp_path / "datasets",
        default_feature_version="features-v0-baseline",
        market_data_service=market_data_service,
        daily_bars_daily=DailyBarsDailyDataset(market_data_service=market_data_service),
        lineage_service=LineageService(
            repository=LineageRepository(tmp_path / "lineage-label.sqlite3")
        ),
    )
    service = LabelService(
        default_label_version="labels-v0-forward-return",
        root_dir=tmp_path / "datasets",
        market_data_service=market_data_service,
        dataset_service=dataset_service,
        daily_bars_daily=DailyBarsDailyDataset(market_data_service=market_data_service),
        lineage_service=LineageService(
            repository=LineageRepository(tmp_path / "lineage-label-service.sqlite3")
        ),
    )

    response = service.build_label_dataset(
        LabelDatasetBuildRequest(
            max_symbols=2,
            force_refresh=True,
        )
    )

    assert response.summary.as_of_date == date(2026, 3, 20)
    assert response.summary.label_version == "labels-2026-03-20-v1"


def test_backtest_service_uses_central_label_policy_for_default_window_end(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        backtest_service_module,
        "resolve_label_analysis_as_of_date",
        lambda: date(2026, 3, 20),
    )
    label_service = _StubLabelService()
    prediction_service = _StubPredictionService()
    service = BacktestService(
        experiment_service=_StubExperimentService(),
        label_service=label_service,
        prediction_service=prediction_service,
        lineage_service=LineageService(
            repository=LineageRepository(tmp_path / "lineage-backtest.sqlite3")
        ),
    )

    response = service.run_screener_backtest(
        ScreenerBacktestRunRequest(
            lookback_days=40,
            top_k=1,
        )
    )

    assert response.window_end == date(2026, 3, 20)
    assert label_service.request_dates
    assert prediction_service.request_dates

"""预测数据链路服务测试（特征/标签/预测/回测）。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.schemas.backtest import ScreenerBacktestRunRequest
from app.schemas.dataset import FeatureDatasetBuildRequest, LabelDatasetBuildRequest
from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem, UniverseResponse
from app.schemas.prediction import CrossSectionPredictionRunRequest
from app.services.backtest_service.backtest_service import BacktestService
from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset
from app.services.dataset_service.dataset_service import DatasetService
from app.services.evaluation_service.evaluation_service import EvaluationService
from app.services.experiment_service.experiment_service import ExperimentService
from app.services.label_service.label_service import LabelService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.repository import LineageRepository
from app.services.prediction_service.prediction_service import PredictionService


class _StubMarketDataService:
    def __init__(self) -> None:
        self._symbols = ["600519.SH", "000001.SZ"]
        self._bars: dict[str, list[DailyBar]] = {}
        start = date(2026, 2, 2)
        for symbol in self._symbols:
            bars: list[DailyBar] = []
            close = 100.0 if symbol == "600519.SH" else 80.0
            volume = 1_000_000.0 if symbol == "600519.SH" else 700_000.0
            current = start
            while len(bars) < 45:
                if current.weekday() < 5:
                    close += 0.6 if symbol == "600519.SH" else 0.3
                    volume += 15_000 if symbol == "600519.SH" else 8_000
                    bars.append(
                        DailyBar(
                            symbol=symbol,
                            trade_date=current,
                            open=close - 0.5,
                            high=close + 0.7,
                            low=close - 0.8,
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
            count=2,
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        *,
        force_refresh: bool = False,
        provider_names=None,
    ) -> DailyBarResponse:
        bars = list(self._bars[symbol])
        if start_date is not None:
            start = date.fromisoformat(start_date)
            bars = [bar for bar in bars if bar.trade_date >= start]
        if end_date is not None:
            end = date.fromisoformat(end_date)
            bars = [bar for bar in bars if bar.trade_date <= end]
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


def _build_services(tmp_path: Path):
    market = _StubMarketDataService()
    experiment_service = ExperimentService()
    daily_bars_daily = DailyBarsDailyDataset(market_data_service=market)
    lineage_service = LineageService(
        repository=LineageRepository(tmp_path / "prediction_assets" / "lineage.sqlite3")
    )
    dataset_service = DatasetService(
        root_dir=tmp_path / "prediction_assets" / "datasets",
        default_feature_version=experiment_service.get_default_feature_version(),
        market_data_service=market,
        daily_bars_daily=daily_bars_daily,
        lineage_service=lineage_service,
    )
    label_service = LabelService(
        default_label_version=experiment_service.get_default_label_version(),
        root_dir=tmp_path / "prediction_assets" / "datasets",
        market_data_service=market,
        dataset_service=dataset_service,
        daily_bars_daily=daily_bars_daily,
        lineage_service=lineage_service,
    )
    prediction_service = PredictionService(
        dataset_service=dataset_service,
        label_service=label_service,
        experiment_service=experiment_service,
        lineage_service=lineage_service,
    )
    backtest_service = BacktestService(
        experiment_service=experiment_service,
        label_service=label_service,
        prediction_service=prediction_service,
        lineage_service=lineage_service,
    )
    evaluation_service = EvaluationService(
        experiment_service=experiment_service,
        label_service=label_service,
        backtest_service=backtest_service,
        lineage_service=lineage_service,
    )
    return (
        dataset_service,
        label_service,
        prediction_service,
        backtest_service,
        evaluation_service,
    )


def test_feature_and_label_dataset_build_chain(tmp_path: Path) -> None:
    dataset_service, label_service, _, _, _ = _build_services(tmp_path)
    as_of_date = date(2026, 3, 20)

    feature_dataset = dataset_service.build_feature_dataset(
        FeatureDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )
    assert feature_dataset.summary.symbol_count == 2
    assert feature_dataset.summary.lineage_metadata is not None
    assert feature_dataset.summary.upstream_sources
    feature_records = dataset_service.load_feature_records(
        feature_dataset.summary.dataset_version
    )
    assert len(feature_records) == 2

    label_dataset = label_service.build_label_dataset(
        LabelDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )
    assert label_dataset.summary.symbol_count == 2
    assert label_dataset.summary.feature_version == feature_dataset.summary.dataset_version
    assert label_dataset.summary.lineage_metadata is not None
    label_records = label_service.load_label_records(label_dataset.summary.label_version)
    assert len(label_records) == 2
    assert "forward_return_5d" in label_records[0]


def test_prediction_and_backtest_consume_real_dataset_records(tmp_path: Path) -> None:
    (
        dataset_service,
        label_service,
        prediction_service,
        backtest_service,
        _,
    ) = _build_services(tmp_path)
    as_of_date = date(2026, 3, 20)

    dataset_service.build_feature_dataset(
        FeatureDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )
    label_service.build_label_dataset(
        LabelDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )

    snapshot = prediction_service.get_symbol_prediction(
        symbol="600519.SH",
        as_of_date=as_of_date,
        model_version="baseline-rule-v1",
    )
    assert snapshot.symbol == "600519.SH"
    assert snapshot.predictive_score >= 0
    assert snapshot.feature_version.startswith("features-")
    assert snapshot.dataset_version.startswith("prediction_snapshot:")
    assert snapshot.lineage_metadata is not None

    cross = prediction_service.run_cross_section_prediction(
        CrossSectionPredictionRunRequest(
            model_version="baseline-rule-v1",
            as_of_date=as_of_date,
            max_symbols=2,
            top_k=1,
            force_refresh=False,
        )
    )
    assert cross.total_symbols == 2
    assert len(cross.candidates) == 1
    assert cross.lineage_metadata is not None

    backtest = backtest_service.run_screener_backtest(
        ScreenerBacktestRunRequest(
            model_version="baseline-rule-v1",
            lookback_days=120,
            top_k=1,
            as_of_end=as_of_date,
        )
    )
    assert backtest.backtest_type == "screener"
    assert "win_rate" in backtest.metrics
    assert backtest.lineage_metadata is not None


def test_symbol_prediction_fallback_when_feature_records_missing(tmp_path: Path) -> None:
    (
        _dataset_service,
        _label_service,
        prediction_service,
        _backtest_service,
        _evaluation_service,
    ) = _build_services(tmp_path)
    as_of_date = date(2026, 3, 20)

    snapshot = prediction_service.get_symbol_prediction(
        symbol="600519.SH",
        as_of_date=as_of_date,
        model_version="baseline-rule-v1",
        build_feature_dataset=False,
    )

    assert snapshot.symbol == "600519.SH"
    assert snapshot.predictive_score >= 0
    assert snapshot.feature_version.startswith("features-")
    assert snapshot.warning_messages
    assert snapshot.lineage_metadata is not None


def test_evaluation_service_consumes_real_backtest_metrics(tmp_path: Path) -> None:
    (
        dataset_service,
        label_service,
        _prediction_service,
        backtest_service,
        evaluation_service,
    ) = _build_services(tmp_path)
    as_of_date = date(2026, 3, 20)

    dataset_service.build_feature_dataset(
        FeatureDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )
    label_service.build_label_dataset(
        LabelDatasetBuildRequest(
            as_of_date=as_of_date,
            max_symbols=2,
            force_refresh=True,
        )
    )
    # 触发一次回测，确保评估可消费真实结果。
    backtest_service.run_screener_backtest(
        ScreenerBacktestRunRequest(
            model_version="baseline-rule-v1",
            lookback_days=120,
            top_k=1,
            as_of_end=as_of_date,
        )
    )

    evaluation = evaluation_service.get_model_evaluation("baseline-rule-v1")
    assert evaluation.model_version == "baseline-rule-v1"
    assert evaluation.backtest_references
    assert "screener_win_rate" in evaluation.metrics
    assert "quality_score" in evaluation.metrics
    assert evaluation.lineage_metadata is not None
    assert evaluation.recommendation is not None
    assert evaluation.recommendation.recommendation in {
        "keep_baseline",
        "observe",
    }

    compared = evaluation_service.get_model_evaluation("baseline-rule-v2")
    assert compared.comparison is not None
    assert compared.comparison.baseline_model_version == "baseline-rule-v1"
    assert "win_rate_delta" in compared.comparison.metric_deltas
    assert compared.recommendation is not None
    assert compared.recommendation.recommended_model_version != ""

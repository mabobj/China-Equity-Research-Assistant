"""Backtest service."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from app.schemas.backtest import (
    BacktestRunResponse,
    ScreenerBacktestRunRequest,
    StrategyBacktestRunRequest,
)
from app.schemas.dataset import LabelDatasetBuildRequest
from app.schemas.prediction import CrossSectionPredictionRunRequest
from app.services.data_products.freshness import resolve_label_analysis_as_of_date
from app.services.experiment_service.experiment_service import ExperimentService
from app.services.label_service.label_service import LabelService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.utils import (
    build_dependency,
    build_lineage_metadata,
    build_source_ref,
    utcnow,
)
from app.services.prediction_service.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class BacktestService:
    """Run minimal walk-forward backtests."""

    def __init__(
        self,
        *,
        experiment_service: ExperimentService,
        label_service: LabelService,
        prediction_service: PredictionService,
        lineage_service: LineageService,
    ) -> None:
        self._experiment_service = experiment_service
        self._label_service = label_service
        self._prediction_service = prediction_service
        self._lineage_service = lineage_service

    def run_screener_backtest(
        self,
        request: ScreenerBacktestRunRequest,
    ) -> BacktestRunResponse:
        model_version = (
            request.model_version or self._experiment_service.get_default_model_version()
        )
        window_end = request.as_of_end or _default_backtest_as_of_date()
        window_start = window_end - timedelta(days=request.lookback_days)
        slices = _build_walk_forward_slices(window_start=window_start, window_end=window_end)
        all_slice_returns: list[float] = []
        effective_slices = 0
        label_versions_used: set[str] = set()
        feature_versions_used: set[str] = set()

        for slice_date in slices:
            label_dataset = self._label_service.build_label_dataset(
                LabelDatasetBuildRequest(
                    as_of_date=slice_date,
                    max_symbols=max(request.top_k * 20, 300),
                    force_refresh=False,
                )
            )
            label_versions_used.add(label_dataset.summary.label_version)
            if label_dataset.summary.feature_version:
                feature_versions_used.add(label_dataset.summary.feature_version)

            label_records = self._label_service.load_label_records(
                label_dataset.summary.label_version
            )
            label_map = _build_label_map(label_records)
            prediction = self._prediction_service.run_cross_section_prediction(
                CrossSectionPredictionRunRequest(
                    max_symbols=max(request.top_k * 20, 300),
                    top_k=request.top_k,
                    as_of_date=slice_date,
                    model_version=model_version,
                )
            )
            feature_versions_used.add(prediction.feature_version)
            label_versions_used.add(prediction.label_version)
            candidate_symbols = [item.symbol for item in prediction.candidates]
            slice_returns = [
                label_map[symbol]["forward_return_5d"]
                for symbol in candidate_symbols
                if symbol in label_map
            ]
            if not slice_returns:
                continue
            effective_slices += 1
            all_slice_returns.append(sum(slice_returns) / len(slice_returns))

        metrics = _build_backtest_metrics(all_slice_returns)
        metrics["slice_count"] = float(effective_slices)
        run_id = _build_run_id(prefix="bt-screener")
        feature_version = _prefer_first_sorted(feature_versions_used)
        label_version = _prefer_first_sorted(label_versions_used)
        dataset_version = (
            f"backtest:screener:{window_end.isoformat()}:{model_version}:v1"
        )
        lineage_metadata = build_lineage_metadata(
            dataset="backtest_screener",
            dataset_version=dataset_version,
            as_of_date=window_end,
            dependencies=_build_backtest_dependencies(
                window_end=window_end,
                model_version=model_version,
                feature_versions=feature_versions_used,
                label_versions=label_versions_used,
            ),
            warning_messages=[
                "当前为最小可用回测版本，切片评估已启用，仍未接入成本与滑点模拟。",
            ],
            generated_at=utcnow(),
        )
        response = BacktestRunResponse(
            run_id=run_id,
            dataset_version=dataset_version,
            backtest_type="screener",
            model_version=model_version,
            feature_version=feature_version,
            label_version=label_version,
            window_start=window_start,
            window_end=window_end,
            metrics=metrics,
            summary="选股回测已完成（简化 walk-forward 切片聚合）。",
            warning_messages=[
                "当前为最小可用回测版本，切片评估已启用，仍未接入成本与滑点模拟。",
            ],
            finished_at=lineage_metadata.generated_at,
            lineage_metadata=lineage_metadata,
        )
        self._lineage_service.register_metadata(lineage_metadata)
        return response

    def run_strategy_backtest(
        self,
        request: StrategyBacktestRunRequest,
    ) -> BacktestRunResponse:
        model_version = (
            request.model_version or self._experiment_service.get_default_model_version()
        )
        window_end = request.as_of_end or _default_backtest_as_of_date()
        window_start = window_end - timedelta(days=request.lookback_days)
        slices = _build_walk_forward_slices(window_start=window_start, window_end=window_end)

        returns_5d: list[float] = []
        label_versions_used: set[str] = set()
        feature_versions_used: set[str] = set()
        for slice_date in slices:
            label_dataset = self._label_service.build_label_dataset(
                LabelDatasetBuildRequest(
                    as_of_date=slice_date,
                    max_symbols=500,
                    force_refresh=False,
                )
            )
            label_versions_used.add(label_dataset.summary.label_version)
            if label_dataset.summary.feature_version:
                feature_versions_used.add(label_dataset.summary.feature_version)
            label_records = self._label_service.load_label_records(
                label_dataset.summary.label_version
            )
            for record in label_records:
                if str(record.get("symbol")) != request.symbol:
                    continue
                returns_5d.append(float(record.get("forward_return_5d", 0.0)))

        dataset_version = f"backtest:strategy:{window_end.isoformat()}:{model_version}:v1"
        if not returns_5d:
            lineage_metadata = build_lineage_metadata(
                dataset="backtest_strategy",
                dataset_version=dataset_version,
                as_of_date=window_end,
                symbol=request.symbol,
                dependencies=_build_backtest_dependencies(
                    window_end=window_end,
                    model_version=model_version,
                    feature_versions=feature_versions_used,
                    label_versions=label_versions_used,
                ),
                warning_messages=["strategy_symbol_not_found_in_label_dataset"],
                generated_at=utcnow(),
            )
            response = BacktestRunResponse(
                run_id=_build_run_id(prefix="bt-strategy"),
                dataset_version=dataset_version,
                backtest_type="strategy",
                model_version=model_version,
                feature_version=_prefer_first_sorted(feature_versions_used),
                label_version=_prefer_first_sorted(label_versions_used),
                window_start=window_start,
                window_end=window_end,
                metrics={"top_k_avg_return": 0.0, "win_rate": 0.0, "max_drawdown": 0.0},
                summary="未找到该股票在当前标签窗口的样本，返回空回测结果。",
                warning_messages=["strategy_symbol_not_found_in_label_dataset"],
                finished_at=lineage_metadata.generated_at,
                lineage_metadata=lineage_metadata,
            )
            self._lineage_service.register_metadata(lineage_metadata)
            return response

        metrics = _build_backtest_metrics(returns_5d)
        metrics["slice_count"] = float(len(slices))
        lineage_metadata = build_lineage_metadata(
            dataset="backtest_strategy",
            dataset_version=dataset_version,
            as_of_date=window_end,
            symbol=request.symbol,
            dependencies=_build_backtest_dependencies(
                window_end=window_end,
                model_version=model_version,
                feature_versions=feature_versions_used,
                label_versions=label_versions_used,
            ),
            warning_messages=[
                "当前为最小可用回测版本，未包含交易成本和滑点模拟。",
            ],
            generated_at=utcnow(),
        )
        response = BacktestRunResponse(
            run_id=_build_run_id(prefix="bt-strategy"),
            dataset_version=dataset_version,
            backtest_type="strategy",
            model_version=model_version,
            feature_version=_prefer_first_sorted(feature_versions_used),
            label_version=_prefer_first_sorted(label_versions_used),
            window_start=window_start,
            window_end=window_end,
            metrics=metrics,
            summary="策略回测已完成（简化 walk-forward 切片聚合）。",
            warning_messages=[
                "当前为最小可用回测版本，未包含交易成本和滑点模拟。",
            ],
            finished_at=lineage_metadata.generated_at,
            lineage_metadata=lineage_metadata,
        )
        self._lineage_service.register_metadata(lineage_metadata)
        return response


def _build_backtest_dependencies(
    *,
    window_end: date,
    model_version: str,
    feature_versions: set[str],
    label_versions: set[str],
) -> list:
    dependencies = [
        build_dependency(
            "model_version",
            build_source_ref(
                dataset="model_registry",
                dataset_version=model_version,
                as_of_date=window_end,
                source_mode="baseline",
                freshness_mode="static",
            ),
        )
    ]
    for version in sorted(feature_versions):
        dependencies.append(
            build_dependency(
                "feature_dataset",
                build_source_ref(
                    dataset="feature_dataset",
                    dataset_version=version,
                    as_of_date=window_end,
                    source_mode="mixed",
                    freshness_mode="cache_preferred",
                ),
            )
        )
    for version in sorted(label_versions):
        dependencies.append(
            build_dependency(
                "label_dataset",
                build_source_ref(
                    dataset="label_dataset",
                    dataset_version=version,
                    as_of_date=window_end,
                    source_mode="mixed",
                    freshness_mode="cache_preferred",
                ),
            )
        )
    return dependencies


def _build_label_map(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for record in records:
        symbol = str(record.get("symbol") or "").strip()
        if symbol == "":
            continue
        result[symbol] = {
            "forward_return_5d": float(record.get("forward_return_5d", 0.0)),
            "forward_return_10d": float(record.get("forward_return_10d", 0.0)),
        }
    return result


def _build_backtest_metrics(returns_5d: list[float]) -> dict[str, float]:
    if not returns_5d:
        return {
            "top_k_avg_return": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
        }
    avg_return = sum(returns_5d) / len(returns_5d)
    win_rate = sum(1 for value in returns_5d if value > 0) / len(returns_5d)

    cumulative = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns_5d:
        cumulative *= 1.0 + value
        peak = max(peak, cumulative)
        drawdown = 1.0 - (cumulative / peak)
        max_drawdown = max(max_drawdown, drawdown)

    return {
        "top_k_avg_return": round(avg_return, 6),
        "win_rate": round(win_rate, 6),
        "max_drawdown": round(max_drawdown, 6),
    }


def _build_walk_forward_slices(*, window_start: date, window_end: date) -> list[date]:
    if window_start >= window_end:
        return [window_end]
    total_days = (window_end - window_start).days
    slice_count = max(1, min(8, total_days // 20))
    step = max(1, total_days // slice_count)
    slices: list[date] = []
    for index in range(slice_count + 1):
        candidate = window_start + timedelta(days=index * step)
        if candidate > window_end:
            candidate = window_end
        candidate = _normalize_weekday(candidate)
        if not slices or slices[-1] != candidate:
            slices.append(candidate)
    if slices[-1] != _normalize_weekday(window_end):
        slices.append(_normalize_weekday(window_end))
    return slices


def _normalize_weekday(value: date) -> date:
    candidate = value
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _build_run_id(*, prefix: str) -> str:
    timestamp = utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"


def _default_backtest_as_of_date() -> date:
    return resolve_label_analysis_as_of_date()


def _prefer_first_sorted(values: set[str]) -> str | None:
    if not values:
        return None
    return sorted(values)[0]

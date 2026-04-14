"""Evaluation service."""

from __future__ import annotations

from datetime import timedelta
from threading import Lock
from typing import Any

from app.schemas.backtest import (
    BacktestRunResponse,
    ScreenerBacktestRunRequest,
    StrategyBacktestRunRequest,
)
from app.schemas.dataset import LabelDatasetBuildRequest
from app.schemas.evaluation import (
    EvaluationBacktestReference,
    ModelEvaluationComparison,
    ModelEvaluationResponse,
    ModelVersionRecommendation,
)
from app.services.backtest_service.backtest_service import BacktestService
from app.services.experiment_service.experiment_service import ExperimentService
from app.services.label_service.label_service import LabelService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.utils import (
    build_dependency,
    build_lineage_metadata,
    build_source_ref,
    utcnow,
)


class EvaluationService:
    """Build model evaluation summaries backed by real backtest outputs."""

    def __init__(
        self,
        *,
        experiment_service: ExperimentService,
        label_service: LabelService,
        backtest_service: BacktestService,
        lineage_service: LineageService,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._experiment_service = experiment_service
        self._label_service = label_service
        self._backtest_service = backtest_service
        self._lineage_service = lineage_service
        self._cache_ttl = timedelta(seconds=max(cache_ttl_seconds, 30))
        self._cache: dict[str, tuple[Any, ModelEvaluationResponse]] = {}
        self._cache_lock = Lock()

    def get_model_evaluation(self, model_version: str) -> ModelEvaluationResponse:
        normalized_model_version = (
            model_version.strip() or self._experiment_service.get_default_model_version()
        )
        cached = self._get_cached(normalized_model_version)
        if cached is not None:
            return cached

        as_of = self._label_service.resolve_as_of_date(None)
        window_end = as_of
        window_start = as_of - timedelta(days=120)

        evaluation_warnings: list[str] = []
        backtest_references: list[EvaluationBacktestReference] = []

        screener_backtest = self._backtest_service.run_screener_backtest(
            ScreenerBacktestRunRequest(
                model_version=normalized_model_version,
                lookback_days=120,
                top_k=20,
                as_of_end=window_end,
            )
        )
        backtest_references.append(_build_reference(screener_backtest))
        evaluation_warnings.extend(screener_backtest.warning_messages)

        strategy_backtest = self._run_strategy_backtest_for_reference(
            model_version=normalized_model_version,
            as_of_end=window_end,
            warning_messages=evaluation_warnings,
        )
        if strategy_backtest is not None:
            backtest_references.append(_build_reference(strategy_backtest))
            evaluation_warnings.extend(strategy_backtest.warning_messages)

        metrics = _build_metrics(
            screener_backtest=screener_backtest,
            strategy_backtest=strategy_backtest,
        )
        strengths, risks = _build_strengths_and_risks(
            screener_backtest=screener_backtest,
            strategy_backtest=strategy_backtest,
            metrics=metrics,
        )

        comparison = self._build_comparison_if_needed(
            model_version=normalized_model_version,
            window_end=window_end,
            metrics=metrics,
            warning_messages=evaluation_warnings,
        )
        dataset_version = (
            f"model_evaluation:{window_end.isoformat()}:{normalized_model_version}:v1"
        )
        lineage_metadata = build_lineage_metadata(
            dataset="model_evaluation",
            dataset_version=dataset_version,
            as_of_date=window_end,
            dependencies=_build_evaluation_dependencies(
                window_end=window_end,
                model_version=normalized_model_version,
                screener_backtest=screener_backtest,
                strategy_backtest=strategy_backtest,
            ),
            warning_messages=_dedupe_messages(evaluation_warnings),
            generated_at=utcnow(),
        )

        response = ModelEvaluationResponse(
            model_version=normalized_model_version,
            feature_version=self._experiment_service.get_default_feature_version(),
            label_version=self._label_service.get_default_label_version(),
            evaluated_at=lineage_metadata.generated_at,
            window_start=window_start,
            window_end=window_end,
            metrics=metrics,
            strengths=strengths,
            risks=risks,
            warning_messages=_dedupe_messages(evaluation_warnings),
            backtest_references=backtest_references,
            comparison=comparison,
            recommendation=_build_recommendation(
                model_version=normalized_model_version,
                baseline_model_version=self._experiment_service.get_default_model_version(),
                metrics=metrics,
                comparison=comparison,
            ),
            dataset_version=dataset_version,
            lineage_metadata=lineage_metadata,
        )
        self._save_cached(normalized_model_version, response)
        self._lineage_service.register_metadata(lineage_metadata)
        return response

    def _get_cached(self, model_version: str) -> ModelEvaluationResponse | None:
        now = utcnow()
        with self._cache_lock:
            cached = self._cache.get(model_version)
            if cached is None:
                return None
            cached_at, payload = cached
            if now - cached_at > self._cache_ttl:
                self._cache.pop(model_version, None)
                return None
            return payload

    def _save_cached(self, model_version: str, payload: ModelEvaluationResponse) -> None:
        with self._cache_lock:
            self._cache[model_version] = (utcnow(), payload)

    def _run_strategy_backtest_for_reference(
        self,
        *,
        model_version: str,
        as_of_end,
        warning_messages: list[str],
    ) -> BacktestRunResponse | None:
        try:
            label_dataset = self._label_service.build_label_dataset(
                LabelDatasetBuildRequest(
                    as_of_date=as_of_end,
                    max_symbols=300,
                    force_refresh=False,
                )
            )
            records = self._label_service.load_label_records(
                label_dataset.summary.label_version
            )
            symbol = _pick_first_symbol(records)
            if symbol is None:
                warning_messages.append("evaluation.strategy_reference_symbol_unavailable")
                return None
            return self._backtest_service.run_strategy_backtest(
                StrategyBacktestRunRequest(
                    symbol=symbol,
                    model_version=model_version,
                    lookback_days=120,
                    as_of_end=as_of_end,
                )
            )
        except Exception:
            warning_messages.append("evaluation.strategy_reference_backtest_failed")
            return None

    def _build_comparison_if_needed(
        self,
        *,
        model_version: str,
        window_end,
        metrics: dict[str, float],
        warning_messages: list[str],
    ) -> ModelEvaluationComparison | None:
        baseline_version = self._experiment_service.get_default_model_version()
        if model_version == baseline_version:
            return None
        try:
            baseline_backtest = self._backtest_service.run_screener_backtest(
                ScreenerBacktestRunRequest(
                    model_version=baseline_version,
                    lookback_days=120,
                    top_k=20,
                    as_of_end=window_end,
                )
            )
        except Exception:
            warning_messages.append("evaluation.baseline_comparison_unavailable")
            return None

        baseline_return = _metric(baseline_backtest.metrics, "top_k_avg_return")
        baseline_win_rate = _metric(baseline_backtest.metrics, "win_rate")
        current_return = metrics.get("screener_top_k_avg_return", 0.0)
        current_win_rate = metrics.get("screener_win_rate", 0.0)

        deltas = {
            "top_k_avg_return_delta": round(current_return - baseline_return, 6),
            "win_rate_delta": round(current_win_rate - baseline_win_rate, 6),
        }
        return ModelEvaluationComparison(
            baseline_model_version=baseline_version,
            compared_model_version=model_version,
            metric_deltas=deltas,
            summary="已生成与默认基线模型的同窗对比，可用于版本筛选与回归检查。",
        )


def _build_evaluation_dependencies(
    *,
    window_end,
    model_version: str,
    screener_backtest: BacktestRunResponse,
    strategy_backtest: BacktestRunResponse | None,
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
        ),
        build_dependency(
            "backtest_screener",
            build_source_ref(
                dataset="backtest_screener",
                dataset_version=screener_backtest.dataset_version,
                as_of_date=screener_backtest.window_end,
                source_mode="computed",
                freshness_mode="computed",
            ),
        ),
    ]
    if strategy_backtest is not None:
        dependencies.append(
            build_dependency(
                "backtest_strategy",
                build_source_ref(
                    dataset="backtest_strategy",
                    dataset_version=strategy_backtest.dataset_version,
                    as_of_date=strategy_backtest.window_end,
                    symbol=getattr(strategy_backtest.lineage_metadata, "symbol", None),
                    source_mode="computed",
                    freshness_mode="computed",
                ),
            )
        )
    return dependencies


def _build_reference(result: BacktestRunResponse) -> EvaluationBacktestReference:
    return EvaluationBacktestReference(
        backtest_type=result.backtest_type,
        run_id=result.run_id,
        window_start=result.window_start,
        window_end=result.window_end,
        metrics=result.metrics,
        summary=result.summary,
    )


def _pick_first_symbol(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        symbol = str(record.get("symbol") or "").strip()
        if symbol != "":
            return symbol
    return None


def _metric(metrics: dict[str, float], key: str) -> float:
    value = metrics.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_metrics(
    *,
    screener_backtest: BacktestRunResponse,
    strategy_backtest: BacktestRunResponse | None,
) -> dict[str, float]:
    screener_avg_return = _metric(screener_backtest.metrics, "top_k_avg_return")
    screener_win_rate = _metric(screener_backtest.metrics, "win_rate")
    screener_drawdown = _metric(screener_backtest.metrics, "max_drawdown")
    screener_slice_count = _metric(screener_backtest.metrics, "slice_count")

    strategy_avg_return = 0.0
    strategy_win_rate = 0.0
    strategy_drawdown = 0.0
    if strategy_backtest is not None:
        strategy_avg_return = _metric(strategy_backtest.metrics, "top_k_avg_return")
        strategy_win_rate = _metric(strategy_backtest.metrics, "win_rate")
        strategy_drawdown = _metric(strategy_backtest.metrics, "max_drawdown")

    stability_score = max(0.0, min(1.0, 1.0 - screener_drawdown))
    coverage_score = max(0.0, min(1.0, screener_slice_count / 6.0))
    quality_score = round(
        0.45 * screener_win_rate + 0.35 * stability_score + 0.20 * coverage_score,
        6,
    )

    return {
        "precision_at_20": round(screener_win_rate, 6),
        "hit_rate_5d": round((screener_win_rate + strategy_win_rate) / 2.0, 6),
        "excess_return_10d": round(screener_avg_return, 6),
        "screener_top_k_avg_return": round(screener_avg_return, 6),
        "screener_win_rate": round(screener_win_rate, 6),
        "screener_max_drawdown": round(screener_drawdown, 6),
        "screener_slice_count": round(screener_slice_count, 2),
        "strategy_avg_return": round(strategy_avg_return, 6),
        "strategy_win_rate": round(strategy_win_rate, 6),
        "strategy_max_drawdown": round(strategy_drawdown, 6),
        "stability_score": round(stability_score, 6),
        "quality_score": quality_score,
    }


def _build_strengths_and_risks(
    *,
    screener_backtest: BacktestRunResponse,
    strategy_backtest: BacktestRunResponse | None,
    metrics: dict[str, float],
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []

    if metrics.get("screener_win_rate", 0.0) >= 0.55:
        strengths.append("选股回测胜率超过 55%，候选排序具备基础稳定性。")
    if metrics.get("screener_top_k_avg_return", 0.0) > 0.0:
        strengths.append("Top-K 回测平均收益为正，版本可继续纳入候选观察。")
    if metrics.get("screener_slice_count", 0.0) >= 4:
        strengths.append("walk-forward 切片覆盖较充分，短窗偶然性相对可控。")
    if strategy_backtest is not None and metrics.get("strategy_win_rate", 0.0) >= 0.5:
        strengths.append("策略参考回测胜率不低于 50%，可用于单票辅助确认。")

    if metrics.get("screener_slice_count", 0.0) < 3:
        risks.append("有效切片数量偏少，版本稳定性需要继续观察。")
    if metrics.get("screener_max_drawdown", 0.0) > 0.2:
        risks.append("回测最大回撤偏大，仓位与止损约束需要收紧。")
    if strategy_backtest is None:
        risks.append("未生成策略参考回测，当前评估主要依赖截面结果。")

    if not strengths:
        strengths.append("版本评估链路已打通，可持续积累对比样本。")
    if not risks:
        risks.append("当前为最小可用评估版本，尚未纳入交易成本与滑点。")

    if "walk-forward" not in screener_backtest.summary.lower():
        strengths.append("回测结果已包含切片聚合摘要，可用于版本回溯。")
    return strengths[:4], risks[:4]


def _dedupe_messages(messages: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for message in messages:
        text = str(message).strip()
        if text == "" or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _build_recommendation(
    *,
    model_version: str,
    baseline_model_version: str,
    metrics: dict[str, float],
    comparison: ModelEvaluationComparison | None,
) -> ModelVersionRecommendation:
    quality_score = metrics.get("quality_score", 0.0)
    recommendation = "observe"
    reason = "当前版本已完成最小评估链路，建议继续观察更多切片样本。"
    if model_version == baseline_model_version:
        recommendation = "keep_baseline"
        reason = "当前为默认基线模型，继续作为稳定参考版本。"
    elif comparison is not None and comparison.metric_deltas.get("top_k_avg_return_delta", 0.0) > 0:
        recommendation = "promote_candidate"
        reason = "相对基线收益表现更优，可作为升级候选。"
    elif quality_score < 0.45:
        recommendation = "keep_baseline"
        reason = "当前版本质量分偏低，不建议替代默认基线。"

    return ModelVersionRecommendation(
        recommendation=recommendation,
        recommended_model_version=model_version
        if recommendation != "keep_baseline"
        else baseline_model_version,
        reason=reason,
        supporting_metrics={
            "quality_score": round(quality_score, 6),
            "screener_win_rate": round(metrics.get("screener_win_rate", 0.0), 6),
            "screener_top_k_avg_return": round(
                metrics.get("screener_top_k_avg_return", 0.0),
                6,
            ),
        },
        guardrails=[
            "仅在样本切片覆盖继续提高后再考虑正式升级。",
            "当前评估仍未纳入交易成本与滑点。",
        ],
    )

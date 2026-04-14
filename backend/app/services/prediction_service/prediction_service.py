"""Prediction service."""

from __future__ import annotations

from datetime import date
from hashlib import sha1
import logging
from typing import Any, Optional

from app.schemas.dataset import FeatureDatasetBuildRequest
from app.schemas.prediction import (
    CrossSectionPredictionCandidate,
    CrossSectionPredictionRunRequest,
    CrossSectionPredictionRunResponse,
    PredictionSnapshotResponse,
)
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.normalize import normalize_symbol
from app.services.dataset_service.dataset_service import DatasetService
from app.services.experiment_service.experiment_service import ExperimentService
from app.services.label_service.label_service import LabelService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.utils import (
    build_dependency,
    build_lineage_metadata,
    build_source_ref,
    utcnow,
)

logger = logging.getLogger(__name__)


class PredictionService:
    """Serve single-symbol and cross-section baseline predictions."""

    def __init__(
        self,
        *,
        dataset_service: DatasetService,
        label_service: LabelService,
        experiment_service: ExperimentService,
        lineage_service: LineageService,
    ) -> None:
        self._dataset_service = dataset_service
        self._label_service = label_service
        self._experiment_service = experiment_service
        self._lineage_service = lineage_service

    def get_symbol_prediction(
        self,
        *,
        symbol: str,
        as_of_date: date | None = None,
        model_version: str | None = None,
        build_feature_dataset: bool = True,
    ) -> PredictionSnapshotResponse:
        normalized_symbol = normalize_symbol(symbol)
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        resolved_model_version = (
            model_version or self._experiment_service.get_default_model_version()
        )
        label_version = self._label_service.get_default_label_version()
        warning_messages: list[str] = []

        feature_version: str
        if build_feature_dataset:
            feature_version = self._ensure_feature_dataset(
                as_of_date=resolved_as_of_date,
                max_symbols=500,
            )
        else:
            try:
                feature_version = self.get_feature_dataset_version()
                warning_messages.append("预测快照使用已有特征数据集，未触发在线重建。")
            except Exception as exc:  # pragma: no cover
                logger.debug(
                    "prediction.snapshot.feature_version_unavailable symbol=%s error=%s",
                    normalized_symbol,
                    exc,
                )
                feature_version = self._experiment_service.get_default_feature_version()
                warning_messages.append("特征数据集暂不可用，已使用轻量回退预测。")
                return self._build_fallback_snapshot(
                    symbol=normalized_symbol,
                    as_of_date=resolved_as_of_date,
                    model_version=resolved_model_version,
                    feature_version=feature_version,
                    label_version=label_version,
                    warning_messages=warning_messages,
                )

        try:
            feature_record = self._find_feature_record(
                feature_version=feature_version,
                symbol=normalized_symbol,
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "prediction.snapshot.feature_record_unavailable symbol=%s feature_version=%s error=%s",
                normalized_symbol,
                feature_version,
                exc,
            )
            feature_record = None
            warning_messages.append("特征数据记录不可用，已使用轻量回退预测。")

        if feature_record is None:
            warning_messages.append("特征集中未命中该股票，已使用哈希回退分数（联调用）。")
            return self._build_fallback_snapshot(
                symbol=normalized_symbol,
                as_of_date=resolved_as_of_date,
                model_version=resolved_model_version,
                feature_version=feature_version,
                label_version=label_version,
                warning_messages=warning_messages,
            )

        score = _score_from_feature_record(feature_record)
        confidence = _build_model_confidence(score)
        expected_excess_return = round((score - 50) / 400.0, 4)
        dataset_version = _build_prediction_dataset_version(
            symbol=normalized_symbol,
            as_of_date=resolved_as_of_date,
            model_version=resolved_model_version,
        )
        lineage_metadata = build_lineage_metadata(
            dataset="prediction_snapshot",
            dataset_version=dataset_version,
            as_of_date=resolved_as_of_date,
            symbol=normalized_symbol,
            dependencies=_build_prediction_dependencies(
                as_of_date=resolved_as_of_date,
                feature_version=feature_version,
                label_version=label_version,
                model_version=resolved_model_version,
            ),
            warning_messages=warning_messages,
            generated_at=utcnow(),
        )
        response = PredictionSnapshotResponse(
            symbol=normalized_symbol,
            as_of_date=resolved_as_of_date,
            dataset_version=dataset_version,
            model_version=resolved_model_version,
            feature_version=feature_version,
            label_version=label_version,
            predictive_score=score,
            upside_probability=round(score / 100.0, 4),
            expected_excess_return=expected_excess_return,
            model_confidence=confidence,
            runtime_mode="baseline",
            warning_messages=[
                *warning_messages,
                "当前为 baseline 预测版本，结果用于研究辅助与流程联调。",
            ],
            generated_at=lineage_metadata.generated_at,
            lineage_metadata=lineage_metadata,
        )
        self._lineage_service.register_metadata(lineage_metadata)
        return response

    def run_cross_section_prediction(
        self,
        request: CrossSectionPredictionRunRequest,
    ) -> CrossSectionPredictionRunResponse:
        model_version = (
            request.model_version or self._experiment_service.get_default_model_version()
        )
        as_of_date = resolve_daily_analysis_as_of_date(request.as_of_date)
        feature_version = self._ensure_feature_dataset(
            as_of_date=as_of_date,
            max_symbols=request.max_symbols,
            force_refresh=request.force_refresh,
        )
        records = self._dataset_service.load_feature_records(feature_version)

        scored_items: list[tuple[str, int]] = []
        for record in records:
            symbol = str(record.get("symbol") or "").strip()
            if symbol == "":
                continue
            scored_items.append((symbol, _score_from_feature_record(record)))

        ordered = sorted(scored_items, key=lambda item: item[1], reverse=True)[: request.top_k]
        candidates = [
            CrossSectionPredictionCandidate(
                symbol=symbol,
                rank=index + 1,
                predictive_score=score,
                model_confidence=_build_model_confidence(score),
                expected_excess_return=round((score - 50) / 400.0, 4),
            )
            for index, (symbol, score) in enumerate(ordered)
        ]
        run_id = _build_run_id(prefix="pred")
        dataset_version = _build_cross_section_dataset_version(
            as_of_date=as_of_date,
            model_version=model_version,
        )
        lineage_metadata = build_lineage_metadata(
            dataset="cross_section_prediction",
            dataset_version=dataset_version,
            as_of_date=as_of_date,
            dependencies=_build_prediction_dependencies(
                as_of_date=as_of_date,
                feature_version=feature_version,
                label_version=self._label_service.get_default_label_version(),
                model_version=model_version,
            ),
            warning_messages=[
                "当前为 baseline 预测版本，候选排序用于研究辅助与联调。",
            ],
            generated_at=utcnow(),
        )
        response = CrossSectionPredictionRunResponse(
            run_id=run_id,
            status="completed",
            as_of_date=as_of_date,
            dataset_version=dataset_version,
            model_version=model_version,
            feature_version=feature_version,
            label_version=self._label_service.get_default_label_version(),
            total_symbols=len(records),
            candidates=candidates,
            warning_messages=[
                "当前为 baseline 预测版本，候选排序用于研究辅助与联调。",
            ],
            generated_at=lineage_metadata.generated_at,
            lineage_metadata=lineage_metadata,
        )
        self._lineage_service.register_metadata(lineage_metadata)
        return response

    def get_feature_dataset_version(self) -> str:
        dataset = self._dataset_service.get_feature_dataset("latest")
        return dataset.summary.dataset_version

    def _ensure_feature_dataset(
        self,
        *,
        as_of_date: date,
        max_symbols: int,
        force_refresh: bool = False,
    ) -> str:
        response = self._dataset_service.build_feature_dataset(
            FeatureDatasetBuildRequest(
                as_of_date=as_of_date,
                max_symbols=max_symbols,
                force_refresh=force_refresh,
            )
        )
        return response.summary.dataset_version

    def _find_feature_record(
        self,
        *,
        feature_version: str,
        symbol: str,
    ) -> Optional[dict[str, Any]]:
        records = self._dataset_service.load_feature_records(feature_version)
        for record in records:
            if str(record.get("symbol") or "").strip().upper() == symbol.upper():
                return record
        return None

    def _build_fallback_snapshot(
        self,
        *,
        symbol: str,
        as_of_date: date,
        model_version: str,
        feature_version: str,
        label_version: str,
        warning_messages: list[str],
    ) -> PredictionSnapshotResponse:
        score = _build_hash_fallback_score(
            symbol=symbol,
            as_of_date=as_of_date,
            model_version=model_version,
        )
        confidence = _build_model_confidence(score)
        dataset_version = _build_prediction_dataset_version(
            symbol=symbol,
            as_of_date=as_of_date,
            model_version=model_version,
        )
        lineage_metadata = build_lineage_metadata(
            dataset="prediction_snapshot",
            dataset_version=dataset_version,
            as_of_date=as_of_date,
            symbol=symbol,
            dependencies=_build_prediction_dependencies(
                as_of_date=as_of_date,
                feature_version=feature_version,
                label_version=label_version,
                model_version=model_version,
            ),
            warning_messages=warning_messages,
            generated_at=utcnow(),
        )
        response = PredictionSnapshotResponse(
            symbol=symbol,
            as_of_date=as_of_date,
            dataset_version=dataset_version,
            model_version=model_version,
            feature_version=feature_version,
            label_version=label_version,
            predictive_score=score,
            upside_probability=round(score / 100.0, 4),
            expected_excess_return=round((score - 50) / 300.0, 4),
            model_confidence=confidence,
            runtime_mode="baseline",
            warning_messages=warning_messages,
            generated_at=lineage_metadata.generated_at,
            lineage_metadata=lineage_metadata,
        )
        self._lineage_service.register_metadata(lineage_metadata)
        return response


def _build_prediction_dependencies(
    *,
    as_of_date: date,
    feature_version: str,
    label_version: str,
    model_version: str,
) -> list[LineageDependency]:
    return [
        build_dependency(
            "feature_dataset",
            build_source_ref(
                dataset="feature_dataset",
                dataset_version=feature_version,
                as_of_date=as_of_date,
                symbol=None,
                source_mode="mixed",
                freshness_mode="cache_preferred",
            ),
        ),
        build_dependency(
            "label_dataset",
            build_source_ref(
                dataset="label_dataset",
                dataset_version=label_version,
                as_of_date=as_of_date,
                symbol=None,
                source_mode="mixed",
                freshness_mode="cache_preferred",
            ),
        ),
        build_dependency(
            "model_version",
            build_source_ref(
                dataset="model_registry",
                dataset_version=model_version,
                as_of_date=as_of_date,
                symbol=None,
                source_mode="baseline",
                freshness_mode="static",
            ),
        ),
    ]


def _build_prediction_dataset_version(
    *,
    symbol: str,
    as_of_date: date,
    model_version: str,
) -> str:
    return f"prediction_snapshot:{as_of_date.isoformat()}:{symbol}:{model_version}:v1"


def _build_cross_section_dataset_version(
    *,
    as_of_date: date,
    model_version: str,
) -> str:
    return f"cross_section_prediction:{as_of_date.isoformat()}:global:{model_version}:v1"


def _score_from_feature_record(record: dict[str, Any]) -> int:
    trend_score = _safe_float(record.get("trend_score"), fallback=50.0)
    alpha_score = _safe_float(record.get("alpha_score"), fallback=50.0)
    risk_score = _safe_float(record.get("risk_score"), fallback=50.0)
    close_return_20d = _safe_float(record.get("close_return_20d"), fallback=0.0)
    volume_ratio_20d = _safe_float(record.get("volume_ratio_20d"), fallback=1.0)

    score = (
        trend_score * 0.35
        + alpha_score * 0.40
        + (100.0 - risk_score) * 0.20
        + max(-20.0, min(20.0, close_return_20d)) * 0.3
        + max(-20.0, min(20.0, (volume_ratio_20d - 1.0) * 20.0)) * 0.05
    )
    return int(max(0, min(100, round(score))))


def _safe_float(value: Any, *, fallback: float) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _build_hash_fallback_score(*, symbol: str, as_of_date: date, model_version: str) -> int:
    seed = f"{symbol}-{as_of_date.isoformat()}-{model_version}"
    digest = sha1(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return 20 + (value % 61)


def _build_model_confidence(score: int) -> float:
    if score >= 80:
        return 0.86
    if score >= 70:
        return 0.78
    if score >= 60:
        return 0.70
    if score >= 50:
        return 0.62
    if score >= 40:
        return 0.54
    return 0.46


def _build_run_id(*, prefix: str) -> str:
    timestamp = utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"

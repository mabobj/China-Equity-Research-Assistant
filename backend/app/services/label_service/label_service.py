"""Label dataset service."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime
import json
import logging
from pathlib import Path
from typing import Any

from app.schemas.dataset import (
    FeatureDatasetBuildRequest,
    LabelDatasetBuildRequest,
    LabelDatasetResponse,
    LabelDatasetSummary,
)
from app.schemas.lineage import LineageDependency, LineageSourceRef
from app.services.data_products.base import build_dataset_version
from app.services.data_products.freshness import resolve_label_analysis_as_of_date
from app.services.data_service.market_data_service import MarketDataService
from app.services.dataset_service.dataset_service import DatasetService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.utils import (
    build_dependency,
    build_lineage_metadata,
    build_source_ref,
    utcnow,
)

logger = logging.getLogger(__name__)


class LabelService:
    """Build and reuse forward-return label datasets."""

    def __init__(
        self,
        *,
        default_label_version: str,
        root_dir: Path,
        market_data_service: MarketDataService,
        dataset_service: DatasetService,
        daily_bars_daily,
        lineage_service: LineageService,
    ) -> None:
        self._default_label_version = default_label_version
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._labels_dir = self._root_dir / "labels"
        self._labels_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._root_dir / "label_manifest.json"
        self._market_data_service = market_data_service
        self._dataset_service = dataset_service
        self._daily_bars_daily = daily_bars_daily
        self._lineage_service = lineage_service

    def get_default_label_version(self) -> str:
        return self._default_label_version

    def get_label_window(self) -> tuple[int, int]:
        return (5, 10)

    def resolve_as_of_date(self, as_of_date: date | None) -> date:
        return resolve_label_analysis_as_of_date(as_of_date)

    def build_label_dataset(
        self,
        request: LabelDatasetBuildRequest,
    ) -> LabelDatasetResponse:
        as_of_date = self.resolve_as_of_date(request.as_of_date)
        label_version = f"labels-{as_of_date.isoformat()}-v1"
        label_path = self._labels_dir / f"{label_version}.json"

        manifest = self._load_manifest()
        existing = manifest.get("datasets", {}).get(label_version)
        if existing is not None and label_path.exists() and not request.force_refresh:
            return _build_label_response(label_version, existing)

        self._dataset_service.build_feature_dataset(
            FeatureDatasetBuildRequest(
                as_of_date=as_of_date,
                max_symbols=request.max_symbols,
                force_refresh=request.force_refresh,
            )
        )
        feature_version = f"features-{as_of_date.isoformat()}-v1"
        feature_records = self._dataset_service.load_feature_records(feature_version)

        records: list[dict[str, Any]] = []
        warning_messages: list[str] = []
        generated_at = utcnow()
        daily_bars_source = _build_global_daily_bars_source(as_of_date)
        feature_source = build_source_ref(
            dataset="feature_dataset",
            dataset_version=feature_version,
            as_of_date=as_of_date,
            symbol=None,
            source_mode="mixed",
            freshness_mode="cache_preferred",
        )
        dependencies = [
            build_dependency("feature_dataset", feature_source),
            build_dependency("daily_bars_daily", daily_bars_source),
        ]

        session_scope = getattr(self._market_data_service, "session_scope", None)
        scope = session_scope() if callable(session_scope) else nullcontext()
        with scope:
            for record in feature_records:
                symbol = str(record.get("symbol") or "").strip()
                if symbol == "":
                    continue
                try:
                    bars_result = self._daily_bars_daily.get(
                        symbol,
                        as_of_date=as_of_date,
                        force_refresh=False,
                        provider_priority=("mootdx", "baostock", "akshare"),
                    )
                except Exception:
                    warning_messages.append(f"{symbol}:daily_bars_unavailable_for_labels")
                    continue

                self._lineage_service.register_data_product(bars_result)
                bars = [bar for bar in bars_result.payload.bars if bar.close is not None]
                bars.sort(key=lambda item: item.trade_date)
                index = _find_trade_date_index(bars, as_of_date)
                if index is None or (index + 10) >= len(bars):
                    warning_messages.append(f"{symbol}:insufficient_forward_window")
                    continue

                base_close = float(bars[index].close or 0.0)
                if base_close <= 0:
                    warning_messages.append(f"{symbol}:invalid_base_close")
                    continue

                forward_close_5d = float(bars[index + 5].close or 0.0)
                forward_close_10d = float(bars[index + 10].close or 0.0)
                if forward_close_5d <= 0 or forward_close_10d <= 0:
                    warning_messages.append(f"{symbol}:invalid_forward_close")
                    continue

                forward_return_5d = (forward_close_5d / base_close) - 1.0
                forward_return_10d = (forward_close_10d / base_close) - 1.0
                records.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of_date.isoformat(),
                        "forward_return_5d": round(forward_return_5d, 6),
                        "forward_return_10d": round(forward_return_10d, 6),
                        "hit_label_5d": int(forward_return_5d > 0),
                    }
                )

        lineage_metadata = build_lineage_metadata(
            dataset="label_dataset",
            dataset_version=label_version,
            as_of_date=as_of_date,
            dependencies=dependencies,
            warning_messages=warning_messages[:200],
            generated_at=generated_at,
        )
        payload = {
            "label_version": label_version,
            "as_of_date": as_of_date.isoformat(),
            "symbol_count": len(records),
            "window_5d": 5,
            "window_10d": 10,
            "source_mode": "mixed",
            "description": "基于日线未来收益构建的最小标签集",
            "warning_messages": warning_messages[:200],
            "feature_version": feature_version,
            "generated_at": generated_at.isoformat(),
            "schema_version": 1,
            "dependencies": [item.model_dump(mode="json") for item in dependencies],
            "records": records,
        }
        with label_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        manifest.setdefault("datasets", {})[label_version] = {
            "as_of_date": payload["as_of_date"],
            "symbol_count": payload["symbol_count"],
            "window_5d": payload["window_5d"],
            "window_10d": payload["window_10d"],
            "source_mode": payload["source_mode"],
            "description": payload["description"],
            "warning_messages": payload["warning_messages"],
            "feature_version": payload["feature_version"],
            "generated_at": payload["generated_at"],
            "schema_version": payload["schema_version"],
            "dependencies": payload["dependencies"],
        }
        manifest["latest_version"] = label_version
        self._save_manifest(manifest)
        self._lineage_service.register_metadata(lineage_metadata)

        logger.info(
            "prediction.labels.build_done label_version=%s symbol_count=%s warning_count=%s",
            label_version,
            len(records),
            len(warning_messages),
        )
        return _build_label_response(label_version, manifest["datasets"][label_version])

    def get_label_dataset(self, label_version: str) -> LabelDatasetResponse:
        manifest = self._load_manifest()
        resolved_version = (
            str(manifest.get("latest_version", self._default_label_version))
            if label_version == "latest"
            else label_version
        )
        dataset = manifest.get("datasets", {}).get(resolved_version)
        if dataset is None:
            raise ValueError(f"label dataset version 不存在：{label_version}")
        return _build_label_response(resolved_version, dataset)

    def load_label_records(self, label_version: str = "latest") -> list[dict[str, Any]]:
        manifest = self._load_manifest()
        resolved_version = (
            str(manifest.get("latest_version", self._default_label_version))
            if label_version == "latest"
            else label_version
        )
        label_path = self._labels_dir / f"{resolved_version}.json"
        if not label_path.exists():
            raise ValueError(f"label dataset records 不存在：{resolved_version}")
        with label_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        records = payload.get("records", [])
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict)]

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_path.exists():
            with self._manifest_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        manifest = self._build_default_manifest()
        self._save_manifest(manifest)
        return manifest

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        with self._manifest_path.open("w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)

    def _build_default_manifest(self) -> dict[str, Any]:
        today = self.resolve_as_of_date(None)
        generated_at = utcnow()
        feature_source = build_source_ref(
            dataset="feature_dataset",
            dataset_version=f"features-{today.isoformat()}-v1",
            as_of_date=today,
            symbol=None,
            source_mode="mixed",
            freshness_mode="cache_preferred",
        )
        daily_bars_source = _build_global_daily_bars_source(today)
        return {
            "latest_version": self._default_label_version,
            "datasets": {
                self._default_label_version: {
                    "as_of_date": today.isoformat(),
                    "symbol_count": 0,
                    "window_5d": 5,
                    "window_10d": 10,
                    "source_mode": "local",
                    "description": "预测标签骨架初始版本（未构建真实标签）",
                    "warning_messages": ["尚未构建真实标签数据集。"],
                    "feature_version": None,
                    "generated_at": generated_at.isoformat(),
                    "schema_version": 1,
                    "dependencies": [
                        build_dependency("feature_dataset", feature_source).model_dump(
                            mode="json"
                        ),
                        build_dependency(
                            "daily_bars_daily",
                            daily_bars_source,
                        ).model_dump(mode="json"),
                    ],
                }
            },
        }


def _find_trade_date_index(bars: list[Any], target_date: date) -> int | None:
    for index, bar in enumerate(bars):
        if bar.trade_date == target_date:
            return index
    return None


def _build_label_response(
    label_version: str,
    dataset: dict[str, Any],
) -> LabelDatasetResponse:
    dependencies = _load_dependencies(dataset)
    as_of_date = date.fromisoformat(str(dataset["as_of_date"]))
    return LabelDatasetResponse(
        summary=LabelDatasetSummary(
            label_version=label_version,
            as_of_date=as_of_date,
            symbol_count=int(dataset.get("symbol_count", 0)),
            window_5d=int(dataset.get("window_5d", 5)),
            window_10d=int(dataset.get("window_10d", 10)),
            source_mode=str(dataset.get("source_mode", "local")),
            description=_optional_text(dataset.get("description")),
            feature_version=_optional_text(dataset.get("feature_version")),
            lineage_metadata=build_lineage_metadata(
                dataset="label_dataset",
                dataset_version=label_version,
                as_of_date=as_of_date,
                dependencies=dependencies,
                warning_messages=list(dataset.get("warning_messages", [])),
                generated_at=datetime.fromisoformat(
                    str(dataset.get("generated_at", utcnow().isoformat()))
                ),
            ),
        ),
        warning_messages=list(dataset.get("warning_messages", [])),
    )


def _load_dependencies(dataset: dict[str, Any]) -> list[LineageDependency]:
    result: list[LineageDependency] = []
    for item in dataset.get("dependencies", []):
        if not isinstance(item, dict):
            continue
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, dict):
            continue
        result.append(
            build_dependency(
                str(item.get("role", "upstream")),
                LineageSourceRef.model_validate(source_ref),
            )
        )
    return result


def _build_global_daily_bars_source(as_of_date: date) -> LineageSourceRef:
    return build_source_ref(
        dataset="daily_bars_daily",
        dataset_version=build_dataset_version("daily_bars_daily", as_of_date, "global"),
        as_of_date=as_of_date,
        symbol=None,
        source_mode="local_preferred",
        freshness_mode="cache_preferred",
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

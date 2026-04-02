"""特征数据集服务（最小真实链路版）。"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date
import json
import logging
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Optional

from app.schemas.dataset import (
    FeatureDatasetBuildRequest,
    FeatureDatasetResponse,
    FeatureDatasetSummary,
)
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_service.market_data_service import MarketDataService

logger = logging.getLogger(__name__)


class DatasetService:
    """管理特征数据集版本，支持按交易日构建与复用。"""

    def __init__(
        self,
        *,
        root_dir: Path,
        default_feature_version: str,
        market_data_service: MarketDataService,
    ) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._features_dir = self._root_dir / "features"
        self._features_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._root_dir / "feature_manifest.json"
        self._default_feature_version = default_feature_version
        self._market_data_service = market_data_service
        self._default_feature_names = [
            "close_return_5d",
            "close_return_20d",
            "volume_ratio_5d",
            "volume_ratio_20d",
            "trend_score",
            "alpha_score",
            "risk_score",
        ]

    def get_feature_dataset(self, dataset_version: str) -> FeatureDatasetResponse:
        manifest = self._load_manifest()
        resolved_version = dataset_version
        if dataset_version == "latest":
            resolved_version = str(
                manifest.get("latest_version", self._default_feature_version)
            )

        dataset = manifest.get("datasets", {}).get(resolved_version)
        if dataset is None:
            raise ValueError(f"feature dataset version 不存在：{dataset_version}")

        return _build_feature_response(
            resolved_version,
            dataset,
            self._default_feature_names,
        )

    def build_feature_dataset(
        self,
        request: FeatureDatasetBuildRequest,
    ) -> FeatureDatasetResponse:
        as_of_date = request.as_of_date or resolve_last_closed_trading_day()
        dataset_version = f"features-{as_of_date.isoformat()}-v1"
        feature_path = self._features_dir / f"{dataset_version}.json"

        manifest = self._load_manifest()
        existing = manifest.get("datasets", {}).get(dataset_version)
        if existing is not None and feature_path.exists() and not request.force_refresh:
            logger.debug(
                "prediction.features.cache_hit dataset_version=%s symbol_count=%s",
                dataset_version,
                existing.get("symbol_count", 0),
            )
            manifest["latest_version"] = dataset_version
            self._save_manifest(manifest)
            return _build_feature_response(
                dataset_version,
                existing,
                self._default_feature_names,
            )

        universe = self._market_data_service.get_stock_universe().items[
            : request.max_symbols
        ]
        records: list[dict[str, Any]] = []
        warning_messages: list[str] = []

        # 批量构建特征时强制本地优先，避免单次评估触发大量远端补数。
        session_scope = getattr(self._market_data_service, "session_scope", None)
        scope = session_scope() if callable(session_scope) else nullcontext()
        with scope:
            for item in universe:
                try:
                    bars_response = self._get_daily_bars_for_dataset(
                        symbol=item.symbol,
                        end_date=as_of_date.isoformat(),
                    )
                except Exception as exc:  # pragma: no cover - 防御性分支
                    warning_messages.append(f"{item.symbol}:daily_bars_unavailable")
                    logger.debug(
                        "prediction.features.symbol_skip symbol=%s reason=%s",
                        item.symbol,
                        exc.__class__.__name__,
                    )
                    continue

                valid_bars = [
                    bar
                    for bar in bars_response.bars
                    if (
                        bar.close is not None
                        and bar.volume is not None
                        and bar.trade_date <= as_of_date
                    )
                ]
                valid_bars.sort(key=lambda bar: bar.trade_date)
                if len(valid_bars) < 25:
                    warning_messages.append(f"{item.symbol}:insufficient_history")
                    continue

                closes = [float(bar.close) for bar in valid_bars]
                volumes = [float(bar.volume or 0.0) for bar in valid_bars]
                record = _build_feature_record(
                    symbol=item.symbol,
                    as_of_date=as_of_date,
                    closes=closes,
                    volumes=volumes,
                )
                records.append(record)

        payload = {
            "dataset_version": dataset_version,
            "as_of_date": as_of_date.isoformat(),
            "symbol_count": len(records),
            "feature_names": self._default_feature_names,
            "label_version": f"labels-{as_of_date.isoformat()}-v1",
            "source_mode": "mixed",
            "description": "point-in-time 特征数据集（最小可用版）",
            "warning_messages": warning_messages[:200],
            "records": records,
        }

        with feature_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        manifest.setdefault("datasets", {})[dataset_version] = {
            "as_of_date": payload["as_of_date"],
            "symbol_count": payload["symbol_count"],
            "feature_names": payload["feature_names"],
            "label_version": payload["label_version"],
            "source_mode": payload["source_mode"],
            "description": payload["description"],
            "warning_messages": payload["warning_messages"],
        }
        manifest["latest_version"] = dataset_version
        self._save_manifest(manifest)

        logger.info(
            "prediction.features.build_done dataset_version=%s symbol_count=%s warning_count=%s",
            dataset_version,
            len(records),
            len(warning_messages),
        )
        return _build_feature_response(
            dataset_version,
            manifest["datasets"][dataset_version],
            self._default_feature_names,
        )

    def load_feature_records(self, dataset_version: str = "latest") -> list[dict[str, Any]]:
        manifest = self._load_manifest()
        resolved_version = (
            str(manifest.get("latest_version", self._default_feature_version))
            if dataset_version == "latest"
            else dataset_version
        )
        feature_path = self._features_dir / f"{resolved_version}.json"
        if not feature_path.exists():
            raise ValueError(f"feature dataset records 不存在：{resolved_version}")
        with feature_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        records = payload.get("records", [])
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict)]

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_path.exists():
            with self._manifest_path.open("r", encoding="utf-8") as file:
                return json.load(file)

        default_manifest = self._build_default_manifest()
        self._save_manifest(default_manifest)
        return default_manifest

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        with self._manifest_path.open("w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)

    def _build_default_manifest(self) -> dict[str, Any]:
        today = date.today().isoformat()
        return {
            "latest_version": self._default_feature_version,
            "datasets": {
                self._default_feature_version: {
                    "as_of_date": today,
                    "symbol_count": 0,
                    "feature_names": self._default_feature_names,
                    "label_version": None,
                    "source_mode": "local",
                    "description": "预测底座骨架初始版本（未构建真实特征）",
                    "warning_messages": ["尚未构建真实特征数据集。"],
                }
            },
        }

    def _get_daily_bars_for_dataset(self, *, symbol: str, end_date: str):
        try:
            return self._market_data_service.get_daily_bars(
                symbol=symbol,
                end_date=end_date,
                allow_remote_sync=False,
                provider_names=("mootdx", "baostock", "akshare"),
            )
        except TypeError:
            try:
                return self._market_data_service.get_daily_bars(
                    symbol=symbol,
                    end_date=end_date,
                    provider_names=("mootdx", "baostock", "akshare"),
                )
            except TypeError:
                return self._market_data_service.get_daily_bars(
                    symbol=symbol,
                    end_date=end_date,
                )


def _build_feature_response(
    dataset_version: str,
    dataset: dict[str, Any],
    default_feature_names: list[str],
) -> FeatureDatasetResponse:
    feature_names = list(dataset.get("feature_names", default_feature_names))
    summary = FeatureDatasetSummary(
        dataset_version=dataset_version,
        as_of_date=date.fromisoformat(str(dataset["as_of_date"])),
        symbol_count=int(dataset.get("symbol_count", 0)),
        feature_count=len(feature_names),
        label_version=_optional_text(dataset.get("label_version")),
        source_mode=str(dataset.get("source_mode", "local")),
        description=_optional_text(dataset.get("description")),
    )
    return FeatureDatasetResponse(
        summary=summary,
        feature_names=feature_names,
        warning_messages=list(dataset.get("warning_messages", [])),
    )


def _build_feature_record(
    *,
    symbol: str,
    as_of_date: date,
    closes: list[float],
    volumes: list[float],
) -> dict[str, Any]:
    close_return_5d = _pct_change(closes[-6], closes[-1])
    close_return_20d = _pct_change(closes[-21], closes[-1])
    volume_ma_5d = mean(volumes[-5:]) if len(volumes) >= 5 else None
    volume_ma_20d = mean(volumes[-20:]) if len(volumes) >= 20 else None
    volume_ratio_5d = _safe_ratio(volumes[-1], volume_ma_5d)
    volume_ratio_20d = _safe_ratio(volumes[-1], volume_ma_20d)

    ma20 = mean(closes[-20:])
    trend_score = 50
    trend_score += 20 if closes[-1] >= ma20 else -20
    trend_score += 15 if closes[-1] >= closes[-6] else -15
    trend_score += 15 if closes[-1] >= closes[-21] else -15
    trend_score = max(0, min(100, trend_score))

    alpha_score = max(
        0,
        min(
            100,
            int(50 + close_return_20d * 2 + close_return_5d * 1.2),
        ),
    )

    daily_returns = _daily_returns(closes[-21:])
    volatility = pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    risk_score = max(0, min(100, int(volatility * 1200)))

    return {
        "symbol": symbol,
        "as_of_date": as_of_date.isoformat(),
        "close_return_5d": round(close_return_5d, 6),
        "close_return_20d": round(close_return_20d, 6),
        "volume_ratio_5d": _round_optional(volume_ratio_5d),
        "volume_ratio_20d": _round_optional(volume_ratio_20d),
        "trend_score": trend_score,
        "alpha_score": alpha_score,
        "risk_score": risk_score,
        "latest_close": round(closes[-1], 4),
    }


def _pct_change(base_value: float, current_value: float) -> float:
    if base_value == 0:
        return 0.0
    return (current_value / base_value - 1.0) * 100.0


def _safe_ratio(value: float, baseline: Optional[float]) -> Optional[float]:
    if baseline is None or baseline == 0:
        return None
    return value / baseline


def _daily_returns(closes: list[float]) -> list[float]:
    if len(closes) <= 1:
        return []
    returns: list[float] = []
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        current = closes[index]
        if previous == 0:
            continue
        returns.append((current / previous) - 1.0)
    return returns


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _round_optional(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 6)

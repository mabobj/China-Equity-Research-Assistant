"""预测/回测/评估 API 骨架契约测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_backtest_service,
    get_dataset_service,
    get_evaluation_service,
    get_label_service,
    get_prediction_service,
)
from app.main import app
from app.schemas.backtest import BacktestRunResponse
from app.schemas.dataset import (
    FeatureDatasetResponse,
    FeatureDatasetSummary,
    LabelDatasetResponse,
    LabelDatasetSummary,
)
from app.schemas.evaluation import ModelEvaluationResponse
from app.schemas.prediction import (
    CrossSectionPredictionCandidate,
    CrossSectionPredictionRunResponse,
    PredictionSnapshotResponse,
)

client = TestClient(app)


class _StubPredictionService:
    def get_symbol_prediction(
        self,
        *,
        symbol: str,
        as_of_date: date | None = None,
        model_version: str | None = None,
    ) -> PredictionSnapshotResponse:
        return PredictionSnapshotResponse(
            symbol=symbol,
            as_of_date=as_of_date or date(2026, 4, 1),
            model_version=model_version or "baseline-rule-v1",
            feature_version="features-v0-baseline",
            label_version="labels-v0-forward-return",
            predictive_score=66,
            upside_probability=0.66,
            expected_excess_return=0.0533,
            model_confidence=0.7,
            runtime_mode="baseline",
            warning_messages=["stub"],
            generated_at=datetime.now(timezone.utc),
        )

    def run_cross_section_prediction(self, request) -> CrossSectionPredictionRunResponse:
        return CrossSectionPredictionRunResponse(
            run_id="pred-20260401010101",
            status="completed",
            as_of_date=request.as_of_date or date(2026, 4, 1),
            model_version=request.model_version or "baseline-rule-v1",
            feature_version="features-v0-baseline",
            label_version="labels-v0-forward-return",
            total_symbols=request.max_symbols,
            candidates=[
                CrossSectionPredictionCandidate(
                    symbol="600519.SH",
                    rank=1,
                    predictive_score=88,
                    model_confidence=0.86,
                    expected_excess_return=0.12,
                )
            ],
            warning_messages=[],
            generated_at=datetime.now(timezone.utc),
        )


class _StubBacktestService:
    def run_screener_backtest(self, request) -> BacktestRunResponse:
        return BacktestRunResponse(
            run_id="bt-screener-20260401",
            backtest_type="screener",
            model_version=request.model_version or "baseline-rule-v1",
            window_start=date(2025, 12, 1),
            window_end=date(2026, 4, 1),
            metrics={"top_k_avg_return": 0.08},
            summary="stub",
            warning_messages=[],
            finished_at=datetime.now(timezone.utc),
        )

    def run_strategy_backtest(self, request) -> BacktestRunResponse:
        return BacktestRunResponse(
            run_id="bt-strategy-20260401",
            backtest_type="strategy",
            model_version=request.model_version or "baseline-rule-v1",
            window_start=date(2025, 12, 1),
            window_end=date(2026, 4, 1),
            metrics={"top_k_avg_return": 0.05},
            summary="stub",
            warning_messages=[],
            finished_at=datetime.now(timezone.utc),
        )


class _StubEvaluationService:
    def get_model_evaluation(self, model_version: str) -> ModelEvaluationResponse:
        return ModelEvaluationResponse(
            model_version=model_version,
            feature_version="features-v0-baseline",
            label_version="labels-v0-forward-return",
            evaluated_at=datetime.now(timezone.utc),
            window_start=date(2025, 12, 1),
            window_end=date(2026, 4, 1),
            metrics={"precision_at_20": 0.62},
            strengths=["stub"],
            risks=["stub"],
            warning_messages=[],
            recommendation={
                "recommendation": "keep_baseline",
                "recommended_model_version": "baseline-rule-v1",
                "reason": "stub",
                "supporting_metrics": {"quality_score": 0.62},
                "guardrails": ["stub"],
            },
        )


class _StubDatasetService:
    def get_feature_dataset(self, dataset_version: str) -> FeatureDatasetResponse:
        if dataset_version == "missing":
            raise ValueError("not found")
        return FeatureDatasetResponse(
            summary=FeatureDatasetSummary(
                dataset_version="features-v0-baseline",
                as_of_date=date(2026, 4, 1),
                symbol_count=5000,
                feature_count=7,
                label_version="labels-v0-forward-return",
                source_mode="local",
                description="stub",
            ),
            feature_names=["alpha_score"],
            warning_messages=[],
        )

    def build_feature_dataset(self, request) -> FeatureDatasetResponse:
        return self.get_feature_dataset("latest")


class _StubLabelService:
    def get_label_dataset(self, label_version: str) -> LabelDatasetResponse:
        return LabelDatasetResponse(
            summary=LabelDatasetSummary(
                label_version="labels-v0-forward-return",
                as_of_date=date(2026, 4, 1),
                symbol_count=5000,
                window_5d=5,
                window_10d=10,
                source_mode="local",
                description="stub",
            ),
            warning_messages=[],
        )

    def build_label_dataset(self, request) -> LabelDatasetResponse:
        return self.get_label_dataset("latest")


def test_prediction_and_backtest_routes_return_structured_payload() -> None:
    app.dependency_overrides[get_prediction_service] = lambda: _StubPredictionService()
    app.dependency_overrides[get_backtest_service] = lambda: _StubBacktestService()
    app.dependency_overrides[get_evaluation_service] = lambda: _StubEvaluationService()
    app.dependency_overrides[get_dataset_service] = lambda: _StubDatasetService()
    app.dependency_overrides[get_label_service] = lambda: _StubLabelService()

    prediction_response = client.get("/predictions/600519.SH")
    assert prediction_response.status_code == 200
    assert prediction_response.json()["symbol"] == "600519.SH"
    assert prediction_response.json()["runtime_mode"] == "baseline"

    cross_section_response = client.post(
        "/predictions/cross-section/run",
        json={"max_symbols": 100, "top_k": 10},
    )
    assert cross_section_response.status_code == 200
    assert cross_section_response.json()["candidates"][0]["symbol"] == "600519.SH"

    screener_backtest_response = client.post(
        "/backtests/screener/run",
        json={"lookback_days": 180, "top_k": 20},
    )
    assert screener_backtest_response.status_code == 200
    assert screener_backtest_response.json()["backtest_type"] == "screener"

    strategy_backtest_response = client.post(
        "/backtests/strategy/run",
        json={"symbol": "600519.SH", "lookback_days": 120},
    )
    assert strategy_backtest_response.status_code == 200
    assert strategy_backtest_response.json()["backtest_type"] == "strategy"

    evaluation_response = client.get("/evaluations/models/baseline-rule-v1")
    assert evaluation_response.status_code == 200
    assert evaluation_response.json()["model_version"] == "baseline-rule-v1"
    assert "backtest_references" in evaluation_response.json()
    assert evaluation_response.json()["recommendation"]["recommended_model_version"] == "baseline-rule-v1"

    dataset_response = client.get("/datasets/features/latest")
    assert dataset_response.status_code == 200
    assert dataset_response.json()["summary"]["dataset_version"] == "features-v0-baseline"

    dataset_build_response = client.post(
        "/datasets/features/build",
        json={"max_symbols": 100},
    )
    assert dataset_build_response.status_code == 200

    labels_response = client.get("/datasets/labels/latest")
    assert labels_response.status_code == 200
    assert labels_response.json()["summary"]["label_version"] == "labels-v0-forward-return"

    labels_build_response = client.post(
        "/datasets/labels/build",
        json={"max_symbols": 100},
    )
    assert labels_build_response.status_code == 200

    missing_dataset_response = client.get("/datasets/features/missing")
    assert missing_dataset_response.status_code == 404

    app.dependency_overrides.clear()

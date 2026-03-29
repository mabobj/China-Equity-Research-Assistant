"""选股服务包。"""

from __future__ import annotations

from typing import Any

__all__ = ["ScreenerPipeline", "DeepScreenerPipeline"]


def __getattr__(name: str) -> Any:
    if name == "ScreenerPipeline":
        from app.services.screener_service.pipeline import ScreenerPipeline

        return ScreenerPipeline
    if name == "DeepScreenerPipeline":
        from app.services.screener_service.deep_pipeline import DeepScreenerPipeline

        return DeepScreenerPipeline
    raise AttributeError(name)

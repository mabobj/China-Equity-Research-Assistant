"""波动状态评估。"""

from typing import Dict, Optional


def evaluate_volatility_state(latest_row: Dict[str, Optional[float]]) -> str:
    """基于 ATR 和布林带宽度给出波动状态。"""
    close = latest_row.get("close")
    atr14 = latest_row.get("atr14")
    bollinger_upper = latest_row.get("bollinger_upper")
    bollinger_lower = latest_row.get("bollinger_lower")

    if close is None or close <= 0:
        return "normal"

    atr_ratio = (atr14 / close) if atr14 is not None else None
    band_ratio = None
    if bollinger_upper is not None and bollinger_lower is not None:
        band_ratio = (bollinger_upper - bollinger_lower) / close

    ratios = [ratio for ratio in (atr_ratio, band_ratio) if ratio is not None]
    if not ratios:
        return "normal"

    ratio = max(ratios)
    if ratio >= 0.12:
        return "high"
    if ratio <= 0.04:
        return "low"
    return "normal"

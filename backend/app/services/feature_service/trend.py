"""趋势状态与趋势评分。"""

from typing import Dict, Optional

from app.services.feature_service.indicators import clamp_score


def evaluate_trend(latest_row: Dict[str, Optional[float]]) -> tuple[str, int]:
    """基于最新技术特征给出趋势状态与分数。"""
    score = 50.0

    close = latest_row.get("close")
    ma20 = latest_row.get("ma20")
    ma60 = latest_row.get("ma60")
    ma120 = latest_row.get("ma120")
    macd = latest_row.get("macd")
    macd_signal = latest_row.get("macd_signal")
    macd_histogram = latest_row.get("macd_histogram")
    rsi14 = latest_row.get("rsi14")

    if close is not None and ma20 is not None:
        score += 12.0 if close >= ma20 else -12.0
    if close is not None and ma60 is not None:
        score += 10.0 if close >= ma60 else -10.0
    if close is not None and ma120 is not None:
        score += 8.0 if close >= ma120 else -8.0

    if ma20 is not None and ma60 is not None:
        score += 10.0 if ma20 >= ma60 else -10.0
    if ma60 is not None and ma120 is not None:
        score += 8.0 if ma60 >= ma120 else -8.0

    if macd is not None and macd_signal is not None:
        score += 8.0 if macd >= macd_signal else -8.0
    if macd_histogram is not None:
        score += 6.0 if macd_histogram >= 0.0 else -6.0

    if rsi14 is not None:
        if 50.0 <= rsi14 <= 70.0:
            score += 8.0
        elif rsi14 < 35.0:
            score -= 8.0
        elif rsi14 > 80.0:
            score -= 4.0

    final_score = clamp_score(score)
    if final_score >= 65:
        return "up", final_score
    if final_score <= 35:
        return "down", final_score
    return "neutral", final_score

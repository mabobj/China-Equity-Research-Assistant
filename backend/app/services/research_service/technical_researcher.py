"""基于技术快照的规则化研究器。"""

from app.schemas.research import TechnicalResearchResult
from app.schemas.technical import TechnicalSnapshot


class TechnicalResearcher:
    """负责将技术快照转换为结构化技术研究结果。"""

    def analyze(self, snapshot: TechnicalSnapshot) -> TechnicalResearchResult:
        """分析技术快照并给出第一版技术评分。"""
        score = float(snapshot.trend_score)
        key_reasons: list[str] = []
        risks: list[str] = []
        triggers: list[str] = []
        invalidations: list[str] = []

        if snapshot.trend_state == "up":
            score += 8
            key_reasons.append(
                "趋势状态为上行，趋势分数 {score}。".format(
                    score=snapshot.trend_score,
                ),
            )
        elif snapshot.trend_state == "down":
            score -= 15
            risks.append("趋势状态为下行，短期技术结构偏弱。")
        else:
            key_reasons.append("趋势状态中性，仍需等待更明确方向。")

        if snapshot.macd.histogram is not None:
            if snapshot.macd.histogram > 0:
                score += 6
                key_reasons.append("MACD 柱体为正，动能仍偏多。")
            elif snapshot.macd.histogram < 0:
                score -= 6
                risks.append("MACD 柱体为负，动能尚未明显修复。")

        if snapshot.rsi14 is not None:
            if 45 <= snapshot.rsi14 <= 70:
                score += 5
            elif snapshot.rsi14 > 75:
                score -= 8
                risks.append("RSI14 处于偏高区间，短线有回撤压力。")
            elif snapshot.rsi14 < 30:
                score -= 4
                risks.append("RSI14 偏低，价格仍可能延续弱势。")

        ma20 = snapshot.moving_averages.ma20
        if ma20 is not None:
            if snapshot.latest_close >= ma20:
                score += 5
                key_reasons.append("最新收盘价站上 MA20，中期结构尚可。")
            else:
                score -= 8
                risks.append("最新收盘价位于 MA20 下方，中期结构偏弱。")
                invalidations.append("若价格持续无法重新站上 MA20，技术修复预期下降。")

        if snapshot.support_level is not None:
            if snapshot.latest_close < snapshot.support_level:
                score -= 12
                risks.append("价格已跌破支撑位，防守结构受损。")
                invalidations.append(
                    "若价格继续运行在支撑位 {price:.2f} 下方，技术观点失效。".format(
                        price=snapshot.support_level,
                    ),
                )
            else:
                distance_to_support = (
                    snapshot.latest_close - snapshot.support_level
                ) / snapshot.support_level
                if distance_to_support <= 0.05:
                    triggers.append("若价格在支撑位附近企稳，短线情绪可能改善。")

        if snapshot.resistance_level is not None:
            if snapshot.latest_close >= snapshot.resistance_level * 0.97:
                risks.append("价格已接近压力位，向上突破前波动可能放大。")
                triggers.append(
                    "若有效突破压力位 {price:.2f}，趋势延续概率会提升。".format(
                        price=snapshot.resistance_level,
                    ),
                )

        if snapshot.volatility_state == "low":
            score += 3
        elif snapshot.volatility_state == "high":
            score -= 8
            risks.append("波动水平偏高，仓位管理需要更谨慎。")
            invalidations.append("若高波动伴随价格转弱，技术风险会进一步抬升。")

        final_score = _clamp_score(score)
        summary = _build_summary(snapshot=snapshot, score=final_score)

        return TechnicalResearchResult(
            score=final_score,
            summary=summary,
            key_reasons=_limit_items(key_reasons, fallback="技术面暂无明显优势。"),
            risks=_limit_items(risks, fallback="技术面暂无突出风险，但仍需跟踪价格演变。"),
            triggers=_limit_items(
                triggers,
                fallback="关注价格能否延续当前趋势并确认关键位。",
            ),
            invalidations=_limit_items(
                invalidations,
                fallback="若趋势分数明显走弱，本轮技术判断需要下修。",
            ),
        )


def _build_summary(snapshot: TechnicalSnapshot, score: int) -> str:
    """生成简洁的技术面摘要。"""
    if snapshot.trend_state == "up":
        return "技术面偏强，当前评分 {score}，趋势与动能对价格形成支撑。".format(
            score=score,
        )
    if snapshot.trend_state == "down":
        return "技术面偏弱，当前评分 {score}，趋势与波动状态仍需修复。".format(
            score=score,
        )
    return "技术面中性，当前评分 {score}，需要等待更明确的方向确认。".format(
        score=score,
    )


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))


def _limit_items(items: list[str], fallback: str) -> list[str]:
    """去重并限制最多返回 3 条。"""
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    if not deduped:
        deduped.append(fallback)
    return deduped[:3]

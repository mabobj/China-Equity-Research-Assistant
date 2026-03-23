"""基于财务摘要的规则化研究器。"""

from app.schemas.research import FundamentalResearchResult
from app.schemas.research_inputs import FinancialSummary


class FundamentalResearcher:
    """负责将财务摘要转换为结构化基本面研究结果。"""

    def analyze(self, summary: FinancialSummary) -> FundamentalResearchResult:
        """分析财务摘要并给出第一版基本面评分。"""
        key_reasons: list[str] = []
        risks: list[str] = []
        triggers: list[str] = []
        invalidations: list[str] = []

        core_fields = [
            summary.revenue,
            summary.revenue_yoy,
            summary.net_profit,
            summary.net_profit_yoy,
            summary.roe,
            summary.gross_margin,
            summary.debt_ratio,
            summary.eps,
            summary.bps,
        ]
        available_count = len([value for value in core_fields if value is not None])
        score = 30.0 + (available_count / len(core_fields)) * 20.0

        if summary.net_profit is not None:
            if summary.net_profit > 0:
                score += 12
                key_reasons.append("归母净利润为正，盈利基础仍在。")
            else:
                score -= 18
                risks.append("归母净利润为负，盈利能力偏弱。")
                invalidations.append("若净利润无法回正，基本面假设需要明显下修。")

        if summary.net_profit_yoy is not None:
            if summary.net_profit_yoy >= 15:
                score += 12
                key_reasons.append("归母净利润同比增长较快，盈利改善明显。")
            elif summary.net_profit_yoy > 0:
                score += 6
            else:
                score -= 12
                risks.append("归母净利润同比转弱，盈利弹性不足。")

        if summary.revenue_yoy is not None:
            if summary.revenue_yoy >= 10:
                score += 8
                key_reasons.append("收入同比保持增长，主营扩张仍有支撑。")
            elif summary.revenue_yoy > 0:
                score += 4
            else:
                score -= 8
                risks.append("收入同比下滑，需求或交付节奏需要关注。")

        if summary.roe is not None:
            if summary.roe >= 15:
                score += 10
                key_reasons.append("ROE 处于较健康区间，资本回报率较好。")
            elif summary.roe >= 8:
                score += 4
            elif summary.roe < 0:
                score -= 12
                risks.append("ROE 为负，股东回报能力较弱。")

        if summary.gross_margin is not None:
            if summary.gross_margin >= 25:
                score += 6
            elif summary.gross_margin < 10:
                score -= 6
                risks.append("毛利率偏低，盈利缓冲不足。")

        if summary.debt_ratio is not None:
            if summary.debt_ratio <= 50:
                score += 6
            elif summary.debt_ratio >= 70:
                score -= 10
                risks.append("资产负债率偏高，财务杠杆压力较大。")
                invalidations.append("若杠杆继续抬升，风险容忍度需要下降。")

        if summary.eps is not None:
            if summary.eps > 0:
                score += 4
            else:
                score -= 8
                risks.append("每股收益为负，盈利质量仍待修复。")

        if available_count <= 4:
            risks.append("可用财务字段较少，当前基本面判断置信度有限。")
        else:
            triggers.append("若后续报告继续验证收入和利润增长，基本面评分可继续上修。")

        if summary.report_period is not None:
            triggers.append(
                "关注下一次财报能否延续 {period} 的财务表现。".format(
                    period=summary.report_period.isoformat(),
                ),
            )

        final_score = _clamp_score(score)
        report_summary = _build_summary(summary=summary, score=final_score)

        return FundamentalResearchResult(
            score=final_score,
            summary=report_summary,
            key_reasons=_limit_items(key_reasons, fallback="财务指标整体中性，暂无明显亮点。"),
            risks=_limit_items(risks, fallback="基本面暂无突出风险，但仍需持续跟踪财报。"),
            triggers=_limit_items(
                triggers,
                fallback="后续关注收入、利润和资本回报率是否继续改善。",
            ),
            invalidations=_limit_items(
                invalidations,
                fallback="若核心盈利指标持续走弱，基本面判断需要调整。",
            ),
        )


def _build_summary(summary: FinancialSummary, score: int) -> str:
    """生成简洁的基本面摘要。"""
    period_text = summary.report_period.isoformat() if summary.report_period is not None else "最近一期"
    if score >= 70:
        return "{period} 财务表现偏稳健，当前基本面评分 {score}。".format(
            period=period_text,
            score=score,
        )
    if score >= 45:
        return "{period} 财务表现中性，当前基本面评分 {score}。".format(
            period=period_text,
            score=score,
        )
    return "{period} 财务表现偏弱，当前基本面评分 {score}。".format(
        period=period_text,
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

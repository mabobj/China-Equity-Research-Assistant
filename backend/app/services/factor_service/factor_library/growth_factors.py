"""成长因子。"""

from __future__ import annotations

from app.schemas.research_inputs import FinancialSummary
from app.services.factor_service.base import FactorGroupResult, FactorMetric
from app.services.factor_service.preprocess import average_scores, linear_score, percent_like


def build_growth_group(financial_summary: FinancialSummary | None) -> FactorGroupResult:
    """构建成长因子组。"""
    revenue_yoy = None if financial_summary is None else percent_like(financial_summary.revenue_yoy)
    net_profit_yoy = None if financial_summary is None else percent_like(financial_summary.net_profit_yoy)

    metrics = [
        FactorMetric(
            factor_name="revenue_yoy",
            raw_value=revenue_yoy,
            normalized_score=linear_score(revenue_yoy, -30.0, 60.0),
            positive_signal="收入同比保持增长，基本面扩张仍在持续",
            negative_signal="收入同比偏弱，增长动能不足",
        ),
        FactorMetric(
            factor_name="net_profit_yoy",
            raw_value=net_profit_yoy,
            normalized_score=linear_score(net_profit_yoy, -50.0, 80.0),
            positive_signal="净利润同比表现较强，盈利增长质量较好",
            negative_signal="净利润同比偏弱，盈利增长承压",
        ),
        FactorMetric(
            factor_name="revenue_acceleration",
            raw_value=None,
            normalized_score=None,
            note="当前版本预留收入加速度，暂未接入上一期财务摘要。",
        ),
        FactorMetric(
            factor_name="net_profit_acceleration",
            raw_value=None,
            normalized_score=None,
            note="当前版本预留净利润加速度，暂未接入上一期财务摘要。",
        ),
    ]

    return FactorGroupResult(
        group_name="growth",
        metrics=metrics,
        score=average_scores(metric.normalized_score for metric in metrics),
    )

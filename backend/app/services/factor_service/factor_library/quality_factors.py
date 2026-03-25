"""质量因子。"""

from __future__ import annotations

from app.schemas.research_inputs import FinancialSummary
from app.services.factor_service.base import FactorGroupResult, FactorMetric
from app.services.factor_service.preprocess import average_scores, linear_score, percent_like, safe_ratio


def build_quality_group(financial_summary: FinancialSummary | None) -> FactorGroupResult:
    """构建质量因子组。"""
    if financial_summary is None:
        return FactorGroupResult(
            group_name="quality",
            metrics=[
                FactorMetric(
                    factor_name="financial_data_completeness",
                    raw_value=0.0,
                    normalized_score=0.0,
                    negative_signal="财务摘要缺失，质量维度暂时无法有效判断",
                ),
            ],
            score=0.0,
        )

    roe = percent_like(financial_summary.roe)
    net_margin = None
    if financial_summary.net_profit is not None and financial_summary.revenue not in (None, 0):
        net_margin = safe_ratio(financial_summary.net_profit, financial_summary.revenue)
        if net_margin is not None:
            net_margin = net_margin * 100.0
    debt_ratio = percent_like(financial_summary.debt_ratio)
    eps = financial_summary.eps
    completeness_fields = [
        financial_summary.roe,
        net_margin,
        financial_summary.debt_ratio,
        financial_summary.eps,
        financial_summary.revenue_yoy,
        financial_summary.net_profit_yoy,
    ]
    completeness_ratio = sum(value is not None for value in completeness_fields) / len(completeness_fields)
    completeness_score = completeness_ratio * 100.0

    metrics = [
        FactorMetric(
            factor_name="roe",
            raw_value=roe,
            normalized_score=linear_score(roe, 0.0, 25.0),
            positive_signal="ROE 高于常见阈值，资本回报质量较好",
            negative_signal="ROE 偏弱，盈利质量支撑不足",
        ),
        FactorMetric(
            factor_name="net_margin",
            raw_value=net_margin,
            normalized_score=linear_score(net_margin, 0.0, 25.0),
            positive_signal="净利率处于较健康区间，主营盈利能力尚可",
            negative_signal="净利率偏低，利润转化能力一般",
        ),
        FactorMetric(
            factor_name="debt_ratio",
            raw_value=debt_ratio,
            normalized_score=linear_score(debt_ratio, 20.0, 80.0, reverse=True),
            positive_signal="负债率可控，财务杠杆压力较轻",
            negative_signal="负债率偏高，财务杠杆压力需要关注",
        ),
        FactorMetric(
            factor_name="eps",
            raw_value=eps,
            normalized_score=linear_score(eps, 0.0, 3.0),
            positive_signal="EPS 为正且水平尚可，单股盈利具备一定支撑",
            negative_signal="EPS 偏弱，单股盈利支撑不足",
        ),
        FactorMetric(
            factor_name="financial_data_completeness",
            raw_value=completeness_score,
            normalized_score=completeness_score,
            positive_signal="财务字段完整度较好，质量判断更可靠",
            negative_signal="财务字段缺失较多，质量判断可靠性有限",
        ),
    ]

    return FactorGroupResult(
        group_name="quality",
        metrics=metrics,
        score=average_scores(metric.normalized_score for metric in metrics),
    )

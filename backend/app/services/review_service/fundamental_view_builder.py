"""构建基本面画像。"""

from __future__ import annotations

from app.schemas.research_inputs import FinancialSummary
from app.schemas.review import FundamentalView


def build_fundamental_view(
    financial_summary: FinancialSummary | None,
) -> FundamentalView:
    """基于财务摘要生成基本面画像。"""
    if financial_summary is None:
        return FundamentalView(
            quality_read=None,
            growth_read=None,
            leverage_read=None,
            data_completeness_note="当前缺少财务摘要，基本面判断仅能保持中性保守。",
            key_financial_flags=["财务摘要缺失"],
        )

    return FundamentalView(
        quality_read=_build_quality_read(financial_summary),
        growth_read=_build_growth_read(financial_summary),
        leverage_read=_build_leverage_read(financial_summary),
        data_completeness_note=_build_completeness_note(financial_summary),
        key_financial_flags=_build_financial_flags(financial_summary),
    )


def _build_quality_read(financial_summary: FinancialSummary) -> str:
    if financial_summary.roe is None and financial_summary.eps is None:
        return "盈利质量字段有限，当前只能维持中性判断。"
    if (financial_summary.roe or 0) >= 15 and (financial_summary.eps or 0) > 0:
        return "ROE 与 EPS 组合表现尚可，盈利质量对估值和趋势具备一定支撑。"
    if (financial_summary.roe or 0) >= 8 and (financial_summary.eps or 0) > 0:
        return "盈利质量处于可接受区间，但还不足以单独形成强基本面结论。"
    return "盈利质量偏弱，当前更需要依赖趋势与事件催化来支撑关注度。"


def _build_growth_read(financial_summary: FinancialSummary) -> str:
    revenue_yoy = financial_summary.revenue_yoy
    profit_yoy = financial_summary.net_profit_yoy
    if revenue_yoy is None and profit_yoy is None:
        return "增长字段不完整，暂不对增长斜率做强结论。"
    if (revenue_yoy or 0) >= 15 and (profit_yoy or 0) >= 15:
        return "收入与利润同比都保持较好增长，成长性读数偏正面。"
    if (revenue_yoy or 0) >= 0 and (profit_yoy or 0) >= 0:
        return "收入与利润仍在正增长区间，但成长弹性暂不突出。"
    return "收入或利润同比走弱，成长性对当前研判形成拖累。"


def _build_leverage_read(financial_summary: FinancialSummary) -> str:
    debt_ratio = financial_summary.debt_ratio
    if debt_ratio is None:
        return "杠杆字段缺失，财务安全边界需要保守看待。"
    if debt_ratio <= 35:
        return "负债率处于较可控区间，财务杠杆压力相对温和。"
    if debt_ratio <= 60:
        return "负债率处于中性区间，财务结构尚可但需持续跟踪。"
    return "负债率偏高，杠杆压力会放大经营波动对估值的影响。"


def _build_completeness_note(financial_summary: FinancialSummary) -> str:
    fields = [
        financial_summary.revenue,
        financial_summary.revenue_yoy,
        financial_summary.net_profit,
        financial_summary.net_profit_yoy,
        financial_summary.roe,
        financial_summary.gross_margin,
        financial_summary.debt_ratio,
        financial_summary.eps,
        financial_summary.bps,
    ]
    available_count = sum(value is not None for value in fields)
    if available_count == len(fields):
        return "关键财务字段完整，基本面判断的可读性较好。"
    if available_count >= 6:
        return "关键财务字段大体可用，但部分维度仍需保守解读。"
    return "财务字段缺失较多，基本面结论的置信度需要下调。"


def _build_financial_flags(financial_summary: FinancialSummary) -> list[str]:
    flags: list[str] = []
    if financial_summary.net_profit_yoy is not None and financial_summary.net_profit_yoy < 0:
        flags.append("净利润同比为负")
    if financial_summary.revenue_yoy is not None and financial_summary.revenue_yoy < 0:
        flags.append("收入同比为负")
    if financial_summary.debt_ratio is not None and financial_summary.debt_ratio > 60:
        flags.append("负债率偏高")
    if financial_summary.roe is not None and financial_summary.roe < 8:
        flags.append("ROE 偏弱")
    if financial_summary.eps is not None and financial_summary.eps <= 0:
        flags.append("EPS 偏弱")
    if not flags:
        flags.append("当前未出现明显财务红旗")
    return flags[:3]

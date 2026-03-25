"""角色化分析员测试。"""

from datetime import datetime

from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import FundamentalView, TechnicalView
from app.services.debate_service.fundamental_analyst import (
    build_fundamental_analyst_view,
)
from app.services.debate_service.technical_analyst import build_technical_analyst_view


def test_technical_analyst_marks_supportive_when_trend_and_trigger_align() -> None:
    analyst_view = build_technical_analyst_view(
        TechnicalView(
            trend_state="up",
            trigger_state="near_support",
            key_levels=["支撑位 116.00", "压力位 122.00"],
            tactical_read="价格靠近日线支撑区。",
            invalidation_hint="若跌破支撑位则判断下修。",
        ),
        TriggerSnapshot(
            symbol="600519.SH",
            as_of_datetime=datetime(2024, 3, 25, 10, 0, 0),
            daily_trend_state="up",
            daily_support_level=116.0,
            daily_resistance_level=122.0,
            latest_intraday_price=118.0,
            distance_to_support_pct=1.5,
            distance_to_resistance_pct=3.0,
            trigger_state="near_support",
            trigger_note="价格靠近支撑位。",
        ),
    )

    assert analyst_view.role == "technical_analyst"
    assert analyst_view.action_bias == "supportive"
    assert analyst_view.positive_points


def test_fundamental_analyst_collects_financial_risks() -> None:
    analyst_view = build_fundamental_analyst_view(
        FundamentalView(
            quality_read="盈利质量偏弱，当前更需要依赖趋势与事件催化来支撑关注度。",
            growth_read="收入或利润同比走弱，成长性对当前研判形成拖累。",
            leverage_read="负债率偏高，杠杆压力会放大经营波动对估值的影响。",
            data_completeness_note="财务字段缺失较多，基本面结论的置信度需要下调。",
            key_financial_flags=["净利润同比为负", "负债率偏高"],
        )
    )

    assert analyst_view.role == "fundamental_analyst"
    assert analyst_view.action_bias in {"cautious", "negative"}
    assert any(point.title == "财务风险" for point in analyst_view.caution_points)

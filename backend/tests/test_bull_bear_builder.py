"""多空观点 builder 测试。"""

from app.schemas.review import (
    EventView,
    FactorProfileView,
    FundamentalView,
    SentimentView,
    StrategySummary,
    TechnicalView,
)
from app.schemas.strategy import PriceRange
from app.services.review_service.bull_bear_builder import build_bull_bear_case


def test_bull_bear_builder_returns_structured_disagreements() -> None:
    result = build_bull_bear_case(
        factor_profile=FactorProfileView(
            strongest_factor_groups=["趋势", "事件"],
            weakest_factor_groups=["质量"],
            alpha_score=72,
            trigger_score=64,
            risk_score=62,
            concise_summary="alpha 分 72；触发分 64；风险分 62",
        ),
        technical_view=TechnicalView(
            trend_state="up",
            trigger_state="neutral",
            key_levels=["支撑位 116.00", "压力位 122.00"],
            tactical_read="日线趋势仍偏强，但盘中尚未给出明确回踩或突破触发。",
            invalidation_hint="若跌破支撑位则判断下修。",
        ),
        fundamental_view=FundamentalView(
            quality_read="盈利质量处于可接受区间，但还不足以单独形成强基本面结论。",
            growth_read="收入与利润仍在正增长区间，但成长弹性暂不突出。",
            leverage_read="负债率处于中性区间。",
            data_completeness_note="关键财务字段大体可用。",
            key_financial_flags=["当前未出现明显财务红旗"],
        ),
        event_view=EventView(
            recent_catalysts=["关于回购股份方案的公告"],
            recent_risks=["关于减持计划的公告"],
            event_temperature="warm",
            concise_summary="近 30 日公告活跃。",
        ),
        sentiment_view=SentimentView(
            sentiment_bias="cautious",
            crowding_hint="当前拥挤度信号中性。",
            momentum_context="20 日与 60 日相对强弱均偏正。",
            concise_summary="情绪偏谨慎。",
        ),
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=116.0, high=118.0),
            stop_loss_price=114.0,
            take_profit_range=PriceRange(low=123.0, high=126.0),
            review_timeframe="daily_close_review",
            concise_summary="策略层仍以观察为主。",
        ),
    )

    assert result.bull_case.stance == "bull"
    assert result.bear_case.stance == "bear"
    assert result.bull_case.reasons
    assert result.bear_case.reasons
    assert result.key_disagreements

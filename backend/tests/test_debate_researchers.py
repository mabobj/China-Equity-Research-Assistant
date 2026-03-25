"""多空研究员测试。"""

from app.schemas.debate import AnalystView, AnalystViewsBundle, DebatePoint
from app.services.debate_service.bear_researcher import build_bear_case
from app.services.debate_service.bull_researcher import build_bull_case


def test_bull_and_bear_researchers_extract_structured_points() -> None:
    bundle = AnalystViewsBundle(
        technical=AnalystView(
            role="technical_analyst",
            summary="技术偏强。",
            action_bias="supportive",
            positive_points=[DebatePoint(title="趋势", detail="趋势偏强")],
            caution_points=[DebatePoint(title="失效条件", detail="跌破支撑位")],
            key_levels=["支撑位 116.00"],
        ),
        fundamental=AnalystView(
            role="fundamental_analyst",
            summary="基本面中性。",
            action_bias="neutral",
            positive_points=[DebatePoint(title="质量判断", detail="盈利质量可接受")],
            caution_points=[],
            key_levels=[],
        ),
        event=AnalystView(
            role="event_analyst",
            summary="事件偏暖。",
            action_bias="supportive",
            positive_points=[DebatePoint(title="近期催化", detail="回购公告")],
            caution_points=[DebatePoint(title="近期风险", detail="减持公告")],
            key_levels=[],
        ),
        sentiment=AnalystView(
            role="sentiment_analyst",
            summary="情绪中性。",
            action_bias="cautious",
            positive_points=[DebatePoint(title="动量环境", detail="20 日收益率偏正")],
            caution_points=[DebatePoint(title="拥挤度提示", detail="接近阶段高位")],
            key_levels=[],
        ),
    )

    bull_case = build_bull_case(bundle)
    bear_case = build_bear_case(bundle)

    assert bull_case.reasons
    assert bear_case.reasons
    assert bull_case.reasons[0].title in {"趋势", "质量判断", "近期催化", "动量环境"}
    assert bear_case.reasons[0].title in {"失效条件", "近期风险", "拥挤度提示"}

"""单票研究 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_research_manager
from app.main import app
from app.schemas.research import ResearchReport


class StubResearchManager:
    """用于研究 API 测试的 manager 桩。"""

    def get_research_report(self, symbol: str) -> ResearchReport:
        return ResearchReport(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            technical_score=78,
            fundamental_score=82,
            event_score=64,
            risk_score=32,
            overall_score=76,
            action="BUY",
            confidence=73,
            thesis="贵州茅台当前综合判断为 BUY，技术面与基本面均偏稳健，公告层面暂未出现明显负面扰动。",
            key_reasons=[
                "趋势状态为上行，趋势分数较高。",
                "归母净利润与收入同比保持增长。",
                "近期公告中存在回购与分红类正面信号。",
            ],
            risks=[
                "价格接近压力位，短线可能震荡。",
                "需持续跟踪后续财报兑现情况。",
            ],
            triggers=[
                "若有效突破压力位，趋势延续概率会提升。",
                "若下一期财报继续验证增长，基本面评分可上修。",
            ],
            invalidations=[
                "若价格跌破支撑位，技术观点失效。",
                "若盈利指标明显转弱，基本面判断需要下修。",
            ],
        )


client = TestClient(app)


def test_get_research_report_route_returns_structured_payload() -> None:
    """研究报告接口应返回结构化响应。"""
    app.dependency_overrides[get_research_manager] = lambda: StubResearchManager()

    response = client.get("/research/600519")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["action"] == "BUY"
    assert response.json()["overall_score"] == 76

    app.dependency_overrides.clear()

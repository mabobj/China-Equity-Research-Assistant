"""API tests for stock data routes."""

from datetime import date, datetime, time
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_debate_runtime_service,
    get_decision_brief_service,
    get_factor_snapshot_service,
    get_market_data_service,
    get_stock_review_service,
    get_trigger_snapshot_service,
    get_workspace_bundle_service,
)
from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BearCase,
    BullCase,
    ChiefJudgement,
    DebateReviewProgress,
    DebatePoint,
    DebateReviewReport,
    RiskReview,
)
from app.schemas.decision_brief import (
    DecisionBrief,
    DecisionBriefEvidence,
    DecisionPriceLevel,
    DecisionSourceModule,
)
from app.main import app
from app.schemas.factor import (
    AlphaScore,
    FactorGroupScore,
    FactorSnapshot,
    RiskScore,
    TriggerScore,
)
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import (
    DailyBar,
    DailyBarResponse,
    IntradayBar,
    IntradayBarResponse,
    StockProfile,
    TimelinePoint,
    TimelineResponse,
    UniverseItem,
    UniverseResponse,
)
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary
from app.schemas.review import (
    BullBearCase,
    EventView,
    FactorProfileView,
    FinalJudgement,
    FundamentalView,
    SentimentView,
    StockReviewReport,
    StrategySummary,
    TechnicalView,
)
from app.schemas.strategy import PriceRange, StrategyPlan
from app.schemas.workspace import (
    FreshnessSummary,
    WorkspaceBundleResponse,
    WorkspaceFreshnessItem,
    WorkspaceModuleStatus,
)
from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.fallback import DebateRuntimeService


class StubMarketDataService:
    """Stub service for API route tests."""

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            source="stub",
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        return DailyBarResponse(
            symbol="600519.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            count=1,
            bars=[
                DailyBar(
                    symbol="600519.SH",
                    trade_date=date(2024, 1, 2),
                    close=101.0,
                    source="stub",
                )
            ],
        )

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> IntradayBarResponse:
        return IntradayBarResponse(
            symbol="600519.SH",
            frequency=frequency,
            start_datetime=datetime(2024, 1, 2, 9, 30, 0),
            end_datetime=datetime(2024, 1, 2, 10, 0, 0),
            count=1,
            bars=[
                IntradayBar(
                    symbol="600519.SH",
                    trade_datetime=datetime(2024, 1, 2, 9, 31, 0),
                    frequency=frequency,
                    close=100.2,
                    source="stub",
                )
            ],
        )

    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> TimelineResponse:
        return TimelineResponse(
            symbol="600519.SH",
            count=1,
            points=[
                TimelinePoint(
                    symbol="600519.SH",
                    trade_time=time(14, 55, 0),
                    price=100.8,
                    source="stub",
                )
            ],
        )

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=1,
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    code="600519",
                    exchange="SH",
                    name="Kweichow Moutai",
                    source="stub",
                )
            ],
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="Kweichow Moutai",
            revenue=100.0,
            revenue_yoy=12.0,
            net_profit=20.0,
            net_profit_yoy=15.0,
            roe=18.0,
            debt_ratio=30.0,
            eps=2.5,
            source="stub",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(symbol="600519.SH", count=0, items=[])


client = TestClient(app)


class StubTriggerSnapshotService:
    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        return TriggerSnapshot(
            symbol="600519.SH",
            as_of_datetime=datetime(2024, 1, 2, 10, 0, 0),
            daily_trend_state="up",
            daily_support_level=100.0,
            daily_resistance_level=102.0,
            latest_intraday_price=101.3,
            distance_to_support_pct=1.3,
            distance_to_resistance_pct=0.69,
            trigger_state="near_breakout",
            trigger_note="盘中价格接近日线压力位，上行趋势下处于突破观察区。",
        )


class StubFactorSnapshotService:
    def get_factor_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FactorSnapshot:
        return FactorSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 1, 2),
            raw_factors={"return_20d": 0.08},
            normalized_factors={"return_20d": 72.0},
            factor_group_scores=[
                FactorGroupScore(
                    group_name="trend",
                    score=72.0,
                    top_positive_signals=["20日收益率保持正向，短期相对强弱仍在改善"],
                    top_negative_signals=[],
                )
            ],
            alpha_score=AlphaScore(total_score=73, breakdown=[]),
            trigger_score=TriggerScore(
                total_score=68,
                trigger_state="pullback",
                breakdown=[],
            ),
            risk_score=RiskScore(total_score=35, breakdown=[]),
        )


class StubStockReviewService:
    def get_stock_review_report(self, symbol: str) -> StockReviewReport:
        return StockReviewReport(
            symbol="600519.SH",
            name="Kweichow Moutai",
            as_of_date=date(2024, 1, 2),
            factor_profile=FactorProfileView(
                strongest_factor_groups=["趋势", "事件"],
                weakest_factor_groups=["质量"],
                alpha_score=73,
                trigger_score=68,
                risk_score=35,
                concise_summary="alpha 分 73；触发分 68；风险分 35",
            ),
            technical_view=TechnicalView(
                trend_state="up",
                trigger_state="near_breakout",
                key_levels=["支撑位 100.00", "压力位 102.00"],
                tactical_read="价格靠近日线压力区。",
                invalidation_hint="若跌破支撑位则判断下修。",
            ),
            fundamental_view=FundamentalView(
                quality_read="盈利质量处于可接受区间。",
                growth_read="收入与利润维持正增长。",
                leverage_read="负债率可控。",
                data_completeness_note="关键财务字段大体可用。",
                key_financial_flags=["当前未出现明显财务红旗"],
            ),
            event_view=EventView(
                recent_catalysts=["关于回购股份方案的公告"],
                recent_risks=[],
                event_temperature="warm",
                concise_summary="近 30 日事件热度偏暖。",
            ),
            sentiment_view=SentimentView(
                sentiment_bias="bullish",
                crowding_hint="当前拥挤度信号中性。",
                momentum_context="20 日与 60 日相对强弱均偏正。",
                concise_summary="情绪偏多。",
            ),
            bull_case=BullBearCase(
                stance="bull",
                summary="多头论点主要来自趋势与事件。",
                reasons=["趋势占优", "事件偏正向"],
            ),
            bear_case=BullBearCase(
                stance="bear",
                summary="空头约束主要来自位置和风险控制。",
                reasons=["靠近压力位"],
            ),
            key_disagreements=["趋势偏强，但当前触发位置并不便宜。"],
            final_judgement=FinalJudgement(
                action="WATCH",
                summary="当前更适合先观察。",
                key_points=["next_3_to_5_trading_days"],
            ),
            strategy_summary=StrategySummary(
                action="WATCH",
                strategy_type="wait",
                entry_window="next_3_to_5_trading_days",
                ideal_entry_range=PriceRange(low=100.0, high=101.0),
                stop_loss_price=98.0,
                take_profit_range=PriceRange(low=104.0, high=106.0),
                review_timeframe="daily_close_review",
                concise_summary="策略层仍以观察为主。",
            ),
            confidence=69,
        )


class StubDebateOrchestrator:
    def get_debate_review_report(
        self,
        symbol: str,
        use_llm: Optional[bool] = None,
        request_id: Optional[str] = None,
    ) -> DebateReviewReport:
        return DebateReviewReport(
            symbol="600519.SH",
            name="Kweichow Moutai",
            as_of_date=date(2024, 1, 2),
            analyst_views=AnalystViewsBundle(
                technical=AnalystView(
                    role="technical_analyst",
                    summary="技术偏强。",
                    action_bias="supportive",
                    positive_points=[DebatePoint(title="趋势", detail="趋势偏强")],
                    caution_points=[DebatePoint(title="失效条件", detail="跌破支撑位")],
                    key_levels=["支撑位 100.00"],
                ),
                fundamental=AnalystView(
                    role="fundamental_analyst",
                    summary="基本面中性偏稳。",
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
                    caution_points=[],
                    key_levels=[],
                ),
                sentiment=AnalystView(
                    role="sentiment_analyst",
                    summary="情绪偏多。",
                    action_bias="supportive",
                    positive_points=[DebatePoint(title="动量环境", detail="20 日与 60 日相对强弱均偏正")],
                    caution_points=[DebatePoint(title="拥挤度提示", detail="当前拥挤度中性")],
                    key_levels=[],
                ),
            ),
            bull_case=BullCase(
                summary="多头理由主要来自趋势、事件与动量。",
                reasons=[DebatePoint(title="趋势", detail="趋势偏强")],
            ),
            bear_case=BearCase(
                summary="空头约束主要来自位置与纪律。",
                reasons=[DebatePoint(title="失效条件", detail="跌破支撑位")],
            ),
            key_disagreements=["当前分歧集中在执行时点。"],
            chief_judgement=ChiefJudgement(
                final_action="WATCH",
                summary="当前更适合先观察。",
                decisive_points=["alpha 分 73"],
                key_disagreements=["当前分歧集中在执行时点。"],
            ),
            risk_review=RiskReview(
                risk_level="medium",
                summary="风险可控但需要纪律。",
                execution_reminders=["严格观察止损参考位 98.00。"],
            ),
            final_action="WATCH",
            strategy_summary=StrategySummary(
                action="WATCH",
                strategy_type="wait",
                entry_window="next_3_to_5_trading_days",
                ideal_entry_range=PriceRange(low=100.0, high=101.0),
                stop_loss_price=98.0,
                take_profit_range=PriceRange(low=104.0, high=106.0),
                review_timeframe="daily_close_review",
                concise_summary="策略层仍以观察为主。",
            ),
            confidence=67,
            runtime_mode="llm" if use_llm else "rule_based",
        )

    def get_debate_review_progress(
        self,
        symbol: str,
        *,
        request_id: Optional[str] = None,
        use_llm: Optional[bool] = None,
    ) -> DebateReviewProgress:
        return DebateReviewProgress(
            symbol="600519.SH",
            request_id=request_id,
            status="running",
            stage="running_roles",
            runtime_mode="llm" if use_llm else "rule_based",
            current_step="正在执行：技术分析员",
            completed_steps=1,
            total_steps=9,
            message="后台正在运行技术分析员。",
            recent_steps=["正在执行：技术分析员"],
        )


class _FallbackRuleDebateOrchestrator:
    def get_debate_review_report(self, symbol: str):
        return StubDebateOrchestrator().get_debate_review_report(symbol, use_llm=False)


class _FailingLLMOrchestrator:
    def get_debate_review_report(self, symbol: str, request_id: Optional[str] = None):
        raise TimeoutError("mock timeout")


class StubDecisionBriefService:
    def get_decision_brief(
        self,
        symbol: str,
        *,
        use_llm: Optional[bool] = None,
    ) -> DecisionBrief:
        return DecisionBrief(
            symbol="600519.SH",
            name="Kweichow Moutai",
            as_of_date=date(2024, 1, 2),
            headline_verdict="Kweichow Moutai 鏇撮€傚悎鍏堢瓑鍥炶俯锛屼笉瑕佺洿鎺ヨ拷浠枫€?",
            action_now="WAIT_PULLBACK",
            conviction_level="medium",
            why_it_made_the_list=["瓒嬪娍鍜屼簨浠剁淮搴︿粛鏈夋敮鎾戙€?"],
            why_not_all_in=["褰撳墠浣嶇疆杩樺緱绛夊洖鎵嶆洿鑸掓湇銆?"],
            key_evidence=[
                DecisionBriefEvidence(
                    title="瓒嬪娍鍗犱紭",
                    detail="20鏃ユ敹鐩婄巼淇濇寔姝ｅ悜锛岀煭鏈熺浉瀵瑰己寮变粛鍦ㄦ敼鍠勩€?",
                    source_module="factor_snapshot",
                )
            ],
            key_risks=[
                DecisionBriefEvidence(
                    title="浣嶇疆绾︽潫",
                    detail="褰撳墠鏇撮€傚悎绛夊洖鎵嶇‘璁わ紝涓嶅疁鐩存帴杩戒环銆?",
                    source_module="review_report",
                )
            ],
            price_levels_to_watch=[
                DecisionPriceLevel(
                    label="鐞嗘兂瑙傚療鍖洪棿",
                    value_text="100.00 - 101.00",
                )
            ],
            what_to_do_next=["鍏堢瓑鍥炶俯鍒?100.00 - 101.00 闄勮繎鍐嶅鏍搞€?"],
            next_review_window="daily_close_review",
            source_modules=[
                DecisionSourceModule(
                    module_name="debate_review",
                    as_of="2024-01-02",
                    note="runtime_mode=llm" if use_llm else "runtime_mode=rule_based",
                )
            ],
        )


class StubWorkspaceBundleService:
    def get_workspace_bundle(
        self,
        symbol: str,
        *,
        use_llm: Optional[bool] = None,
        force_refresh: bool = False,
        request_id: Optional[str] = None,
    ) -> WorkspaceBundleResponse:
        return WorkspaceBundleResponse(
            symbol="600519.SH",
            use_llm=bool(use_llm),
            profile=StubMarketDataService().get_stock_profile(symbol),
            factor_snapshot=StubFactorSnapshotService().get_factor_snapshot(symbol),
            review_report=StubStockReviewService().get_stock_review_report(symbol),
            debate_review=StubDebateOrchestrator().get_debate_review_report(
                symbol,
                use_llm=use_llm,
                request_id=request_id,
            ),
            strategy_plan=StrategyPlan(
                symbol="600519.SH",
                name="Kweichow Moutai",
                as_of_date=date(2024, 1, 2),
                action="WATCH",
                strategy_type="wait",
                entry_window="next_3_to_5_trading_days",
                ideal_entry_range=PriceRange(low=100.0, high=101.0),
                entry_triggers=["Wait for a cleaner pullback."],
                avoid_if=["Avoid chasing a breakout without confirmation."],
                initial_position_hint="small",
                stop_loss_price=98.0,
                stop_loss_rule="Use the support break as the stop-loss reference.",
                take_profit_range=PriceRange(low=104.0, high=106.0),
                take_profit_rule="Scale out into the target zone.",
                hold_rule="Keep reviewing at the daily close.",
                sell_rule="Exit if the thesis breaks.",
                review_timeframe="daily_close_review",
                confidence=68,
            ),
            trigger_snapshot=StubTriggerSnapshotService().get_trigger_snapshot(symbol),
            decision_brief=StubDecisionBriefService().get_decision_brief(
                symbol,
                use_llm=use_llm,
            ),
            module_status_summary=[
                WorkspaceModuleStatus(module_name="profile", status="success"),
                WorkspaceModuleStatus(module_name="debate_review", status="success"),
            ],
            freshness_summary=FreshnessSummary(
                default_as_of_date=date(2024, 1, 2),
                items=[
                    WorkspaceFreshnessItem(
                        item_name="factor_snapshot_daily",
                        as_of_date=date(2024, 1, 2),
                        freshness_mode="cache_hit",
                        source_mode="snapshot",
                    )
                ],
            ),
        )


class StubPartialWorkspaceBundleService:
    def get_workspace_bundle(
        self,
        symbol: str,
        *,
        use_llm: Optional[bool] = None,
        force_refresh: bool = False,
        request_id: Optional[str] = None,
    ) -> WorkspaceBundleResponse:
        return WorkspaceBundleResponse(
            symbol="600519.SH",
            use_llm=bool(use_llm),
            profile=StubMarketDataService().get_stock_profile(symbol),
            factor_snapshot=StubFactorSnapshotService().get_factor_snapshot(symbol),
            review_report=None,
            debate_review=None,
            strategy_plan=None,
            trigger_snapshot=None,
            decision_brief=None,
            module_status_summary=[
                WorkspaceModuleStatus(module_name="profile", status="success"),
                WorkspaceModuleStatus(
                    module_name="review_report",
                    status="error",
                    message="mock review failure",
                    fallback_applied=True,
                    fallback_reason="review_report failed and was skipped.",
                ),
            ],
            freshness_summary=FreshnessSummary(default_as_of_date=date(2024, 1, 2), items=[]),
            fallback_applied=True,
            fallback_reason="One or more workspace modules failed and were skipped.",
            runtime_mode_requested="rule_based",
            runtime_mode_effective="rule_based",
            warning_messages=["Partial workspace result. Failed modules: review_report."],
        )


def test_get_stock_profile_route_returns_structured_payload() -> None:
    """The stock profile endpoint should return the schema payload."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()
    response = client.get("/stocks/600519/profile")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["name"] == "Kweichow Moutai"

    app.dependency_overrides.clear()


def test_get_stock_universe_route_returns_structured_payload() -> None:
    """The stock universe endpoint should remain schema compatible."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()
    response = client.get("/stocks/universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["symbol"] == "600519.SH"
    assert payload["items"][0]["name"] == "Kweichow Moutai"

    app.dependency_overrides.clear()


def test_get_daily_bars_route_returns_structured_payload() -> None:
    """The daily bars endpoint should remain schema compatible."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()
    response = client.get("/stocks/600519/daily-bars")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["count"] == 1
    assert payload["bars"][0]["trade_date"] == "2024-01-02"

    app.dependency_overrides.clear()


def test_workspace_bundle_route_returns_structured_payload() -> None:
    """Workspace bundle should expose the stock page primary payload."""
    app.dependency_overrides[get_workspace_bundle_service] = (
        lambda: StubWorkspaceBundleService()
    )

    response = client.get(
        "/stocks/600519/workspace-bundle?use_llm=true&request_id=req-1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["use_llm"] is True
    assert payload["decision_brief"]["action_now"] == "WAIT_PULLBACK"
    assert payload["module_status_summary"][0]["module_name"] == "profile"
    assert payload["freshness_summary"]["default_as_of_date"] == "2024-01-02"

    app.dependency_overrides.clear()


def test_workspace_bundle_route_returns_200_when_one_module_fails() -> None:
    """Workspace bundle should still return 200 with module-level error states."""
    app.dependency_overrides[get_workspace_bundle_service] = (
        lambda: StubPartialWorkspaceBundleService()
    )

    response = client.get("/stocks/600519/workspace-bundle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["review_report"] is None
    assert payload["module_status_summary"][1]["module_name"] == "review_report"
    assert payload["module_status_summary"][1]["status"] == "error"
    assert payload["module_status_summary"][1]["message"] == "mock review failure"
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "One or more workspace modules failed and were skipped."
    assert payload["warning_messages"][0].startswith("Partial workspace result")

    app.dependency_overrides.clear()


def test_decision_brief_route_returns_structured_payload() -> None:
    """The decision-brief route should expose unified brief payloads."""
    app.dependency_overrides[get_decision_brief_service] = (
        lambda: StubDecisionBriefService()
    )

    response = client.get("/stocks/600519/decision-brief?use_llm=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["action_now"] == "WAIT_PULLBACK"
    assert payload["conviction_level"] == "medium"
    assert payload["key_evidence"][0]["source_module"] == "factor_snapshot"
    assert payload["source_modules"][0]["note"] == "runtime_mode=llm"

    app.dependency_overrides.clear()


def test_invalid_symbol_returns_400() -> None:
    """Invalid symbols should return a clear 400 response."""
    app.dependency_overrides.clear()
    response = client.get("/stocks/not-a-symbol/profile")

    assert response.status_code == 400
    assert "Invalid symbol" in response.json()["detail"]


def test_intraday_bars_route_supports_frequency_and_datetime_filters() -> None:
    """The intraday route should expose structured minute-bar payloads."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()

    response = client.get(
        "/stocks/600519/intraday-bars?frequency=5m&start_datetime=2024-01-02T09:30:00&end_datetime=2024-01-02T10:00:00",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["frequency"] == "5m"
    assert payload["start_datetime"] == "2024-01-02T09:30:00"
    assert payload["end_datetime"] == "2024-01-02T10:00:00"
    assert payload["count"] == 1

    app.dependency_overrides.clear()


def test_timeline_route_returns_structured_payload() -> None:
    """The timeline route should return the latest-trading-day preview points."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()

    response = client.get("/stocks/600519/timeline?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["count"] == 1
    assert payload["points"][0]["trade_time"] == "14:55:00"

    app.dependency_overrides.clear()


def test_trigger_snapshot_route_returns_structured_payload() -> None:
    """The trigger snapshot route should return structured trigger fields."""
    app.dependency_overrides[get_trigger_snapshot_service] = (
        lambda: StubTriggerSnapshotService()
    )

    response = client.get("/stocks/600519/trigger-snapshot?frequency=5m&limit=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["trigger_state"] == "near_breakout"
    assert payload["daily_trend_state"] == "up"

    app.dependency_overrides.clear()


def test_factor_snapshot_route_returns_structured_payload() -> None:
    """The factor snapshot route should return structured factor fields."""
    app.dependency_overrides[get_factor_snapshot_service] = (
        lambda: StubFactorSnapshotService()
    )

    response = client.get("/stocks/600519/factor-snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["alpha_score"]["total_score"] == 73
    assert payload["trigger_score"]["trigger_state"] == "pullback"
    assert payload["risk_score"]["total_score"] == 35

    app.dependency_overrides.clear()


def test_review_report_route_returns_structured_payload() -> None:
    """The review-report route should expose review v2 payloads."""
    app.dependency_overrides[get_stock_review_service] = (
        lambda: StubStockReviewService()
    )

    response = client.get("/stocks/600519/review-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["factor_profile"]["alpha_score"] == 73
    assert payload["technical_view"]["trigger_state"] == "near_breakout"
    assert payload["final_judgement"]["action"] == "WATCH"

    app.dependency_overrides.clear()


def test_debate_review_route_returns_structured_payload() -> None:
    """The debate-review route should expose debate-role payloads."""
    app.dependency_overrides[get_debate_runtime_service] = (
        lambda: StubDebateOrchestrator()
    )

    response = client.get("/stocks/600519/debate-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["analyst_views"]["technical"]["role"] == "technical_analyst"
    assert payload["chief_judgement"]["final_action"] == "WATCH"
    assert payload["risk_review"]["risk_level"] == "medium"
    assert payload["runtime_mode"] == "rule_based"
    assert payload["runtime_mode_effective"] in {None, "rule_based"}

    response = client.get("/stocks/600519/debate-review?use_llm=true&force_refresh=true")
    payload = response.json()
    assert payload["runtime_mode"] == "llm"
    assert payload["runtime_mode_requested"] in {None, "llm"}

    app.dependency_overrides.clear()


def test_debate_review_route_falls_back_to_rule_based_when_llm_timeout() -> None:
    """When LLM mode fails, the route should still return a controlled rule-based payload."""
    runtime_service = DebateRuntimeService(
        rule_based_orchestrator=_FallbackRuleDebateOrchestrator(),
        llm_orchestrator=_FailingLLMOrchestrator(),
        settings=LLMDebateSettings(
            enabled=True,
            api_key="test-key",
            model="gpt-test",
            base_url=None,
            timeout_seconds=10,
        ),
    )
    app.dependency_overrides[get_debate_runtime_service] = lambda: runtime_service

    response = client.get("/stocks/600519/debate-review?use_llm=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_mode"] == "rule_based"
    assert payload["symbol"] == "600519.SH"
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "LLM runtime failed or timed out."
    assert payload["runtime_mode_requested"] == "llm"
    assert payload["runtime_mode_effective"] == "rule_based"
    assert payload["provider_used"] == "rule_based"

    app.dependency_overrides.clear()


def test_debate_review_progress_route_returns_structured_payload() -> None:
    """The debate-review-progress route should expose backend progress."""
    app.dependency_overrides[get_debate_runtime_service] = (
        lambda: StubDebateOrchestrator()
    )

    response = client.get(
        "/stocks/600519/debate-review-progress?use_llm=true&request_id=req-1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["request_id"] == "req-1"
    assert payload["stage"] == "running_roles"
    assert payload["current_step"] == "正在执行：技术分析员"

    app.dependency_overrides.clear()

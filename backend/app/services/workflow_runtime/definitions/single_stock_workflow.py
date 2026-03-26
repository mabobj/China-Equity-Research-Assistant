"""单票完整研判 workflow 定义。"""

from __future__ import annotations

from typing import Any

from app.schemas.debate import DebateReviewReport, SingleStockResearchInputs
from app.schemas.factor import FactorSnapshot
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan
from app.schemas.workflow import (
    SingleStockWorkflowOutput,
    SingleStockWorkflowRunRequest,
)
from app.services.debate_service.debate_orchestrator import DebateOrchestrator
from app.services.factor_service.factor_snapshot_service import FactorSnapshotService
from app.services.llm_debate_service.fallback import DebateRuntimeService
from app.services.research_service.strategy_planner import StrategyPlanner
from app.services.review_service.stock_review_service import StockReviewService
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext


class SingleStockWorkflowDefinitionBuilder:
    """构建单票 workflow 定义。"""

    def __init__(
        self,
        debate_orchestrator: DebateOrchestrator,
        factor_snapshot_service: FactorSnapshotService,
        stock_review_service: StockReviewService,
        debate_runtime_service: DebateRuntimeService,
        strategy_planner: StrategyPlanner,
    ) -> None:
        self._debate_orchestrator = debate_orchestrator
        self._factor_snapshot_service = factor_snapshot_service
        self._stock_review_service = stock_review_service
        self._debate_runtime_service = debate_runtime_service
        self._strategy_planner = strategy_planner

    def build(self) -> WorkflowDefinition:
        """返回单票 workflow 定义。"""
        return WorkflowDefinition(
            name="single_stock_full_review",
            request_contract=SingleStockWorkflowRunRequest,
            final_output_contract=SingleStockWorkflowOutput,
            nodes=(
                WorkflowNode(
                    name="SingleStockResearchInputs",
                    input_contract=SingleStockWorkflowRunRequest,
                    output_contract=SingleStockResearchInputs,
                    handler=self._build_research_inputs,
                    input_summary_builder=self._build_symbol_only_summary,
                    output_summary_builder=self._build_research_inputs_summary,
                ),
                WorkflowNode(
                    name="FactorSnapshotBuild",
                    input_contract=SingleStockWorkflowRunRequest,
                    output_contract=FactorSnapshot,
                    handler=self._build_factor_snapshot,
                    input_summary_builder=self._build_symbol_only_summary,
                    output_summary_builder=self._build_factor_snapshot_summary,
                ),
                WorkflowNode(
                    name="ReviewReportBuild",
                    input_contract=SingleStockWorkflowRunRequest,
                    output_contract=StockReviewReport,
                    handler=self._build_review_report,
                    input_summary_builder=self._build_symbol_only_summary,
                    output_summary_builder=self._build_review_summary,
                ),
                WorkflowNode(
                    name="DebateReviewBuild",
                    input_contract=SingleStockResearchInputs,
                    output_contract=DebateReviewReport,
                    handler=self._build_debate_review,
                    input_summary_builder=self._build_symbol_only_summary,
                    output_summary_builder=self._build_debate_summary,
                ),
                WorkflowNode(
                    name="StrategyPlanBuild",
                    input_contract=SingleStockWorkflowRunRequest,
                    output_contract=StrategyPlan,
                    handler=self._build_strategy_plan,
                    input_summary_builder=self._build_symbol_only_summary,
                    output_summary_builder=self._build_strategy_summary,
                ),
            ),
            input_summary_builder=self._build_request_summary,
            final_output_builder=self._build_final_output,
            final_output_summary_builder=self._build_final_output_summary,
        )

    def _build_research_inputs(self, context: WorkflowContext) -> SingleStockResearchInputs:
        request = self._get_request(context)
        output = self._debate_orchestrator.build_inputs(request.symbol)
        context.set_output("SingleStockResearchInputs", output)
        return output

    def _build_factor_snapshot(self, context: WorkflowContext) -> FactorSnapshot:
        request = self._get_request(context)
        output = self._factor_snapshot_service.get_factor_snapshot(request.symbol)
        context.set_output("FactorSnapshotBuild", output)
        return output

    def _build_review_report(self, context: WorkflowContext) -> StockReviewReport:
        request = self._get_request(context)
        output = self._stock_review_service.get_stock_review_report(request.symbol)
        context.set_output("ReviewReportBuild", output)
        return output

    def _build_debate_review(self, context: WorkflowContext) -> DebateReviewReport:
        request = self._get_request(context)
        output = self._debate_runtime_service.get_debate_review_report(
            request.symbol,
            use_llm=context.use_llm,
        )
        context.set_output("DebateReviewBuild", output)
        return output

    def _build_strategy_plan(self, context: WorkflowContext) -> StrategyPlan:
        request = self._get_request(context)
        output = self._strategy_planner.get_strategy_plan(request.symbol)
        context.set_output("StrategyPlanBuild", output)
        return output

    def _build_request_summary(
        self,
        request: SingleStockWorkflowRunRequest,
    ) -> dict[str, Any]:
        return {
            "symbol": request.symbol,
            "start_from": request.start_from,
            "stop_after": request.stop_after,
            "use_llm": request.use_llm,
        }

    def _build_symbol_only_summary(self, context: WorkflowContext) -> dict[str, Any]:
        request = self._get_request(context)
        return {"symbol": request.symbol, "use_llm": context.use_llm}

    def _build_research_inputs_summary(
        self,
        output: SingleStockResearchInputs,
    ) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "review_action": output.review_report.final_judgement.action,
            "trigger_state": output.trigger_state,
            "factor_alpha_score": output.factor_alpha_score,
            "factor_risk_score": output.factor_risk_score,
        }

    def _build_factor_snapshot_summary(self, output: FactorSnapshot) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "as_of_date": output.as_of_date.isoformat(),
            "alpha_score": output.alpha_score.total_score,
            "trigger_score": output.trigger_score.total_score,
            "risk_score": output.risk_score.total_score,
        }

    def _build_review_summary(self, output: StockReviewReport) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "action": output.final_judgement.action,
            "confidence": output.confidence,
            "alpha_score": output.factor_profile.alpha_score,
            "risk_score": output.factor_profile.risk_score,
        }

    def _build_debate_summary(self, output: DebateReviewReport) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "final_action": output.final_action,
            "confidence": output.confidence,
            "runtime_mode": output.runtime_mode,
        }

    def _build_strategy_summary(self, output: StrategyPlan) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "action": output.action,
            "strategy_type": output.strategy_type,
            "confidence": output.confidence,
        }

    def _build_final_output(self, context: WorkflowContext) -> SingleStockWorkflowOutput:
        request = self._get_request(context)
        return SingleStockWorkflowOutput(
            symbol=request.symbol,
            research_inputs=context.get_output(
                "SingleStockResearchInputs",
                SingleStockResearchInputs,
            ),
            factor_snapshot=context.get_output("FactorSnapshotBuild", FactorSnapshot),
            review_report=context.get_output("ReviewReportBuild", StockReviewReport),
            debate_review=context.get_output("DebateReviewBuild", DebateReviewReport),
            strategy_plan=context.get_output("StrategyPlanBuild", StrategyPlan),
        )

    def _build_final_output_summary(
        self,
        output: SingleStockWorkflowOutput,
    ) -> dict[str, Any]:
        return {
            "symbol": output.symbol,
            "has_research_inputs": output.research_inputs is not None,
            "has_factor_snapshot": output.factor_snapshot is not None,
            "review_action": (
                output.review_report.final_judgement.action
                if output.review_report is not None
                else None
            ),
            "debate_action": (
                output.debate_review.final_action
                if output.debate_review is not None
                else None
            ),
            "strategy_action": (
                output.strategy_plan.action if output.strategy_plan is not None else None
            ),
        }

    def _get_request(self, context: WorkflowContext) -> SingleStockWorkflowRunRequest:
        return SingleStockWorkflowRunRequest.model_validate(context.request)


def build_single_stock_workflow_definition(
    debate_orchestrator: DebateOrchestrator,
    factor_snapshot_service: FactorSnapshotService,
    stock_review_service: StockReviewService,
    debate_runtime_service: DebateRuntimeService,
    strategy_planner: StrategyPlanner,
) -> WorkflowDefinition:
    """构建单票完整研判 workflow 定义。"""
    return SingleStockWorkflowDefinitionBuilder(
        debate_orchestrator=debate_orchestrator,
        factor_snapshot_service=factor_snapshot_service,
        stock_review_service=stock_review_service,
        debate_runtime_service=debate_runtime_service,
        strategy_planner=strategy_planner,
    ).build()

"""深筛复核 workflow 定义。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import (
    CandidateWorkflowItem,
    DeepCandidateSelection,
    DeepReviewBatchOutput,
    DeepReviewWorkflowOutput,
    DeepReviewWorkflowRunRequest,
    WorkflowSymbolFailure,
)
from app.services.llm_debate_service.fallback import DebateRuntimeService
from app.services.screener_service.pipeline import ScreenerPipeline
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext

if TYPE_CHECKING:
    from app.services.research_service.strategy_planner import StrategyPlanner
    from app.services.review_service.stock_review_service import StockReviewService


class DeepReviewWorkflowDefinitionBuilder:
    """构建深筛复核 workflow 定义。"""

    def __init__(
        self,
        screener_pipeline: ScreenerPipeline,
        stock_review_service: StockReviewService,
        debate_runtime_service: DebateRuntimeService,
        strategy_planner: StrategyPlanner,
    ) -> None:
        self._screener_pipeline = screener_pipeline
        self._stock_review_service = stock_review_service
        self._debate_runtime_service = debate_runtime_service
        self._strategy_planner = strategy_planner

    def build(self) -> WorkflowDefinition:
        """返回深筛复核 workflow 定义。"""
        return WorkflowDefinition(
            name="deep_candidate_review",
            request_contract=DeepReviewWorkflowRunRequest,
            final_output_contract=DeepReviewWorkflowOutput,
            nodes=(
                WorkflowNode(
                    name="ScreenerRun",
                    input_contract=DeepReviewWorkflowRunRequest,
                    output_contract=ScreenerRunResponse,
                    handler=self._run_screener,
                    input_summary_builder=self._build_request_input_summary,
                    output_summary_builder=self._build_screener_summary,
                ),
                WorkflowNode(
                    name="DeepCandidateSelect",
                    input_contract=ScreenerRunResponse,
                    output_contract=DeepCandidateSelection,
                    handler=self._select_candidates,
                    input_summary_builder=self._build_selection_input_summary,
                    output_summary_builder=self._build_selection_summary,
                ),
                WorkflowNode(
                    name="CandidateReviewBuild",
                    input_contract=DeepCandidateSelection,
                    output_contract=DeepReviewBatchOutput,
                    handler=self._build_candidate_reviews,
                    input_summary_builder=self._build_selection_input_summary,
                    output_summary_builder=self._build_batch_summary,
                ),
                WorkflowNode(
                    name="CandidateDebateBuild",
                    input_contract=DeepReviewBatchOutput,
                    output_contract=DeepReviewBatchOutput,
                    handler=self._build_candidate_debates,
                    input_summary_builder=self._build_batch_input_summary,
                    output_summary_builder=self._build_batch_summary,
                ),
                WorkflowNode(
                    name="CandidateStrategyBuild",
                    input_contract=DeepReviewBatchOutput,
                    output_contract=DeepReviewBatchOutput,
                    handler=self._build_candidate_strategies,
                    input_summary_builder=self._build_batch_input_summary,
                    output_summary_builder=self._build_batch_summary,
                ),
            ),
            input_summary_builder=self._build_request_summary,
            final_output_builder=self._build_final_output,
            final_output_summary_builder=self._build_final_output_summary,
        )

    def _run_screener(self, context: WorkflowContext) -> ScreenerRunResponse:
        request = self._get_request(context)
        try:
            output = self._screener_pipeline.run_screener(
                max_symbols=request.max_symbols,
                top_n=request.top_n,
                force_refresh=bool(request.force_refresh),
            )
        except TypeError:
            output = self._screener_pipeline.run_screener(
                max_symbols=request.max_symbols,
                top_n=request.top_n,
            )
        context.set_output("ScreenerRun", output)
        return output

    def _select_candidates(self, context: WorkflowContext) -> DeepCandidateSelection:
        request = self._get_request(context)
        screener_run = self._ensure_screener_run(context)
        selected = _select_candidates_for_deep_review_lightweight(
            base_result=screener_run,
            deep_top_k=request.deep_top_k,
        )
        output = DeepCandidateSelection(
            selected_candidates=selected,
            selected_symbols=[candidate.symbol for candidate in selected],
        )
        context.set_output("DeepCandidateSelect", output)
        return output

    def _build_candidate_reviews(self, context: WorkflowContext) -> DeepReviewBatchOutput:
        selection = self._ensure_selection(context)
        items: list[CandidateWorkflowItem] = []
        failures: list[WorkflowSymbolFailure] = []

        for candidate in selection.selected_candidates:
            try:
                review_report = self._stock_review_service.get_stock_review_report(
                    candidate.symbol
                )
            except Exception as exc:
                failures.append(
                    WorkflowSymbolFailure(
                        symbol=candidate.symbol,
                        step_name="CandidateReviewBuild",
                        error_message=f"构建个股研判失败：{exc}",
                    )
                )
                continue

            items.append(
                CandidateWorkflowItem(
                    symbol=candidate.symbol,
                    name=review_report.name,
                    base_candidate=candidate,
                    review_report=review_report,
                )
            )

        output = DeepReviewBatchOutput(items=items, failures=failures)
        context.set_output("CandidateReviewBuild", output)
        return output

    def _build_candidate_debates(self, context: WorkflowContext) -> DeepReviewBatchOutput:
        review_batch = self._ensure_review_batch(context)
        items: list[CandidateWorkflowItem] = []
        failures = list(review_batch.failures)

        for item in review_batch.items:
            try:
                debate_review = self._debate_runtime_service.get_debate_review_report(
                    item.symbol,
                    use_llm=context.use_llm,
                )
            except Exception as exc:
                failures.append(
                    WorkflowSymbolFailure(
                        symbol=item.symbol,
                        step_name="CandidateDebateBuild",
                        error_message=f"构建角色化裁决失败：{exc}",
                    )
                )
                continue

            items.append(
                item.model_copy(
                    update={
                        "debate_review": debate_review,
                        "name": debate_review.name,
                    }
                )
            )

        output = DeepReviewBatchOutput(items=items, failures=failures)
        context.set_output("CandidateDebateBuild", output)
        return output

    def _build_candidate_strategies(self, context: WorkflowContext) -> DeepReviewBatchOutput:
        debate_batch = self._ensure_debate_batch(context)
        items: list[CandidateWorkflowItem] = []
        failures = list(debate_batch.failures)

        for item in debate_batch.items:
            try:
                strategy_plan = self._strategy_planner.get_strategy_plan(item.symbol)
            except Exception as exc:
                failures.append(
                    WorkflowSymbolFailure(
                        symbol=item.symbol,
                        step_name="CandidateStrategyBuild",
                        error_message=f"构建交易策略失败：{exc}",
                    )
                )
                continue

            items.append(
                item.model_copy(
                    update={
                        "strategy_plan": strategy_plan,
                        "name": strategy_plan.name,
                    }
                )
            )

        output = DeepReviewBatchOutput(items=items, failures=failures)
        context.set_output("CandidateStrategyBuild", output)
        return output

    def _build_request_summary(
        self,
        request: DeepReviewWorkflowRunRequest,
    ) -> dict[str, Any]:
        return {
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "deep_top_k": request.deep_top_k,
            "force_refresh": request.force_refresh,
            "start_from": request.start_from,
            "stop_after": request.stop_after,
            "use_llm": request.use_llm,
        }

    def _build_request_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        request = self._get_request(context)
        return {
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "deep_top_k": request.deep_top_k,
            "force_refresh": request.force_refresh,
            "use_llm": context.use_llm,
        }

    def _build_selection_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        selection = context.get_output("DeepCandidateSelect", DeepCandidateSelection)
        if selection is not None:
            return {
                "selected_symbols": selection.selected_symbols,
                "selected_count": len(selection.selected_symbols),
            }

        screener_run = context.get_output("ScreenerRun", ScreenerRunResponse)
        if screener_run is not None:
            total_candidates = (
                len(screener_run.buy_candidates) + len(screener_run.watch_candidates)
            )
            return {"available_candidates": total_candidates}

        return self._build_request_input_summary(context)

    def _build_batch_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        batch = context.get_output("CandidateReviewBuild", DeepReviewBatchOutput)
        if batch is None:
            batch = context.get_output("CandidateDebateBuild", DeepReviewBatchOutput)
        if batch is None:
            batch = context.get_output("CandidateStrategyBuild", DeepReviewBatchOutput)
        if batch is None:
            selection = self._ensure_selection(context)
            return {
                "selected_symbols": selection.selected_symbols,
                "selected_count": len(selection.selected_symbols),
            }
        return {
            "candidate_count": len(batch.items),
            "failure_count": len(batch.failures),
        }

    def _build_screener_summary(self, output: ScreenerRunResponse) -> dict[str, Any]:
        return {
            "as_of_date": output.as_of_date.isoformat(),
            "total_symbols": output.total_symbols,
            "scanned_symbols": output.scanned_symbols,
            "buy_candidates": len(output.buy_candidates),
            "watch_candidates": len(output.watch_candidates),
        }

    def _build_selection_summary(self, output: DeepCandidateSelection) -> dict[str, Any]:
        return {
            "selected_count": len(output.selected_candidates),
            "selected_symbols": output.selected_symbols,
        }

    def _build_batch_summary(self, output: DeepReviewBatchOutput) -> dict[str, Any]:
        return {
            "success_count": len(output.items),
            "failure_count": len(output.failures),
            "symbols": [item.symbol for item in output.items],
            "failed_symbols": [failure.symbol for failure in output.failures],
        }

    def _build_final_output(self, context: WorkflowContext) -> DeepReviewWorkflowOutput:
        batch = context.get_output("CandidateStrategyBuild", DeepReviewBatchOutput)
        if batch is None:
            batch = context.get_output("CandidateDebateBuild", DeepReviewBatchOutput)
        if batch is None:
            batch = context.get_output("CandidateReviewBuild", DeepReviewBatchOutput)
        if batch is None:
            batch = DeepReviewBatchOutput()

        return DeepReviewWorkflowOutput(
            screener_run=context.get_output("ScreenerRun", ScreenerRunResponse),
            candidate_selection=context.get_output(
                "DeepCandidateSelect",
                DeepCandidateSelection,
            ),
            candidates=batch.items,
            failures=batch.failures,
        )

    def _build_final_output_summary(
        self,
        output: DeepReviewWorkflowOutput,
    ) -> dict[str, Any]:
        return {
            "selected_count": (
                len(output.candidate_selection.selected_symbols)
                if output.candidate_selection is not None
                else 0
            ),
            "success_count": len(output.candidates),
            "failure_count": len(output.failures),
            "failed_symbols": [failure.symbol for failure in output.failures],
            "candidate_symbols": [item.symbol for item in output.candidates],
        }

    def _ensure_screener_run(self, context: WorkflowContext) -> ScreenerRunResponse:
        screener_run = context.get_output("ScreenerRun", ScreenerRunResponse)
        if screener_run is not None:
            return screener_run
        return self._run_screener(context)

    def _ensure_selection(self, context: WorkflowContext) -> DeepCandidateSelection:
        selection = context.get_output("DeepCandidateSelect", DeepCandidateSelection)
        if selection is not None:
            return selection
        return self._select_candidates(context)

    def _ensure_review_batch(self, context: WorkflowContext) -> DeepReviewBatchOutput:
        batch = context.get_output("CandidateReviewBuild", DeepReviewBatchOutput)
        if batch is not None:
            return batch
        return self._build_candidate_reviews(context)

    def _ensure_debate_batch(self, context: WorkflowContext) -> DeepReviewBatchOutput:
        batch = context.get_output("CandidateDebateBuild", DeepReviewBatchOutput)
        if batch is not None:
            return batch
        return self._build_candidate_debates(context)

    def _get_request(self, context: WorkflowContext) -> DeepReviewWorkflowRunRequest:
        return DeepReviewWorkflowRunRequest.model_validate(context.request)


def build_deep_review_workflow_definition(
    screener_pipeline: ScreenerPipeline,
    stock_review_service: StockReviewService,
    debate_runtime_service: DebateRuntimeService,
    strategy_planner: StrategyPlanner,
) -> WorkflowDefinition:
    """构建深筛复核 workflow 定义。"""
    return DeepReviewWorkflowDefinitionBuilder(
        screener_pipeline=screener_pipeline,
        stock_review_service=stock_review_service,
        debate_runtime_service=debate_runtime_service,
        strategy_planner=strategy_planner,
    ).build()


def _select_candidates_for_deep_review_lightweight(
    *,
    base_result: ScreenerRunResponse,
    deep_top_k: int | None,
) -> list:
    candidates = list(base_result.buy_candidates) + list(base_result.watch_candidates)
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            _base_list_priority(item.list_type),
            -item.screener_score,
            item.rank,
            item.symbol,
        ),
    )
    if deep_top_k is not None:
        return sorted_candidates[: max(deep_top_k, 0)]
    return sorted_candidates


def _base_list_priority(list_type: str) -> int:
    priority_map = {
        "BUY_CANDIDATE": 0,
        "WATCHLIST": 1,
        "AVOID": 2,
    }
    return priority_map.get(list_type, 9)

"use client";

import Link from "next/link";
import { Fragment } from "react";

import {
  formatDateTime,
  formatDecisionBriefAction,
  formatLabel,
  formatListType,
  formatModelRecommendation,
  formatPrice,
  formatPredictiveConfidenceLevel,
  formatPredictiveScoreLevel,
  formatRatioPercent,
  formatScore,
} from "@/lib/format";
import type {
  ModelEvaluationResponse,
  ScreenerBatchRecord,
  ScreenerListType,
  ScreenerSymbolResult,
} from "@/types/api";

import { SectionCard } from "./section-card";
import {
  ScreenerField,
  ScreenerMetric,
  ScreenerStringPanel,
} from "./screener-shared";
import { StatusBlock } from "./status-block";

const PAGE_SIZE_OPTIONS = [20, 50, 100, 200] as const;

export type ResultFilters = {
  symbolQuery: string;
  listType: ScreenerListType | "ALL";
  minScore: string;
  maxScore: string;
  reasonQuery: string;
  calculatedFrom: string;
  calculatedTo: string;
  ruleVersion: string;
};

export function ScreenerResultPanel({
  batch,
  batchResultCount,
  loading,
  error,
  results,
  filteredResults,
  selectedSymbol,
  onSelectSymbol,
  filters,
  onUpdateFilter,
  currentPage,
  totalPages,
  totalResults,
  pageSize,
  onPageChange,
  onPageSizeChange,
  evaluationByVersion,
  evaluationLoadingVersion,
  evaluationError,
}: {
  batch: ScreenerBatchRecord | null;
  batchResultCount: number;
  loading: boolean;
  error: string | null;
  results: ScreenerSymbolResult[];
  filteredResults: ScreenerSymbolResult[];
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
  filters: ResultFilters;
  onUpdateFilter: <K extends keyof ResultFilters>(
    key: K,
    value: ResultFilters[K],
  ) => void;
  currentPage: number;
  totalPages: number;
  totalResults: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  evaluationByVersion: Record<string, ModelEvaluationResponse>;
  evaluationLoadingVersion: string | null;
  evaluationError: string | null;
}) {
  const ruleVersions = [
    ...new Set(filteredResults.map((item) => item.rule_version).filter(Boolean)),
  ];
  const bucketSummary: Record<ScreenerListType, number> = {
    READY_TO_BUY: 0,
    WATCH_PULLBACK: 0,
    WATCH_BREAKOUT: 0,
    RESEARCH_ONLY: 0,
    AVOID: 0,
  };
  for (const item of filteredResults) {
    bucketSummary[item.list_type] += 1;
  }

  return (
    <SectionCard
      title="结果"
      description="结果列表始终带着方案上下文展示，不再只给出一串脱离方案的股票。"
    >
      <div className="space-y-4">
        {loading ? (
          <StatusBlock
            title="加载中"
            description="正在读取当前方案最近一次运行结果..."
          />
        ) : null}
        {error ? <StatusBlock title="结果加载失败" description={error} tone="error" /> : null}
        {!loading && !error && !batch ? (
          <StatusBlock
            title="还没有可查看的批次结果"
            description="先运行当前方案，或到下方反馈区选择一条已有历史批次，结果区才会出现候选列表。"
          />
        ) : null}

        {batch ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <ScreenerMetric label="批次" value={batch.batch_id} />
              <ScreenerMetric label="方案名称" value={batch.scheme_name ?? "-"} />
              <ScreenerMetric label="方案版本" value={batch.scheme_version ?? "-"} />
              <ScreenerMetric label="运行状态" value={formatLabel(batch.status)} />
              <ScreenerMetric
                label="完成时间"
                value={formatDateTime(batch.finished_at ?? batch.started_at)}
              />
            </div>

            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-900">
              当前结果区展示的是批次 <span className="font-semibold">{batch.batch_id}</span>{" "}
              的候选列表。若要切换到其他历史运行，请到下方反馈区点击对应批次。
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <ScreenerMetric
                label="当前筛选命中"
                value={String(filteredResults.length)}
              />
              <ScreenerMetric
                label="批次原始候选"
                value={String(batchResultCount)}
              />
              <ScreenerMetric
                label="当前展开股票"
                value={selectedSymbol ?? "未选择"}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <ScreenerMetric
                label={formatListType("READY_TO_BUY")}
                value={String(bucketSummary.READY_TO_BUY)}
              />
              <ScreenerMetric
                label={formatListType("WATCH_PULLBACK")}
                value={String(bucketSummary.WATCH_PULLBACK)}
              />
              <ScreenerMetric
                label={formatListType("WATCH_BREAKOUT")}
                value={String(bucketSummary.WATCH_BREAKOUT)}
              />
              <ScreenerMetric
                label={formatListType("RESEARCH_ONLY")}
                value={String(bucketSummary.RESEARCH_ONLY)}
              />
              <ScreenerMetric
                label={formatListType("AVOID")}
                value={String(bucketSummary.AVOID)}
              />
            </div>
          </>
        ) : null}

        {batch?.warning_messages.length ? (
          <StatusBlock
            title="批次提示"
            description={batch.warning_messages.join("；")}
          />
        ) : null}
        {batch?.failure_reason ? (
          <StatusBlock
            title="批次失败说明"
            description={batch.failure_reason}
            tone="error"
          />
        ) : null}

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-900">结果筛选</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <ScreenerField
              label="股票（代码或名称）"
              value={filters.symbolQuery}
              onChange={(value) => onUpdateFilter("symbolQuery", value)}
            />
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">分桶</span>
              <select
                value={filters.listType}
                onChange={(event) =>
                  onUpdateFilter(
                    "listType",
                    event.target.value as ResultFilters["listType"],
                  )
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="ALL">全部</option>
                <option value="READY_TO_BUY">{formatListType("READY_TO_BUY")}</option>
                <option value="WATCH_PULLBACK">{formatListType("WATCH_PULLBACK")}</option>
                <option value="WATCH_BREAKOUT">{formatListType("WATCH_BREAKOUT")}</option>
                <option value="RESEARCH_ONLY">{formatListType("RESEARCH_ONLY")}</option>
                <option value="AVOID">{formatListType("AVOID")}</option>
              </select>
            </label>
            <ScreenerField
              label="评分下限"
              value={filters.minScore}
              onChange={(value) => onUpdateFilter("minScore", value)}
            />
            <ScreenerField
              label="评分上限"
              value={filters.maxScore}
              onChange={(value) => onUpdateFilter("maxScore", value)}
            />
            <ScreenerField
              label="简述关键词"
              value={filters.reasonQuery}
              onChange={(value) => onUpdateFilter("reasonQuery", value)}
            />
            <ScreenerField
              label="计算时间（起）"
              type="date"
              value={filters.calculatedFrom}
              onChange={(value) => onUpdateFilter("calculatedFrom", value)}
            />
            <ScreenerField
              label="计算时间（止）"
              type="date"
              value={filters.calculatedTo}
              onChange={(value) => onUpdateFilter("calculatedTo", value)}
            />
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">规则版本</span>
              <select
                value={filters.ruleVersion}
                onChange={(event) => onUpdateFilter("ruleVersion", event.target.value)}
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="">全部</option>
                {ruleVersions.map((version) => (
                  <option key={version} value={version}>
                    {version}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <BatchPagination
          totalResults={totalResults}
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />

        <BatchResultTable
          results={results}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={onSelectSymbol}
          evaluationByVersion={evaluationByVersion}
          evaluationLoadingVersion={evaluationLoadingVersion}
          evaluationError={evaluationError}
        />
      </div>
    </SectionCard>
  );
}

function BatchPagination({
  totalResults,
  currentPage,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  totalResults: number;
  currentPage: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const start = totalResults === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalResults);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-700">
          显示第 {start}-{end} 条，共 {totalResults} 条
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            每页
            <select
              value={String(pageSize)}
              onChange={(event) => onPageSizeChange(Number.parseInt(event.target.value, 10))}
              className="min-h-9 rounded-xl border border-slate-300 bg-white px-2 text-sm text-slate-900"
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            条
          </label>
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            上一页
          </button>
          <span className="text-sm text-slate-700">
            第 {currentPage}/{totalPages} 页
          </span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage >= totalPages}
            className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}

function BatchResultTable({
  results,
  selectedSymbol,
  onSelectSymbol,
  evaluationByVersion,
  evaluationLoadingVersion,
  evaluationError,
}: {
  results: ScreenerSymbolResult[];
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
  evaluationByVersion: Record<string, ModelEvaluationResponse>;
  evaluationLoadingVersion: string | null;
  evaluationError: string | null;
}) {
  if (!results.length) {
    return (
      <StatusBlock
        title="没有匹配结果"
        description="当前方案最近运行暂无候选，或者筛选条件已经把结果全部过滤掉了。"
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-700">
          <tr>
            <th className="px-4 py-3">股票</th>
            <th className="px-4 py-3">方案版本</th>
            <th className="px-4 py-3">分桶</th>
            <th className="px-4 py-3">评分</th>
            <th className="px-4 py-3">预测分</th>
            <th className="px-4 py-3">简述</th>
            <th className="px-4 py-3">计算时间</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item) => {
            const isSelected = item.symbol === selectedSymbol;
            const modelVersion = item.predictive_model_version ?? null;
            const evaluation = modelVersion ? evaluationByVersion[modelVersion] ?? null : null;
            const evaluationLoading =
              modelVersion !== null && evaluationLoadingVersion === modelVersion;

            return (
              <Fragment key={`${item.symbol}-${item.calculated_at}`}>
                <tr
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectSymbol(item.symbol)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectSymbol(item.symbol);
                    }
                  }}
                  className={
                    isSelected
                      ? "cursor-pointer border-t border-slate-200 bg-emerald-50"
                      : "cursor-pointer border-t border-slate-200 hover:bg-slate-50"
                  }
                >
                  <td className="px-4 py-3 font-semibold text-emerald-700">
                    {item.symbol}
                    <span className="ml-2 text-slate-900">{item.name}</span>
                  </td>
                  <td className="px-4 py-3">{item.scheme_version ?? "-"}</td>
                  <td className="px-4 py-3">{formatListType(item.list_type)}</td>
                  <td className="px-4 py-3">{formatScore(item.screener_score)}</td>
                  <td className="px-4 py-3">
                    {item.predictive_score === null || item.predictive_score === undefined
                      ? "-"
                      : formatScore(item.predictive_score)}
                  </td>
                  <td className="px-4 py-3">{item.short_reason}</td>
                  <td className="px-4 py-3">{formatDateTime(item.calculated_at)}</td>
                </tr>
                {isSelected ? (
                  <tr className="border-t border-slate-200 bg-white">
                    <td className="px-4 py-4" colSpan={7}>
                      <BatchResultDetail
                        result={item}
                        evaluation={evaluation}
                        evaluationLoading={evaluationLoading}
                        evaluationError={evaluationError}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BatchResultDetail({
  result,
  evaluation,
  evaluationLoading,
  evaluationError,
}: {
  result: ScreenerSymbolResult;
  evaluation: ModelEvaluationResponse | null;
  evaluationLoading: boolean;
  evaluationError: string | null;
}) {
  const hasPredictiveModel = Boolean(result.predictive_model_version);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-base font-semibold text-slate-950">
            {result.name}（{result.symbol}）
          </h4>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            {result.headline_verdict ?? result.short_reason}
          </p>
        </div>
        <Link
          href={`/stocks/${encodeURIComponent(result.symbol)}`}
          className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800"
        >
          打开单票页
        </Link>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <ScreenerMetric label="方案名称" value={result.scheme_name ?? "-"} />
        <ScreenerMetric label="方案版本" value={result.scheme_version ?? "-"} />
        <ScreenerMetric label="分桶" value={formatListType(result.list_type)} />
        <ScreenerMetric label="评分" value={formatScore(result.screener_score)} />
        <ScreenerMetric label="趋势状态" value={formatLabel(result.trend_state)} />
        <ScreenerMetric
          label="当前动作"
          value={result.action_now ? formatDecisionBriefAction(result.action_now) : "-"}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ScreenerMetric label="行情质量" value={formatLabel(result.bars_quality ?? "-")} />
        <ScreenerMetric label="财务质量" value={formatLabel(result.financial_quality ?? "-")} />
        <ScreenerMetric
          label="公告质量"
          value={formatLabel(result.announcement_quality ?? "-")}
        />
        <ScreenerMetric
          label="质量折损"
          value={result.quality_penalty_applied ? "已应用" : "未应用"}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <ScreenerMetric
          label="预测分"
          value={
            result.predictive_score === null || result.predictive_score === undefined
              ? "-"
              : formatScore(result.predictive_score)
          }
        />
        <ScreenerMetric
          label="预测分解释"
          value={formatPredictiveScoreLevel(result.predictive_score)}
        />
        <ScreenerMetric
          label="预测置信度"
          value={formatRatioPercent(result.predictive_confidence)}
        />
        <ScreenerMetric
          label="置信度等级"
          value={formatPredictiveConfidenceLevel(result.predictive_confidence)}
        />
        <ScreenerMetric
          label="预测模型版本"
          value={result.predictive_model_version ?? "-"}
        />
      </div>

      {evaluationLoading ? (
        <StatusBlock
          title="模型版本建议"
          description="正在加载该模型版本的评估建议..."
        />
      ) : null}
      {!hasPredictiveModel ? (
        <StatusBlock
          title="暂无模型评估建议"
          description="这条候选结果还没有绑定预测模型版本，因此不会展示模型评估建议。当前仍可先使用规则侧结果与质量信息进行判断。"
        />
      ) : null}
      {evaluation ? (
        <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">模型版本建议</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ScreenerMetric
              label="建议动作"
              value={formatModelRecommendation(evaluation.recommendation?.recommendation)}
            />
            <ScreenerMetric
              label="建议版本"
              value={evaluation.recommendation?.recommended_model_version ?? "-"}
            />
            <ScreenerMetric
              label="评估质量分"
              value={formatRatioPercent(evaluation.metrics.quality_score)}
            />
            <ScreenerMetric
              label="回测胜率"
              value={formatRatioPercent(evaluation.metrics.screener_win_rate)}
            />
          </div>
          {evaluation.recommendation ? (
            <p className="mt-3 text-sm leading-6 text-slate-700">
              {evaluation.recommendation.reason}
            </p>
          ) : null}
        </div>
      ) : null}
      {evaluationError ? (
        <StatusBlock
          title="模型评估建议加载失败"
          description={evaluationError}
          tone="error"
        />
      ) : null}

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ScreenerMetric label="支撑位" value={formatPrice(result.support_level)} />
        <ScreenerMetric label="压力位" value={formatPrice(result.resistance_level)} />
        <ScreenerMetric label="评分配置" value={result.scoring_profile_name ?? "-"} />
        <ScreenerMetric
          label="质量门控配置"
          value={result.quality_gate_profile_name ?? "-"}
        />
      </div>

      <div className="mt-4 space-y-3">
        <ScreenerMetric label="规则版本" value={result.rule_version} />
        <ScreenerMetric label="规则说明" value={result.rule_summary} />
        {result.quality_note ? (
          <StatusBlock title="数据质量影响说明" description={result.quality_note} />
        ) : null}
        <ScreenerStringPanel title="启用因子组" items={result.selected_factor_groups ?? []} />
        <ScreenerStringPanel title="证据提示" items={result.evidence_hints} />
        {result.fail_reason ? (
          <StatusBlock title="失败说明" description={result.fail_reason} tone="error" />
        ) : null}
      </div>
    </div>
  );
}

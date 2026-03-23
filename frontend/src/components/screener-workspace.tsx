"use client";

import Link from "next/link";
import { useState } from "react";

import { getDeepScreenerRun, getScreenerRun } from "@/lib/api";
import { formatDate, formatPrice, formatRange, formatScore } from "@/lib/format";
import type {
  DeepScreenerCandidate,
  DeepScreenerRunResponse,
  ScreenerCandidate,
  ScreenerRunResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";

type FormState = {
  maxSymbols: string;
  topN: string;
};

type DeepFormState = FormState & {
  deepTopK: string;
};

const INITIAL_FORM_STATE: FormState = {
  maxSymbols: "50",
  topN: "10",
};

const INITIAL_DEEP_FORM_STATE: DeepFormState = {
  maxSymbols: "50",
  topN: "10",
  deepTopK: "5",
};

export function ScreenerWorkspace() {
  const [initialForm, setInitialForm] = useState<FormState>(INITIAL_FORM_STATE);
  const [deepForm, setDeepForm] = useState<DeepFormState>(INITIAL_DEEP_FORM_STATE);
  const [initialRun, setInitialRun] = useState<ScreenerRunResponse | null>(null);
  const [deepRun, setDeepRun] = useState<DeepScreenerRunResponse | null>(null);
  const [initialLoading, setInitialLoading] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [initialError, setInitialError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);

  const handleInitialSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setInitialLoading(true);
    setInitialError(null);

    try {
      const response = await getScreenerRun({
        maxSymbols: parseOptionalInteger(initialForm.maxSymbols),
        topN: parseOptionalInteger(initialForm.topN),
      });
      setInitialRun(response);
    } catch (error) {
      setInitialError(getErrorMessage(error));
    } finally {
      setInitialLoading(false);
    }
  };

  const handleDeepSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDeepLoading(true);
    setDeepError(null);

    try {
      const response = await getDeepScreenerRun({
        maxSymbols: parseOptionalInteger(deepForm.maxSymbols),
        topN: parseOptionalInteger(deepForm.topN),
        deepTopK: parseOptionalInteger(deepForm.deepTopK),
      });
      setDeepRun(response);
    } catch (error) {
      setDeepError(getErrorMessage(error));
    } finally {
      setDeepLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="规则初筛"
        description="调用 /screener/run，查看当前全市场规则初筛结果。"
      >
        <form className="grid gap-4 md:grid-cols-4" onSubmit={handleInitialSubmit}>
          <Field
            label="max_symbols"
            value={initialForm.maxSymbols}
            onChange={(value) =>
              setInitialForm((current) => ({ ...current, maxSymbols: value }))
            }
          />
          <Field
            label="top_n"
            value={initialForm.topN}
            onChange={(value) =>
              setInitialForm((current) => ({ ...current, topN: value }))
            }
          />
          <div className="md:col-span-2 flex items-end">
            <button
              type="submit"
              disabled={initialLoading}
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-emerald-400"
            >
              {initialLoading ? "初筛运行中..." : "运行初筛"}
            </button>
          </div>
        </form>

        <div className="mt-5 space-y-4">
          {initialError ? (
            <StatusBlock title="初筛请求失败" description={initialError} tone="error" />
          ) : null}
          {!initialRun && !initialLoading && !initialError ? (
            <StatusBlock
              title="等待运行"
              description="输入参数后运行初筛，即可看到 BUY_CANDIDATE、WATCHLIST 和 AVOID 三类结果。"
            />
          ) : null}
          {initialLoading ? (
            <StatusBlock
              title="正在加载"
              description="正在请求初筛结果，请稍候。"
            />
          ) : null}
          {initialRun ? <ScreenerRunResult run={initialRun} /> : null}
        </div>
      </SectionCard>

      <SectionCard
        title="深筛聚合"
        description="调用 /screener/deep-run，聚合初筛、研究和策略输出。"
      >
        <form className="grid gap-4 md:grid-cols-4" onSubmit={handleDeepSubmit}>
          <Field
            label="max_symbols"
            value={deepForm.maxSymbols}
            onChange={(value) =>
              setDeepForm((current) => ({ ...current, maxSymbols: value }))
            }
          />
          <Field
            label="top_n"
            value={deepForm.topN}
            onChange={(value) =>
              setDeepForm((current) => ({ ...current, topN: value }))
            }
          />
          <Field
            label="deep_top_k"
            value={deepForm.deepTopK}
            onChange={(value) =>
              setDeepForm((current) => ({ ...current, deepTopK: value }))
            }
          />
          <div className="flex items-end">
            <button
              type="submit"
              disabled={deepLoading}
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {deepLoading ? "深筛运行中..." : "运行深筛"}
            </button>
          </div>
        </form>

        <div className="mt-5 space-y-4">
          {deepError ? (
            <StatusBlock title="深筛请求失败" description={deepError} tone="error" />
          ) : null}
          {!deepRun && !deepLoading && !deepError ? (
            <StatusBlock
              title="等待运行"
              description="深筛会先用初筛结果挑出候选，再聚合研究与策略输出。"
            />
          ) : null}
          {deepLoading ? (
            <StatusBlock
              title="正在加载"
              description="正在请求深筛结果，请稍候。"
            />
          ) : null}
          {deepRun ? <DeepScreenerRunResult run={deepRun} /> : null}
        </div>
      </SectionCard>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode="numeric"
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function ScreenerRunResult({ run }: { run: ScreenerRunResponse }) {
  return (
    <div className="space-y-4">
      <SummaryGrid
        items={[
          { label: "交易日", value: formatDate(run.as_of_date) },
          { label: "股票池总数", value: String(run.total_symbols) },
          { label: "实际扫描数", value: String(run.scanned_symbols) },
        ]}
      />
      <CandidateGroup
        title="BUY_CANDIDATE"
        candidates={run.buy_candidates}
        emptyText="当前没有进入买入候选的股票。"
      />
      <CandidateGroup
        title="WATCHLIST"
        candidates={run.watch_candidates}
        emptyText="当前没有进入观察池的股票。"
      />
      <CandidateGroup
        title="AVOID"
        candidates={run.avoid_candidates}
        emptyText="当前没有落入回避列表的股票。"
      />
    </div>
  );
}

function DeepScreenerRunResult({ run }: { run: DeepScreenerRunResponse }) {
  return (
    <div className="space-y-4">
      <SummaryGrid
        items={[
          { label: "交易日", value: formatDate(run.as_of_date) },
          { label: "股票池总数", value: String(run.total_symbols) },
          { label: "实际扫描数", value: String(run.scanned_symbols) },
          { label: "深筛候选数", value: String(run.selected_for_deep_review) },
        ]}
      />
      {run.deep_candidates.length === 0 ? (
        <StatusBlock
          title="暂无深筛结果"
          description="本次运行没有形成可展示的深筛候选，可能是候选为空或个别股票在聚合过程中被跳过。"
        />
      ) : (
        <div className="grid gap-4">
          {run.deep_candidates.map((candidate) => (
            <DeepCandidateCard key={candidate.symbol} candidate={candidate} />
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateGroup({
  title,
  candidates,
  emptyText,
}: {
  title: string;
  candidates: ScreenerCandidate[];
  emptyText: string;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {candidates.length === 0 ? (
        <StatusBlock title="暂无结果" description={emptyText} />
      ) : (
        <div className="grid gap-4">
          {candidates.map((candidate) => (
            <CandidateCard key={candidate.symbol} candidate={candidate} />
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: ScreenerCandidate }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-semibold text-slate-950">
              {candidate.name}
            </h4>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">
              {candidate.symbol}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {candidate.short_reason}
          </p>
        </div>
        <Link
          href={`/stocks/${encodeURIComponent(candidate.symbol)}`}
          className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800"
        >
          查看单票
        </Link>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="排名" value={`#${candidate.rank}`} />
        <Metric label="评分" value={formatScore(candidate.screener_score)} />
        <Metric label="趋势" value={`${candidate.trend_state} / ${candidate.trend_score}`} />
        <Metric label="收盘价" value={formatPrice(candidate.latest_close)} />
        <Metric label="支撑位" value={formatPrice(candidate.support_level)} />
        <Metric label="压力位" value={formatPrice(candidate.resistance_level)} />
      </div>
    </article>
  );
}

function DeepCandidateCard({
  candidate,
}: {
  candidate: DeepScreenerCandidate;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-semibold text-slate-950">
              {candidate.name}
            </h4>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">
              {candidate.symbol}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{candidate.thesis}</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            {candidate.short_reason}
          </p>
        </div>
        <Link
          href={`/stocks/${encodeURIComponent(candidate.symbol)}`}
          className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800"
        >
          查看单票
        </Link>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Metric label="优先级" value={formatScore(candidate.priority_score)} />
        <Metric label="初筛分数" value={formatScore(candidate.base_screener_score)} />
        <Metric label="研究结论" value={`${candidate.research_action} / ${candidate.research_overall_score}`} />
        <Metric label="策略类型" value={candidate.strategy_type} />
        <Metric label="入场区间" value={formatRange(candidate.ideal_entry_range)} />
        <Metric label="止损价" value={formatPrice(candidate.stop_loss_price)} />
        <Metric label="止盈区间" value={formatRange(candidate.take_profit_range)} />
        <Metric label="复核周期" value={candidate.review_timeframe} />
      </div>
    </article>
  );
}

function SummaryGrid({
  items,
}: {
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <Metric key={item.label} label={item.label} value={item.value} />
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function parseOptionalInteger(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number.parseInt(normalized, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }

  return parsed;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "发生未知错误，请稍后重试。";
}

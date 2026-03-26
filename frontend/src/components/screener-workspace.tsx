"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  getDataRefreshStatus,
  getDeepScreenerRun,
  getScreenerRun,
  startDataRefresh,
} from "@/lib/api";
import {
  formatAction,
  formatDate,
  formatDateTime,
  formatDecisionBriefAction,
  formatListType,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DataRefreshStatus,
  DecisionBriefActionNow,
  DeepScreenerCandidate,
  DeepScreenerRunResponse,
  ScreenerCandidate,
  ScreenerRunResponse,
  ScreenerListType,
} from "@/types/api";

import { DeepReviewWorkflowPanel } from "./deep-review-workflow-panel";
import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";

type FormState = {
  maxSymbols: string;
  topN: string;
};

type DeepFormState = FormState & {
  deepTopK: string;
};

type RefreshFormState = {
  maxSymbols: string;
};

const INITIAL_FORM_STATE: FormState = {
  maxSymbols: "50",
  topN: "20",
};

const INITIAL_DEEP_FORM_STATE: DeepFormState = {
  maxSymbols: "50",
  topN: "20",
  deepTopK: "8",
};

const INITIAL_REFRESH_FORM_STATE: RefreshFormState = {
  maxSymbols: "",
};

const REFRESH_POLL_INTERVAL_MS = 3_000;

const V2_BUCKETS: Array<{
  key:
    | "ready_to_buy_candidates"
    | "watch_pullback_candidates"
    | "watch_breakout_candidates"
    | "research_only_candidates"
    | "avoid_candidates";
  listType: ScreenerListType;
}> = [
  { key: "ready_to_buy_candidates", listType: "READY_TO_BUY" },
  { key: "watch_pullback_candidates", listType: "WATCH_PULLBACK" },
  { key: "watch_breakout_candidates", listType: "WATCH_BREAKOUT" },
  { key: "research_only_candidates", listType: "RESEARCH_ONLY" },
  { key: "avoid_candidates", listType: "AVOID" },
];

export function ScreenerWorkspace() {
  const [refreshForm, setRefreshForm] = useState<RefreshFormState>(
    INITIAL_REFRESH_FORM_STATE,
  );
  const [refreshStatus, setRefreshStatus] = useState<DataRefreshStatus | null>(null);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [refreshStatusLoading, setRefreshStatusLoading] = useState(true);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const [initialForm, setInitialForm] = useState<FormState>(INITIAL_FORM_STATE);
  const [deepForm, setDeepForm] = useState<DeepFormState>(INITIAL_DEEP_FORM_STATE);
  const [initialRun, setInitialRun] = useState<ScreenerRunResponse | null>(null);
  const [deepRun, setDeepRun] = useState<DeepScreenerRunResponse | null>(null);
  const [initialLoading, setInitialLoading] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [initialError, setInitialError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);

  const loadRefreshStatus = useCallback(async (silent = false) => {
    if (!silent) {
      setRefreshStatusLoading(true);
    }

    try {
      const response = await getDataRefreshStatus();
      setRefreshStatus(response);
      setRefreshError(null);
    } catch (error) {
      setRefreshError(getErrorMessage(error));
    } finally {
      if (!silent) {
        setRefreshStatusLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadRefreshStatus();
  }, [loadRefreshStatus]);

  useEffect(() => {
    if (!refreshStatus?.is_running) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadRefreshStatus(true);
    }, REFRESH_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [loadRefreshStatus, refreshStatus?.is_running]);

  const handleRefreshSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    setRefreshLoading(true);
    setRefreshError(null);

    try {
      const response = await startDataRefresh({
        maxSymbols: parseOptionalInteger(refreshForm.maxSymbols),
      });
      setRefreshStatus(response);
    } catch (error) {
      setRefreshError(getErrorMessage(error));
    } finally {
      setRefreshLoading(false);
    }
  };

  const handleInitialSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
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
        title="数据补全"
        description="先刷新本地股票池和基础数据，再运行规则初筛或 deep review，可以明显降低空结果和旧数据问题。"
      >
        <form className="grid gap-4 md:grid-cols-4" onSubmit={handleRefreshSubmit}>
          <Field
            label="max_symbols"
            value={refreshForm.maxSymbols}
            placeholder="留空表示按默认范围执行"
            onChange={(value) =>
              setRefreshForm((current) => ({ ...current, maxSymbols: value }))
            }
          />
          <div className="md:col-span-3 flex flex-wrap items-end gap-3">
            <button
              type="submit"
              disabled={refreshLoading || refreshStatus?.is_running === true}
              className="min-h-11 rounded-2xl bg-amber-600 px-5 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-amber-300"
            >
              {refreshLoading
                ? "正在启动数据补全..."
                : refreshStatus?.is_running
                  ? "数据补全执行中"
                  : "开始数据补全"}
            </button>
            <button
              type="button"
              onClick={() => void loadRefreshStatus()}
              disabled={refreshStatusLoading}
              className="min-h-11 rounded-2xl border border-slate-300 px-5 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              刷新状态
            </button>
          </div>
        </form>

        <div className="mt-5 space-y-4">
          {refreshError ? (
            <StatusBlock title="数据补全请求失败" description={refreshError} tone="error" />
          ) : null}
          {refreshStatusLoading && !refreshStatus ? (
            <StatusBlock
              title="正在加载"
              description="正在读取最近一次数据补全任务状态。"
            />
          ) : null}
          {!refreshStatusLoading && !refreshStatus && !refreshError ? (
            <StatusBlock
              title="尚未执行"
              description="当前没有读取到数据补全状态，可以直接启动一次补全任务。"
            />
          ) : null}
          {refreshStatus ? <RefreshStatusPanel status={refreshStatus} /> : null}
        </div>
      </SectionCard>

      <SectionCard
        title="初筛结果"
        description="主展示字段使用 v2_list_type；兼容字段 list_type 只保留为兼容说明，不再作为主分桶。"
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
              {initialLoading ? "初筛执行中..." : "运行规则初筛"}
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
              description="输入参数后运行初筛，即可看到 READY_TO_BUY、WATCH_PULLBACK、WATCH_BREAKOUT、RESEARCH_ONLY 和 AVOID 五类结果。"
            />
          ) : null}
          {initialLoading ? (
            <StatusBlock title="正在加载" description="正在请求初筛结果，请稍候。" />
          ) : null}
          {initialRun ? <ScreenerRunResult run={initialRun} /> : null}
        </div>
      </SectionCard>

      <SectionCard
        title="深筛结果"
        description="这里展示 deep screener 的聚合结果，适合从初筛候选继续收敛到重点研究名单。"
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
              {deepLoading ? "深筛执行中..." : "运行深筛"}
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
              description="深筛会先缩小候选范围，再聚合研究与策略结果，适合挑出少量优先跟踪标的。"
            />
          ) : null}
          {deepLoading ? (
            <StatusBlock title="正在加载" description="正在请求深筛结果，请稍候。" />
          ) : null}
          {deepRun ? <DeepScreenerRunResult run={deepRun} /> : null}
        </div>
      </SectionCard>

      <DeepReviewWorkflowPanel />
    </div>
  );
}

function RefreshStatusPanel({ status }: { status: DataRefreshStatus }) {
  const tone = status.status === "failed" ? "error" : "default";
  const title = resolveRefreshTitle(status);

  return (
    <div className="space-y-4">
      <StatusBlock title={title} description={status.message} tone={tone} />
      <SummaryGrid
        items={[
          { label: "任务状态", value: status.status },
          { label: "股票池总数", value: String(status.universe_count) },
          { label: "本次目标数", value: String(status.total_symbols) },
          { label: "已处理", value: String(status.processed_symbols) },
          { label: "成功", value: String(status.succeeded_symbols) },
          { label: "失败", value: String(status.failed_symbols) },
          { label: "当前股票", value: status.current_symbol ?? "-" },
          { label: "开始时间", value: formatDateTime(status.started_at) },
          { label: "结束时间", value: formatDateTime(status.finished_at) },
        ]}
      />
      <SummaryGrid
        items={[
          { label: "股票池刷新", value: status.universe_updated ? "已完成" : "未执行" },
          { label: "基础信息", value: String(status.profiles_updated) },
          { label: "日线补全", value: String(status.daily_bars_updated) },
          { label: "日线条数", value: String(status.daily_bars_synced_rows) },
          { label: "财务摘要", value: String(status.financial_summaries_updated) },
          { label: "近期公告", value: String(status.announcements_updated) },
          { label: "公告条数", value: String(status.announcements_synced_items) },
          { label: "基础信息失败", value: String(status.profile_step_failures) },
          { label: "日线失败", value: String(status.daily_bar_step_failures) },
          { label: "财务失败", value: String(status.financial_step_failures) },
          { label: "公告失败", value: String(status.announcement_step_failures) },
        ]}
      />
      {status.recent_warnings.length > 0 ? (
        <StringPanel
          title="最近警告"
          items={status.recent_warnings}
          tone="warning"
        />
      ) : null}
      {status.recent_errors.length > 0 ? (
        <StringPanel
          title="最近错误"
          items={status.recent_errors}
          tone="error"
        />
      ) : null}
    </div>
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
          { label: "兼容 BUY_CANDIDATE", value: String(run.buy_candidates.length) },
          { label: "兼容 WATCHLIST", value: String(run.watch_candidates.length) },
          { label: "兼容 AVOID", value: String(run.avoid_candidates.length) },
        ]}
      />
      <StatusBlock
        title="分桶说明"
        description="主展示字段为 v2_list_type。卡片里会同时展示旧字段 list_type，仅用于兼容和排查。"
      />
      {V2_BUCKETS.map((bucket) => (
        <CandidateGroup
          key={bucket.key}
          title={bucket.listType}
          candidates={run[bucket.key]}
          emptyText={`当前没有 ${bucket.listType} 分桶的候选。`}
        />
      ))}
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
          description="本次深筛没有形成可展示的候选，可能是初筛为空，或候选在聚合阶段被跳过。"
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
  title: ScreenerListType;
  candidates: ScreenerCandidate[];
  emptyText: string;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-slate-900">
        {title} · {formatListType(title)}
      </h3>
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
  const actionNow = getCandidateActionNow(candidate.v2_list_type);
  const headlineVerdict = getCandidateHeadlineVerdict(candidate);

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
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              主展示：{candidate.v2_list_type}
            </span>
            <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700">
              兼容：{candidate.list_type}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold leading-6 text-slate-900">
            {headlineVerdict}
          </p>
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
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <Metric label="褰撳墠鍔ㄤ綔" value={formatDecisionBriefAction(actionNow)} />
        <Metric label="排名" value={`#${candidate.rank}`} />
        <Metric label="总分" value={formatScore(candidate.screener_score)} />
        <Metric label="alpha" value={formatScore(candidate.alpha_score)} />
        <Metric label="trigger" value={formatScore(candidate.trigger_score)} />
        <Metric label="risk" value={formatScore(candidate.risk_score)} />
        <Metric label="最新收盘" value={formatPrice(candidate.latest_close)} />
        <Metric label="支撑位" value={formatPrice(candidate.support_level)} />
        <Metric label="压力位" value={formatPrice(candidate.resistance_level)} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <StringPanel
          title="主要正向因子"
          items={candidate.top_positive_factors}
          emptyText="当前没有主要正向因子。"
        />
        <StringPanel
          title="主要负向因子"
          items={candidate.top_negative_factors}
          emptyText="当前没有主要负向因子。"
        />
        <StringPanel
          title="风险提示"
          items={candidate.risk_notes}
          emptyText="当前没有额外风险提示。"
        />
      </div>
    </article>
  );
}

function getCandidateActionNow(listType: ScreenerListType): DecisionBriefActionNow {
  if (listType === "READY_TO_BUY") {
    return "BUY_NOW";
  }
  if (listType === "WATCH_PULLBACK") {
    return "WAIT_PULLBACK";
  }
  if (listType === "WATCH_BREAKOUT") {
    return "WAIT_BREAKOUT";
  }
  if (listType === "RESEARCH_ONLY") {
    return "RESEARCH_ONLY";
  }
  return "AVOID";
}

function getCandidateHeadlineVerdict(candidate: ScreenerCandidate): string {
  if (candidate.v2_list_type === "READY_TO_BUY") {
    return `${candidate.name} 宸茶繘鍏ラ噸鐐硅瀵熺殑鎵ц绐楀彛锛屼絾浠嶈鎸夌邯寰嬫帶鍒朵粨浣嶃€?`;
  }
  if (candidate.v2_list_type === "WATCH_PULLBACK") {
    return `${candidate.name} 鏂瑰悜涓嶅樊锛屼絾鏇撮€傚悎绛夊洖韪╃‘璁ゃ€?`;
  }
  if (candidate.v2_list_type === "WATCH_BREAKOUT") {
    return `${candidate.name} 鍏堢瓑绐佺牬纭锛屽啀鍐冲畾鏄惁鍙備笌銆?`;
  }
  if (candidate.v2_list_type === "RESEARCH_ONLY") {
    return `${candidate.name} 褰撳墠鏇撮€傚悎缁х画鐮旂┒锛屼笉鐢ㄦ€ョ潃涓嬪崟銆?`;
  }
  return `${candidate.name} 褰撳墠涓嶅湪鍚堥€備氦鏄撶獥鍙ｏ紝鍏堝洖閬裤€?`;
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
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <Metric label="优先级" value={formatScore(candidate.priority_score)} />
        <Metric label="初筛总分" value={formatScore(candidate.base_screener_score)} />
        <Metric label="研究动作" value={formatAction(candidate.research_action)} />
        <Metric
          label="研究分 / 置信度"
          value={`${candidate.research_overall_score} / ${candidate.research_confidence}`}
        />
        <Metric label="策略动作" value={formatAction(candidate.strategy_action)} />
        <Metric label="策略类型" value={candidate.strategy_type} />
        <Metric label="入场区间" value={formatRange(candidate.ideal_entry_range)} />
        <Metric label="止损价" value={formatPrice(candidate.stop_loss_price)} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Metric label="止盈区间" value={formatRange(candidate.take_profit_range)} />
        <Metric label="复核周期" value={candidate.review_timeframe} />
      </div>
    </article>
  );
}

function StringPanel({
  title,
  items,
  emptyText,
  tone = "default",
}: {
  title: string;
  items: string[];
  emptyText?: string;
  tone?: "default" | "warning" | "error";
}) {
  const panelClassName =
    tone === "warning"
      ? "border-amber-200 bg-amber-50"
      : tone === "error"
        ? "border-rose-200 bg-rose-50"
        : "border-slate-200 bg-slate-50";

  const textClassName =
    tone === "warning"
      ? "text-amber-800"
      : tone === "error"
        ? "text-rose-800"
        : "text-slate-700";

  return (
    <div className={`rounded-2xl border p-4 ${panelClassName}`}>
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className={`mt-3 text-sm leading-6 ${textClassName}`}>
          {emptyText ?? "当前没有可展示内容。"}
        </p>
      ) : (
        <ul className={`mt-3 space-y-2 text-sm leading-6 ${textClassName}`}>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode="numeric"
        placeholder={placeholder}
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
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

function resolveRefreshTitle(status: DataRefreshStatus): string {
  if (status.status === "running") {
    return "数据补全执行中";
  }
  if (status.status === "completed") {
    return "数据补全已完成";
  }
  if (status.status === "failed") {
    return "数据补全失败";
  }
  return "尚未执行数据补全";
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

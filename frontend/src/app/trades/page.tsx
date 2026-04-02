"use client";

import { useEffect, useMemo, useState } from "react";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";
import { createTradeFromCurrentDecision, listTrades, normalizeSymbolInput } from "@/lib/api";
import {
  formatAction,
  formatDateTime,
  formatRatioPercent,
  formatStrategyAlignment,
  formatTradeReasonType,
  formatTradeSide,
} from "@/lib/format";
import type {
  StrategyAlignment,
  TradeReasonType,
  TradeRecord,
  TradeSide,
} from "@/types/api";

type TradeFormState = {
  symbol: string;
  side: TradeSide;
  reasonType: TradeReasonType;
  strategyAlignment: StrategyAlignment;
  alignmentOverrideReason: string;
  price: string;
  quantity: string;
  note: string;
  useLlm: boolean;
};

type OptionItem = {
  value: string;
  label: string;
};

const INITIAL_FORM: TradeFormState = {
  symbol: "600519.SH",
  side: "SKIP",
  reasonType: "watch_only",
  strategyAlignment: "unknown",
  alignmentOverrideReason: "",
  price: "",
  quantity: "",
  note: "",
  useLlm: false,
};

const SIDE_OPTIONS: OptionItem[] = [
  { value: "SKIP", label: formatTradeSide("SKIP") },
  { value: "BUY", label: formatTradeSide("BUY") },
  { value: "SELL", label: formatTradeSide("SELL") },
  { value: "ADD", label: formatTradeSide("ADD") },
  { value: "REDUCE", label: formatTradeSide("REDUCE") },
];

const REASON_OPTIONS: OptionItem[] = [
  { value: "watch_only", label: formatTradeReasonType("watch_only") },
  { value: "signal_entry", label: formatTradeReasonType("signal_entry") },
  { value: "pullback_entry", label: formatTradeReasonType("pullback_entry") },
  { value: "breakout_entry", label: formatTradeReasonType("breakout_entry") },
  { value: "stop_loss", label: formatTradeReasonType("stop_loss") },
  { value: "take_profit", label: formatTradeReasonType("take_profit") },
  { value: "time_exit", label: formatTradeReasonType("time_exit") },
  { value: "manual_override", label: formatTradeReasonType("manual_override") },
  { value: "skip_due_to_quality", label: formatTradeReasonType("skip_due_to_quality") },
  { value: "skip_due_to_risk", label: formatTradeReasonType("skip_due_to_risk") },
];

const ENTRY_REASON_TYPES: TradeReasonType[] = [
  "signal_entry",
  "pullback_entry",
  "breakout_entry",
];
const EXIT_REASON_TYPES: TradeReasonType[] = ["stop_loss", "take_profit", "time_exit"];
const SKIP_REASON_TYPES: TradeReasonType[] = [
  "watch_only",
  "skip_due_to_quality",
  "skip_due_to_risk",
];

const ALIGNMENT_OVERRIDE_TEMPLATES: string[] = [
  "与原判断存在冲突，基于盘中新信息执行人工覆盖。",
  "按小仓位试错执行，后续若不达预期将快速退出。",
  "当前交易为计划外动作，已明确风险并纳入复盘跟踪。",
];

const ALIGNMENT_OPTIONS: OptionItem[] = [
  { value: "unknown", label: formatStrategyAlignment("unknown") },
  { value: "aligned", label: formatStrategyAlignment("aligned") },
  { value: "partially_aligned", label: formatStrategyAlignment("partially_aligned") },
  { value: "not_aligned", label: formatStrategyAlignment("not_aligned") },
];

export default function TradesPage() {
  const [form, setForm] = useState<TradeFormState>(INITIAL_FORM);
  const [filterSymbol, setFilterSymbol] = useState("");
  const [records, setRecords] = useState<TradeRecord[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const selectedRecord = useMemo(
    () => records.find((item) => item.trade_id === selectedTradeId) ?? null,
    [records, selectedTradeId],
  );
  const isSkipSide = form.side === "SKIP";
  const compatibleReasonOptions = useMemo(() => {
    return REASON_OPTIONS.filter((item) =>
      isReasonTypeCompatible(form.side, item.value as TradeReasonType),
    );
  }, [form.side]);
  const isReasonCompatible = useMemo(() => {
    return isReasonTypeCompatible(form.side, form.reasonType);
  }, [form.reasonType, form.side]);
  const recommendedReasonType = useMemo(() => {
    return defaultReasonTypeForSide(form.side);
  }, [form.side]);
  const tradeSummary = useMemo(() => {
    return records.reduce(
      (summary, item) => {
        summary.total += 1;
        if (item.side === "BUY" || item.side === "ADD") summary.entry += 1;
        if (item.side === "SELL" || item.side === "REDUCE") summary.exit += 1;
        if (item.side === "SKIP") summary.skip += 1;
        return summary;
      },
      { total: 0, entry: 0, exit: 0, skip: 0 },
    );
  }, [records]);

  const refreshList = async (symbol?: string) => {
    setStatus("loading");
    setError(null);
    try {
      const response = await listTrades({
        symbol: symbol ? normalizeSymbolInput(symbol) : undefined,
        limit: 200,
      });
      setRecords(response.items);
      setSelectedTradeId((previous) => {
        if (!response.items.length) return null;
        if (previous && response.items.some((item) => item.trade_id === previous)) {
          return previous;
        }
        return response.items[0].trade_id;
      });
      setStatus("success");
    } catch (cause) {
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "加载交易记录失败，请稍后重试。");
    }
  };

  useEffect(() => {
    void refreshList();
  }, []);

  const handleCreateTrade = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitMessage(null);
    setError(null);
    setSubmitting(true);
    try {
      const effectiveReasonType = isReasonTypeCompatible(form.side, form.reasonType)
        ? form.reasonType
        : defaultReasonTypeForSide(form.side);
      if (effectiveReasonType !== form.reasonType) {
        setForm((previous) => ({
          ...previous,
          reasonType: effectiveReasonType,
        }));
      }

      const symbol = normalizeSymbolInput(form.symbol);
      const payload = {
        symbol,
        use_llm: form.useLlm,
        side: form.side,
        reason_type: effectiveReasonType,
        strategy_alignment: form.strategyAlignment,
        alignment_override_reason: form.alignmentOverrideReason.trim() || undefined,
        note: form.note.trim() || undefined,
      } as const;

      if (form.side !== "SKIP") {
        const price = Number.parseFloat(form.price);
        const quantity = Number.parseInt(form.quantity, 10);
        if (!Number.isFinite(price) || price <= 0) {
          throw new Error("非 SKIP 记录必须填写有效价格。");
        }
        if (!Number.isFinite(quantity) || quantity <= 0) {
          throw new Error("非 SKIP 记录必须填写有效数量。");
        }
        await createTradeFromCurrentDecision({
          ...payload,
          price,
          quantity,
        });
      } else {
        await createTradeFromCurrentDecision(payload);
      }

      setSubmitMessage("交易记录创建成功，已自动关联当前决策快照。");
      await refreshList(filterSymbol || symbol);
    } catch (cause) {
      setError(normalizeTradeSubmitError(cause));
    } finally {
      setSubmitting(false);
    }
  };

  const handleFilterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void refreshList(filterSymbol);
  };

  return (
    <PageShell
      title="交易记录"
      description="优先完成快速记录，再按需补充高级参数，形成“判断 -> 执行”可追溯链路。"
    >
      <SectionCard title="快速记录交易" description="默认自动固化并关联当前决策快照。">
        <form className="grid gap-4 lg:grid-cols-4" onSubmit={handleCreateTrade}>
          <Field
            label="股票代码"
            value={form.symbol}
            onChange={(value) => setForm((previous) => ({ ...previous, symbol: value }))}
          />
          <SelectField
            label="动作"
            value={form.side}
            onChange={(value) =>
              setForm((previous) => {
                const nextSide = value as TradeSide;
                const nextReasonType = isReasonTypeCompatible(nextSide, previous.reasonType)
                  ? previous.reasonType
                  : defaultReasonTypeForSide(nextSide);
                return {
                  ...previous,
                  side: nextSide,
                  reasonType: nextReasonType,
                };
              })
            }
            options={SIDE_OPTIONS}
          />
          {!isSkipSide ? (
            <>
              <Field
                label="价格（必填）"
                value={form.price}
                onChange={(value) => setForm((previous) => ({ ...previous, price: value }))}
              />
              <Field
                label="数量（必填）"
                value={form.quantity}
                onChange={(value) => setForm((previous) => ({ ...previous, quantity: value }))}
              />
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 lg:col-span-2">
              当前动作为“跳过”，无需填写价格和数量。
            </div>
          )}
          <div className="flex items-end">
            <button
              type="submit"
              disabled={submitting}
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
            >
              {submitting ? "提交中..." : "创建交易记录"}
            </button>
          </div>
        </form>
        <details className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-900">
            高级参数（原因类型、对齐策略、人工覆盖、备注）
          </summary>
          <div className="mt-4">
            <StatusBlock
              title="动作与原因类型提示"
              description={`当前动作：${formatTradeSide(form.side)}。推荐原因类型：${formatTradeReasonType(
                recommendedReasonType,
              )}。若你选择了不匹配原因，提交时会自动纠正为推荐值。`}
            />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-4">
            <SelectField
              label="原因类型"
              value={form.reasonType}
              onChange={(value) =>
                setForm((previous) => ({ ...previous, reasonType: value as TradeReasonType }))
              }
              options={compatibleReasonOptions}
            />
            <SelectField
              label="策略对齐"
              value={form.strategyAlignment}
              onChange={(value) =>
                setForm((previous) => ({
                  ...previous,
                  strategyAlignment: value as StrategyAlignment,
                }))
              }
              options={ALIGNMENT_OPTIONS}
            />
            <label className="flex items-end">
              <span className="flex min-h-11 items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.useLlm}
                  onChange={(event) =>
                    setForm((previous) => ({ ...previous, useLlm: event.target.checked }))
                  }
                  className="h-4 w-4 rounded border-slate-300"
                />
                使用 LLM 上下文
              </span>
            </label>
            <Field
              label="人工覆盖原因（可选）"
              value={form.alignmentOverrideReason}
              onChange={(value) =>
                setForm((previous) => ({ ...previous, alignmentOverrideReason: value }))
              }
            />
            <div className="lg:col-span-4 rounded-2xl border border-slate-200 bg-white p-3">
              <p className="text-sm font-medium text-slate-700">覆盖原因模板（可一键填入）</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {ALIGNMENT_OVERRIDE_TEMPLATES.map((template) => (
                  <button
                    key={template}
                    type="button"
                    onClick={() =>
                      setForm((previous) => ({
                        ...previous,
                        alignmentOverrideReason: template,
                      }))
                    }
                    className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-700 transition hover:bg-slate-100"
                  >
                    使用模板
                  </button>
                ))}
              </div>
            </div>
            <div className="lg:col-span-4">
              <Field
                label="备注"
                value={form.note}
                onChange={(value) => setForm((previous) => ({ ...previous, note: value }))}
              />
            </div>
          </div>
          {!isReasonCompatible ? (
            <div className="mt-4">
              <StatusBlock
                title="原因类型已自动建议纠正"
                description={`动作“${formatTradeSide(form.side)}”与原因“${formatTradeReasonType(
                  form.reasonType,
                )}”不匹配。建议改为“${formatTradeReasonType(recommendedReasonType)}”。`}
                tone="error"
              />
            </div>
          ) : null}
        </details>
        {submitMessage ? (
          <div className="mt-4">
            <StatusBlock title="操作成功" description={submitMessage} />
          </div>
        ) : null}
        {error ? (
          <div className="mt-4">
            <StatusBlock title="操作失败" description={error} tone="error" />
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="交易记录列表" description="可按股票代码过滤，并查看关联决策快照摘要。">
        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="总记录数" value={String(tradeSummary.total)} />
          <Metric label="入场动作数" value={String(tradeSummary.entry)} />
          <Metric label="离场动作数" value={String(tradeSummary.exit)} />
          <Metric label="跳过动作数" value={String(tradeSummary.skip)} />
        </div>
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={handleFilterSubmit}>
          <Field label="筛选股票代码" value={filterSymbol} onChange={setFilterSymbol} />
          <div className="flex items-end">
            <button
              type="submit"
              className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              刷新列表
            </button>
          </div>
        </form>

        {status === "loading" ? (
          <div className="mt-4">
            <StatusBlock title="加载中" description="正在读取交易记录..." />
          </div>
        ) : null}
        {status === "error" && error ? (
          <div className="mt-4">
            <StatusBlock title="加载失败" description={error} tone="error" />
          </div>
        ) : null}
        {status === "success" && records.length === 0 ? (
          <div className="mt-4">
            <StatusBlock title="暂无记录" description="当前没有交易记录，可先在上方创建一条。" />
          </div>
        ) : null}

        {records.length > 0 ? (
          <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3">日期</th>
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3">动作</th>
                  <th className="px-4 py-3">价格</th>
                  <th className="px-4 py-3">数量</th>
                  <th className="px-4 py-3">决策动作</th>
                  <th className="px-4 py-3">置信度</th>
                  <th className="px-4 py-3">数据质量</th>
                  <th className="px-4 py-3">对齐状态</th>
                </tr>
              </thead>
              <tbody>
                {records.map((item) => (
                  <tr
                    key={item.trade_id}
                    className={
                      selectedTradeId === item.trade_id
                        ? "cursor-pointer border-t border-slate-200 bg-emerald-50"
                        : "cursor-pointer border-t border-slate-200"
                    }
                    onClick={() => setSelectedTradeId(item.trade_id)}
                  >
                    <td className="px-4 py-3">{formatDateTime(item.trade_date)}</td>
                    <td className="px-4 py-3">{item.symbol}</td>
                    <td className="px-4 py-3">{formatTradeSide(item.side)}</td>
                    <td className="px-4 py-3">{item.price ?? "-"}</td>
                    <td className="px-4 py-3">{item.quantity ?? "-"}</td>
                    <td className="px-4 py-3">
                      {item.decision_snapshot?.action
                        ? formatAction(item.decision_snapshot.action as "BUY" | "WATCH" | "AVOID")
                        : "-"}
                    </td>
                    <td className="px-4 py-3">{item.decision_snapshot?.confidence ?? "-"}</td>
                    <td className="px-4 py-3">
                      {item.decision_snapshot?.data_quality_summary
                        ? `${item.decision_snapshot.data_quality_summary.bars_quality}/${item.decision_snapshot.data_quality_summary.financial_quality}/${item.decision_snapshot.data_quality_summary.announcement_quality}`
                        : "-"}
                    </td>
                    <td className="px-4 py-3">{formatStrategyAlignment(item.strategy_alignment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {selectedRecord ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-950">关联快照摘要（{selectedRecord.trade_id}）</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric
                label="动作 / 对齐"
                value={`${formatTradeSide(selectedRecord.side)} / ${formatStrategyAlignment(selectedRecord.strategy_alignment)}`}
              />
              <Metric
                label="决策动作"
                value={
                  selectedRecord.decision_snapshot?.action
                    ? formatAction(selectedRecord.decision_snapshot.action as "BUY" | "WATCH" | "AVOID")
                    : "-"
                }
              />
              <Metric
                label="决策置信度"
                value={String(selectedRecord.decision_snapshot?.confidence ?? "-")}
              />
              <Metric
                label="数据质量"
                value={
                  selectedRecord.decision_snapshot?.data_quality_summary
                    ? `${selectedRecord.decision_snapshot.data_quality_summary.bars_quality}/${selectedRecord.decision_snapshot.data_quality_summary.financial_quality}/${selectedRecord.decision_snapshot.data_quality_summary.announcement_quality}`
                    : "-"
                }
              />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Metric
                label="预测分"
                value={
                  selectedRecord.decision_snapshot?.predictive_score === null ||
                  selectedRecord.decision_snapshot?.predictive_score === undefined
                    ? "-"
                    : `${selectedRecord.decision_snapshot.predictive_score} / 100`
                }
              />
              <Metric
                label="预测置信度"
                value={formatRatioPercent(selectedRecord.decision_snapshot?.predictive_confidence)}
              />
              <Metric
                label="预测模型版本"
                value={selectedRecord.decision_snapshot?.predictive_model_version ?? "-"}
              />
            </div>
            <p className="mt-2 text-sm text-slate-700">
              thesis：{selectedRecord.decision_snapshot?.thesis ?? "暂无"}
            </p>
            <p className="mt-2 text-sm text-slate-700">
              triggers：
              {(selectedRecord.decision_snapshot?.triggers ?? []).join(" | ") || "暂无"}
            </p>
            <p className="mt-2 text-sm text-slate-700">
              invalidations：
              {(selectedRecord.decision_snapshot?.invalidations ?? []).join(" | ") || "暂无"}
            </p>
          </div>
        ) : null}
      </SectionCard>
    </PageShell>
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
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: OptionItem[];
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      >
        {options.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 break-all text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function defaultReasonTypeForSide(side: TradeSide): TradeReasonType {
  if (side === "SKIP") return "watch_only";
  if (side === "SELL" || side === "REDUCE") return "take_profit";
  return "signal_entry";
}

function isReasonTypeCompatible(side: TradeSide, reasonType: TradeReasonType): boolean {
  if (ENTRY_REASON_TYPES.includes(reasonType)) {
    return side === "BUY" || side === "ADD";
  }
  if (EXIT_REASON_TYPES.includes(reasonType)) {
    return side === "SELL" || side === "REDUCE";
  }
  if (SKIP_REASON_TYPES.includes(reasonType)) {
    return side === "SKIP";
  }
  return true;
}

function normalizeTradeSubmitError(cause: unknown): string {
  const fallbackMessage = "创建交易记录失败，请稍后重试。";
  const message = cause instanceof Error ? cause.message : fallbackMessage;
  if (!message) return fallbackMessage;

  if (message.includes("alignment_override_reason")) {
    return "当前交易与原判断存在冲突。若仍要手动指定“对齐/部分对齐”，请填写“人工覆盖原因”；或将“策略对齐”改为“不一致”。";
  }

  if (message.includes("422")) {
    return "参数校验未通过：请检查动作、原因类型、价格和数量是否匹配。";
  }

  return message;
}

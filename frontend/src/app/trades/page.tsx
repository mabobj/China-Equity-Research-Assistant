"use client";

import { useEffect, useMemo, useState } from "react";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";
import { createTradeFromCurrentDecision, listTrades, normalizeSymbolInput } from "@/lib/api";
import {
  formatAction,
  formatDateTime,
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
      const symbol = normalizeSymbolInput(form.symbol);
      const payload = {
        symbol,
        use_llm: form.useLlm,
        side: form.side,
        reason_type: form.reasonType,
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
      setError(cause instanceof Error ? cause.message : "创建交易记录失败，请稍后重试。");
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
      description="记录执行动作并关联当时决策快照，形成“判断 -> 执行”可追溯链路。"
    >
      <SectionCard title="新建交易记录" description="默认从当前研究上下文自动固化决策快照并关联。">
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
              setForm((previous) => ({ ...previous, side: value as TradeSide }))
            }
            options={SIDE_OPTIONS}
          />
          <SelectField
            label="原因类型"
            value={form.reasonType}
            onChange={(value) =>
              setForm((previous) => ({ ...previous, reasonType: value as TradeReasonType }))
            }
            options={REASON_OPTIONS}
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
          <Field
            label="人工覆盖原因（可选）"
            value={form.alignmentOverrideReason}
            onChange={(value) =>
              setForm((previous) => ({ ...previous, alignmentOverrideReason: value }))
            }
          />
          <Field
            label="价格（非 SKIP 必填）"
            value={form.price}
            onChange={(value) => setForm((previous) => ({ ...previous, price: value }))}
          />
          <Field
            label="数量（非 SKIP 必填）"
            value={form.quantity}
            onChange={(value) => setForm((previous) => ({ ...previous, quantity: value }))}
          />
          <Field
            label="备注"
            value={form.note}
            onChange={(value) => setForm((previous) => ({ ...previous, note: value }))}
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

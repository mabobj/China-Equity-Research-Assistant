"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getResearchReport,
  getStrategyPlan,
  normalizeSymbolInput,
} from "@/lib/api";
import {
  formatDate,
  formatLabel,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type { ResearchReport, StrategyPlan } from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";

type StockWorkspaceProps = {
  symbol: string;
};

export function StockWorkspace({ symbol }: StockWorkspaceProps) {
  const router = useRouter();
  const [inputValue, setInputValue] = useState(symbol);
  const [research, setResearch] = useState<ResearchReport | null>(null);
  const [strategy, setStrategy] = useState<StrategyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInputValue(symbol);
  }, [symbol]);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const researchResponse = await getResearchReport(symbol);
        const strategyResponse = await getStrategyPlan(symbol);

        if (!active) {
          return;
        }

        setResearch(researchResponse);
        setStrategy(strategyResponse);
      } catch (loadError) {
        if (!active) {
          return;
        }

        setResearch(null);
        setStrategy(null);
        setError(getErrorMessage(loadError));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [symbol]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedSymbol = normalizeSymbolInput(inputValue);
    if (!normalizedSymbol) {
      return;
    }

    router.push(`/stocks/${encodeURIComponent(normalizedSymbol)}`);
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="切换股票"
        description="页面会同时加载结构化研究报告和结构化策略计划。"
      >
        <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit}>
          <input
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            placeholder="输入股票代码，例如 600519.SH"
            className="min-h-11 flex-1 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
          <button
            type="submit"
            className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            查看单票
          </button>
        </form>
      </SectionCard>

      {loading ? (
        <StatusBlock title="正在加载" description="正在请求研究报告和策略计划，请稍候。" />
      ) : null}
      {error ? (
        <StatusBlock title="加载失败" description={error} tone="error" />
      ) : null}
      {!loading && !error && !research && !strategy ? (
        <StatusBlock
          title="暂无数据"
          description="当前没有拿到可展示的研究或策略结果。"
        />
      ) : null}

      {research ? <ResearchSection research={research} /> : null}
      {strategy ? <StrategySection strategy={strategy} /> : null}
    </div>
  );
}

function ResearchSection({ research }: { research: ResearchReport }) {
  return (
    <SectionCard
      title="研究报告"
      description={`截至 ${formatDate(research.as_of_date)} 的结构化研究结果。`}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric label="动作" value={research.action} />
          <Metric label="综合分数" value={formatScore(research.overall_score)} />
          <Metric label="技术分数" value={formatScore(research.technical_score)} />
          <Metric label="基本面分数" value={formatScore(research.fundamental_score)} />
          <Metric label="事件分数" value={formatScore(research.event_score)} />
          <Metric label="置信度" value={formatScore(research.confidence)} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Thesis</p>
          <p className="mt-2 text-sm leading-7 text-slate-800">{research.thesis}</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <BulletList title="关键原因" items={research.key_reasons} emptyText="暂无关键原因。" />
          <BulletList title="主要风险" items={research.risks} emptyText="暂无主要风险。" />
          <BulletList title="触发条件" items={research.triggers} emptyText="暂无触发条件。" />
          <BulletList
            title="失效条件"
            items={research.invalidations}
            emptyText="暂无失效条件。"
          />
        </div>
      </div>
    </SectionCard>
  );
}

function StrategySection({ strategy }: { strategy: StrategyPlan }) {
  return (
    <SectionCard
      title="策略计划"
      description={`策略动作为 ${strategy.action}，策略类型为 ${formatLabel(strategy.strategy_type)}。`}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric label="动作" value={strategy.action} />
          <Metric label="策略类型" value={formatLabel(strategy.strategy_type)} />
          <Metric label="入场窗口" value={formatLabel(strategy.entry_window)} />
          <Metric label="初始仓位" value={strategy.initial_position_hint ?? "-"} />
          <Metric label="止损价" value={formatPrice(strategy.stop_loss_price)} />
          <Metric label="置信度" value={formatScore(strategy.confidence)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Metric label="理想入场区间" value={formatRange(strategy.ideal_entry_range)} />
          <Metric label="止盈区间" value={formatRange(strategy.take_profit_range)} />
          <Metric label="复核周期" value={formatLabel(strategy.review_timeframe)} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <BulletList
            title="入场触发"
            items={strategy.entry_triggers}
            emptyText="暂无入场触发条件。"
          />
          <BulletList
            title="避免条件"
            items={strategy.avoid_if}
            emptyText="暂无避免条件。"
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <TextCard title="止损规则" content={strategy.stop_loss_rule} />
          <TextCard title="止盈规则" content={strategy.take_profit_rule} />
          <TextCard title="持有规则" content={strategy.hold_rule} />
          <TextCard title="卖出规则" content={strategy.sell_rule} />
        </div>
      </div>
    </SectionCard>
  );
}

function BulletList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">{emptyText}</p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {items.map((item) => (
            <li key={item} className="rounded-xl bg-white px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TextCard({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{content}</p>
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "发生未知错误，请稍后重试。";
}

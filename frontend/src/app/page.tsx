import Link from "next/link";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { SymbolSearchForm } from "@/components/symbol-search-form";

const FEATURE_ITEMS = [
  {
    title: "规则选股",
    description: "查看全市场初筛与深筛结果，快速定位当前更值得继续研究的股票。",
  },
  {
    title: "结构化研究",
    description: "对单票展示技术、基本面、事件评分和简明 thesis，方便快速浏览。",
  },
  {
    title: "结构化策略",
    description: "把买入区间、止损、止盈、持有与卖出规则整理成统一格式。",
  },
];

export default function HomePage() {
  return (
    <PageShell
      title="A 股研究助手"
      description="当前前端已经接入核心后端能力，支持浏览选股结果、查看单票研究报告与结构化策略。"
    >
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <SectionCard
          title="快速开始"
          description="可以先进入选股页查看全市场结果，也可以直接输入股票代码进入单票页面。"
          actions={
            <Link
              href="/screener"
              className="rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
            >
              进入选股器
            </Link>
          }
        >
          <div className="space-y-5">
            <p className="text-sm leading-7 text-slate-700">
              这是一套面向 A 股市场的轻量研究界面。当前版本重点展示后端已经具备的结构化能力，而不是追求复杂图表或花哨交互。
            </p>
            <SymbolSearchForm />
          </div>
        </SectionCard>

        <SectionCard
          title="当前接入"
          description="本轮前端只接入选股、研究和策略三条主链路。"
        >
          <div className="grid gap-3">
            {FEATURE_ITEMS.map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
              >
                <h2 className="text-base font-semibold text-slate-950">
                  {item.title}
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}

import Link from "next/link";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { SymbolSearchForm } from "@/components/symbol-search-form";

const FEATURE_ITEMS = [
  {
    title: "单票分析",
    description:
      "按股票代码进入单票工作台，顺序查看基础信息、因子快照、review-report v2、debate-review、strategy plan 和触发快照。",
    href: "/stocks/600519.SH",
    actionLabel: "打开单票工作台",
  },
  {
    title: "选股工作台",
    description:
      "在同一页面内完成数据补全、规则初筛、深筛结果查看，并跳转到单票继续研究。",
    href: "/screener",
    actionLabel: "进入选股工作台",
  },
  {
    title: "Workflow 执行",
    description:
      "single_stock_full_review 已接入单票工作台，deep_candidate_review 已接入选股工作台，可查看 run_id、步骤摘要和最终输出摘要。",
    href: "/screener#workflow",
    actionLabel: "查看 workflow 入口",
  },
  {
    title: "交易记录",
    description:
      "当前仍是占位入口，后续阶段会补齐录入、查询和复盘链路，本轮不伪造尚未上线的能力。",
    href: "/trades",
    actionLabel: "查看当前状态",
  },
] as const;

export default function HomePage() {
  return (
    <PageShell
      title="A 股研究助手工作台"
      description="这个前端版本的重点不是展示所有原始接口，而是把现有研究、选股、workflow 和后续扩展入口串成可执行的日常工作流。"
    >
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <SectionCard
          title="从一只股票开始"
          description="输入股票代码后直接进入单票工作台。推荐先用 600519.SH 做最小验证。"
        >
          <div className="space-y-5">
            <p className="text-sm leading-7 text-slate-700">
              当前推荐主链路是：输入代码进入单票页，先看 factor / review /
              debate / strategy 的关键摘要；如果要跑显式 workflow，再在单票页或选股页内直接触发。
            </p>
            <SymbolSearchForm />
          </div>
        </SectionCard>

        <SectionCard
          title="系统能做什么"
          description="现阶段聚焦研究与决策支持，不进入实盘执行。"
        >
          <div className="space-y-3">
            <FeaturePill label="全市场选股" />
            <FeaturePill label="单票研究" />
            <FeaturePill label="角色化裁决" />
            <FeaturePill label="结构化策略计划" />
            <FeaturePill label="显式 workflow 执行" />
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="推荐入口"
        description="按操作目标选择入口，而不是自己手工拼多个接口。"
      >
        <div className="grid gap-4 md:grid-cols-2">
          {FEATURE_ITEMS.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <h2 className="text-base font-semibold text-slate-950">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {item.description}
              </p>
              <Link
                href={item.href}
                className="mt-4 inline-flex rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
              >
                {item.actionLabel}
              </Link>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="使用建议"
        description="如果你是第一次使用，建议按下面顺序验证系统。"
      >
        <ol className="space-y-3 text-sm leading-7 text-slate-700">
          <li>1. 在首页输入 600519.SH，进入单票工作台确认基础链路可用。</li>
          <li>2. 在单票页运行 single_stock_full_review，观察 run_id 和步骤摘要。</li>
          <li>3. 打开选股工作台，运行规则初筛和 deep_candidate_review workflow。</li>
          <li>4. 如需排查问题，再参考 README 和 docs/manuals 下的操作文档。</li>
        </ol>
      </SectionCard>
    </PageShell>
  );
}

function FeaturePill({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
      {label}
    </div>
  );
}

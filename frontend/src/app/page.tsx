import Link from "next/link";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { SymbolSearchForm } from "@/components/symbol-search-form";

const FEATURE_ITEMS = [
  {
    title: "单票工作台",
    description:
      "输入股票代码后，按“结论 -> 证据 -> 动作 -> 详情”顺序查看单票分析，默认由 workspace-bundle 聚合驱动。",
    href: "/stocks/600519.SH",
    actionLabel: "进入单票工作台",
  },
  {
    title: "选股工作台",
    description:
      "通过 workflow 运行初筛与深筛，查看 run_id、步骤状态、批次摘要与候选结果。",
    href: "/screener",
    actionLabel: "进入选股工作台",
  },
  {
    title: "交易记录工作台",
    description:
      "将执行动作与当时决策快照关联，形成“判断 -> 执行”的可追溯记录链。",
    href: "/trades",
    actionLabel: "进入交易记录",
  },
  {
    title: "复盘工作台",
    description:
      "从交易记录生成复盘草稿，回看当时判断、执行偏差与复盘结论，积累可迭代经验。",
    href: "/reviews",
    actionLabel: "进入复盘工作台",
  },
] as const;

export default function HomePage() {
  return (
    <PageShell
      title="A 股研究助手工作台"
      description="以“先结论、再证据、后细节”为主交互逻辑，覆盖选股、单票、交易、复盘完整链路。"
    >
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <SectionCard
          title="从单票开始"
          description="输入股票代码后可直接进入单票工作台。"
        >
          <div className="space-y-5">
            <p className="text-sm leading-7 text-slate-700">
              推荐先用 <code>600519.SH</code> 做最小验证，先看主输出链路，再按需触发
              <code>single_stock_full_review</code>。
            </p>
            <SymbolSearchForm />
          </div>
        </SectionCard>

        <SectionCard
          title="当前能力范围"
          description="当前系统是研究与决策辅助产品，不做自动实盘执行。"
        >
          <div className="space-y-3">
            <FeaturePill label="单票研究输出" />
            <FeaturePill label="结构化裁决" />
            <FeaturePill label="策略计划输出" />
            <FeaturePill label="选股工作流" />
            <FeaturePill label="交易记录与复盘" />
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="推荐入口"
        description="优先使用稳定入口，而不是手工拼接多个接口。"
      >
        <div className="grid gap-4 md:grid-cols-2">
          {FEATURE_ITEMS.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <h2 className="text-base font-semibold text-slate-950">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
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
        title="术语说明"
        description="以下术语在页面和文档中保持一致。"
      >
        <ul className="space-y-3 text-sm leading-7 text-slate-700">
          <li>
            <strong>review-report v2</strong>：单票主研究产物（方向层结论）。
          </li>
          <li>
            <strong>decision brief</strong>：单票主输出层（当前动作、证据、风险、下一步）。
          </li>
          <li>
            <strong>debate-review</strong>：结构化裁决层，用于补充解释，不替代确定性计算。
          </li>
          <li>
            <strong>/trades 与 /reviews</strong>：当前已启用，分别用于执行记录与复盘学习。
          </li>
          <li>
            <strong>工作流运行记录（workflow run record）</strong>：工作流运行元数据与步骤摘要，不等于人工复盘笔记。
          </li>
        </ul>
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

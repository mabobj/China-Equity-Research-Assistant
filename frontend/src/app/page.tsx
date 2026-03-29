import Link from "next/link";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { SymbolSearchForm } from "@/components/symbol-search-form";

const FEATURE_ITEMS = [
  {
    title: "单票工作台",
    description:
      "输入一个股票代码后，按主链路查看：基础信息、因子快照、review-report v2、debate-review、策略计划（strategy plan）、触发快照（trigger snapshot）。",
    href: "/stocks/600519.SH",
    actionLabel: "进入单票工作台",
  },
  {
    title: "选股工作台",
    description:
      "在同一页面完成数据补全、初筛与深筛；候选卡片可直接跳转到单票页面继续分析。",
    href: "/screener",
    actionLabel: "进入选股工作台",
  },
  {
    title: "工作流运行记录",
    description:
      "单票和选股页面都使用工作流模式，可查看 run_id、节点摘要和最终输出摘要，避免长请求阻塞。",
    href: "/screener#workflow",
    actionLabel: "查看工作流面板",
  },
  {
    title: "交易与复盘",
    description:
      "当前阶段这两个页面为预留态，会明确标注“未启用”，不会展示伪造功能。",
    href: "/trades",
    actionLabel: "查看预留页面",
  },
] as const;

export default function HomePage() {
  return (
    <PageShell
      title="A 股研究助手工作台"
      description="前端按工作台方式组织：入口清晰、术语统一、关键运行状态可见。"
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
          description="本阶段聚焦研究输出稳定性，不涉及自动交易执行。"
        >
          <div className="space-y-3">
            <FeaturePill label="单票研究输出" />
            <FeaturePill label="结构化裁决" />
            <FeaturePill label="策略计划输出" />
            <FeaturePill label="选股工作流" />
            <FeaturePill label="工作流运行记录" />
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
            <strong>review-report v2</strong>：单票主研究产物。
          </li>
          <li>
            <strong>debate-review</strong>：结构化裁决层。
          </li>
          <li>
            <strong>/reviews</strong>：预留页面，当前未启用。
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

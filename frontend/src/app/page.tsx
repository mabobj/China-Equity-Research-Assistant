import Link from "next/link";

import { PageShell } from "@/components/page-shell";

const SECTIONS = [
  {
    href: "/screener",
    title: "Screener",
    description: "全市场选股页面占位，后续将承接结构化筛选结果。",
  },
  {
    href: "/stocks/600519",
    title: "Stock Research",
    description: "单票研究页面占位，后续展示结构化研究报告与策略输出。",
  },
  {
    href: "/trades",
    title: "Trade Records",
    description: "交易记录页面占位，后续补充录入与查询能力。",
  },
  {
    href: "/reviews",
    title: "Reviews",
    description: "复盘页面占位，后续承接复盘记录与学习结果。",
  },
];

export default function HomePage() {
  return (
    <PageShell
      title="A-Share Research Assistant"
      description="当前为 Phase 0 前端骨架。页面仅提供导航与占位内容，不包含任何研究、选股、交易或复盘业务逻辑。"
    >
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((section) => (
          <Link
            key={section.href}
            href={section.href}
            className="rounded-2xl border border-slate-200 bg-slate-50 p-5 transition hover:border-emerald-200 hover:bg-emerald-50"
          >
            <h2 className="text-lg font-semibold text-slate-900">
              {section.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {section.description}
            </p>
          </Link>
        ))}
      </div>
    </PageShell>
  );
}

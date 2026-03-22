import { PageShell } from "@/components/page-shell";

export default function ScreenerPage() {
  return (
    <PageShell
      title="Screener"
      description="全市场选股页面占位。后续 Phase 4 才会接入机器可读选股结果、排序和名单视图。"
    >
      <p className="text-base leading-7 text-slate-600">
        当前仅保留页面入口与布局，不实现筛选规则、评分逻辑或数据展示。
      </p>
    </PageShell>
  );
}

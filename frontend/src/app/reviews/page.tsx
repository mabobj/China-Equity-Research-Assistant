import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";

export default function ReviewsPage() {
  return (
    <PageShell
      title="复盘"
      description="本页当前只保留清晰占位，后续阶段再接入复盘记录、归因和学习结果。"
    >
      <SectionCard
        title="功能状态"
        description="Phase 5-A 不实现复盘业务逻辑，也不接入交易记录联动。"
      >
        <p className="text-sm leading-7 text-slate-700">
          当前页面仅保留未来扩展位置，确保本轮聚焦在选股、研究和策略的展示链路。
        </p>
      </SectionCard>
    </PageShell>
  );
}

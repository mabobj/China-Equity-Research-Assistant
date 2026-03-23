import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";

export default function TradesPage() {
  return (
    <PageShell
      title="交易记录"
      description="本页当前只保留清晰占位，后续阶段再接入交易录入、记录查询和策略快照。"
    >
      <SectionCard
        title="功能状态"
        description="Phase 5-A 不实现交易记录表单、存储或统计逻辑。"
      >
        <p className="text-sm leading-7 text-slate-700">
          当前页面只用于保留导航入口和未来扩展位置，避免把尚未完成的交易闭环能力混入本轮前端范围。
        </p>
      </SectionCard>
    </PageShell>
  );
}

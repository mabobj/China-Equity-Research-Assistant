import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function TradesPage() {
  return (
    <PageShell
      title="交易记录（预留）"
      description="该页面当前为预留占位，交易日志与持仓生命周期能力尚未启用。"
    >
      <SectionCard
        title="当前状态"
        description="本页只说明边界，不展示未上线功能。"
      >
        <div className="space-y-4">
          <StatusBlock
            title="未启用"
            description="交易录入、持仓跟踪、已实现盈亏统计及自动复盘流程尚未上线。"
          />
          <StatusBlock
            title="后续方向"
            description="后续阶段可能补充结构化交易记录与轻量复盘关联，但不在当前阶段范围内。"
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

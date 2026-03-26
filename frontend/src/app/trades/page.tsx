import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function TradesPage() {
  return (
    <PageShell
      title="交易记录"
      description="当前页面仍为清晰占位页。本阶段不伪造交易录入、持仓或复盘能力，只明确告诉你现在还没上线什么。"
    >
      <SectionCard
        title="当前状态"
        description="交易记录、持仓快照、卖出归因和复盘统计尚未进入本轮范围。"
      >
        <div className="space-y-4">
          <StatusBlock
            title="当前未上线"
            description="交易记录录入、持仓管理、收益统计和自动复盘还没有接入，不建议把这里当成已可用功能。"
          />
          <StatusBlock
            title="下一步会做什么"
            description="后续阶段会优先补齐结构化交易记录、策略快照留存和基础复盘入口，再决定是否扩展更多统计视图。"
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

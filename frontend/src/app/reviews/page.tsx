import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function ReviewsPage() {
  return (
    <PageShell
      title="复盘记录（预留）"
      description="当前路由为预留状态，尚未启用。请勿与 review-report v2 研究输出混淆。"
    >
      <SectionCard
        title="当前状态"
        description="为避免误解，复盘记录与研究输出在术语上明确区分。"
      >
        <div className="space-y-4">
          <StatusBlock
            title="未启用"
            description="人工复盘日志、归因记录和复盘检索能力暂未上线。"
          />
          <StatusBlock
            title="当前可用替代路径"
            description="回看执行过程请使用工作流运行记录（workflow run record）；查看当下研究结论请使用单票页的 review-report v2 与 debate-review。"
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

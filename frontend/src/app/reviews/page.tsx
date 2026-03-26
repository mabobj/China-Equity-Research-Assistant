import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function ReviewsPage() {
  return (
    <PageShell
      title="复盘记录"
      description="当前仍是占位页。系统已经有 review_service 和 workflow 运行记录，但“人工复盘记录”这条业务线本轮还没有正式上线。"
    >
      <SectionCard
        title="当前状态"
        description="不要把 review-service 的分析结果和未来的复盘记录概念混在一起。"
      >
        <div className="space-y-4">
          <StatusBlock
            title="当前未上线"
            description="人工复盘条目、交易后复盘归因、复盘检索和复盘沉淀功能当前都还没有开放。"
          />
          <StatusBlock
            title="现在可以看什么"
            description="如果你要回看分析过程，当前推荐入口是 workflow run record；如果你要回看当下判断，则使用单票工作台中的 review-report 和 debate-review。"
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="选股器"
      description="这里可以分别运行规则初筛和深筛聚合，并用结构化方式浏览候选股票。"
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

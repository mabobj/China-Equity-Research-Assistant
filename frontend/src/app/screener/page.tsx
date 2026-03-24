import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="选股器"
      description="这里可以触发数据补全、运行规则初筛，以及继续查看深筛聚合结果。"
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

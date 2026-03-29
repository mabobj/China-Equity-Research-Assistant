import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="选股工作台"
      description="通过工作流模式运行初筛与深筛，并查看 run_id、节点状态、最终结果和局部失败符号。"
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

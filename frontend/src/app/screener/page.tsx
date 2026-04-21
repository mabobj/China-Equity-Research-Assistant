import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="方案化选股工作台"
      description="先选方案，再发起运行，随后在同一页面里查看候选结果、历史运行和方案级反馈。这里的主线是“方案 -> 运行 -> 结果 -> 反馈”，而不是孤立的一张结果表。"
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

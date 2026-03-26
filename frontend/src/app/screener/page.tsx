import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="选股工作台"
      description="在一个页面里完成数据补全、规则初筛、深筛结果查看，以及 deep_candidate_review workflow 的运行与记录查看。"
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

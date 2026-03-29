import { PageShell } from "@/components/page-shell";
import { ScreenerWorkspace } from "@/components/screener-workspace";

export default function ScreenerPage() {
  return (
    <PageShell
      title="Screener Workspace"
      description="Run initial screener and deep review through workflow mode, then inspect run_id, step summaries, final outputs, and partial-failure symbols."
    >
      <ScreenerWorkspace />
    </PageShell>
  );
}

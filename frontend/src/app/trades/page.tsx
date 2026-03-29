import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function TradesPage() {
  return (
    <PageShell
      title="Trades (Reserved)"
      description="This page is intentionally a reserved placeholder. Trade journal and portfolio lifecycle are not enabled in the current phase."
    >
      <SectionCard
        title="Current status"
        description="No fake UI: this page only explains what is still out of scope."
      >
        <div className="space-y-4">
          <StatusBlock
            title="Not enabled"
            description="Trade entry, position tracking, realized PnL, and automatic review flows are not shipped."
          />
          <StatusBlock
            title="Next stage direction"
            description="A later phase may add structured trade records and lightweight review linkage, but that is outside the current audit close-out scope."
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

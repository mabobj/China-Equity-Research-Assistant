import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";

export default function ReviewsPage() {
  return (
    <PageShell
      title="Reviews (Reserved)"
      description="This route is reserved and not enabled in the current phase. It is not the same thing as review-report v2 output."
    >
      <SectionCard
        title="Current status"
        description="Keep these terms separate to avoid confusion in daily usage."
      >
        <div className="space-y-4">
          <StatusBlock
            title="Not enabled"
            description="Manual post-trade review journal, attribution notes, and review retrieval are not shipped in this phase."
          />
          <StatusBlock
            title="What to use now"
            description="Use workflow run records for execution traces, and use review-report v2 + debate-review on the stock page for current research conclusions."
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}

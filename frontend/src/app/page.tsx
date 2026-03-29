import Link from "next/link";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { SymbolSearchForm } from "@/components/symbol-search-form";

const FEATURE_ITEMS = [
  {
    title: "Single-Stock Workspace",
    description:
      "Open one symbol and follow the main chain: profile, factor snapshot, review-report v2, debate-review, strategy plan, and trigger snapshot.",
    href: "/stocks/600519.SH",
    actionLabel: "Open single-stock workspace",
  },
  {
    title: "Screener Workspace",
    description:
      "Run refresh, initial screener, and deep review in one place. Candidate cards are linked back to the single-stock workspace.",
    href: "/screener",
    actionLabel: "Open screener workspace",
  },
  {
    title: "Workflow Runs",
    description:
      "Both screens use workflow run records. You can track run_id, node summaries, and final output without long blocking requests.",
    href: "/screener#workflow",
    actionLabel: "Open workflow panel",
  },
  {
    title: "Trades and Reviews",
    description:
      "Both pages are intentionally reserved in this phase. They clearly show not-enabled status instead of fake functionality.",
    href: "/trades",
    actionLabel: "See reserved pages",
  },
] as const;

export default function HomePage() {
  return (
    <PageShell
      title="A-Share Research Assistant Workspace"
      description="The UI is organized as an operator workspace instead of a raw API dump: clear entry points, stable wording, and visible workflow progress."
    >
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <SectionCard
          title="Start from one symbol"
          description="Input a stock code and jump directly into the single-stock workspace."
        >
          <div className="space-y-5">
            <p className="text-sm leading-7 text-slate-700">
              Recommended first check: use <code>600519.SH</code>, review the main
              output chain, then trigger <code>single_stock_full_review</code> only when needed.
            </p>
            <SymbolSearchForm />
          </div>
        </SectionCard>

        <SectionCard
          title="Current scope"
          description="This phase focuses on research output stability, not trading execution."
        >
          <div className="space-y-3">
            <FeaturePill label="Single-stock research output" />
            <FeaturePill label="Structured debate adjudication" />
            <FeaturePill label="Strategy plan output" />
            <FeaturePill label="Screener workflows" />
            <FeaturePill label="Workflow run records" />
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Recommended Entry Points"
        description="Use these stable entrances instead of manually combining many endpoints."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {FEATURE_ITEMS.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <h2 className="text-base font-semibold text-slate-950">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {item.description}
              </p>
              <Link
                href={item.href}
                className="mt-4 inline-flex rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
              >
                {item.actionLabel}
              </Link>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="Naming Conventions"
        description="Wording is intentionally converged in this audit close-out."
      >
        <ul className="space-y-3 text-sm leading-7 text-slate-700">
          <li>
            <strong>review-report v2</strong> is the main single-stock research artifact.
          </li>
          <li>
            <strong>debate-review</strong> is the structured adjudication layer.
          </li>
          <li>
            <strong>/reviews</strong> is reserved and currently not enabled.
          </li>
          <li>
            <strong>workflow run record</strong> means saved run metadata and step
            summaries, not manual review notes.
          </li>
        </ul>
      </SectionCard>
    </PageShell>
  );
}

function FeaturePill({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
      {label}
    </div>
  );
}

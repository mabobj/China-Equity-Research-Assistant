import { PageShell } from "@/components/page-shell";
import { StockWorkspace } from "@/components/stock-workspace";

type StockPageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

export default async function StockPage({ params }: StockPageProps) {
  const { symbol } = await params;
  const decodedSymbol = decodeURIComponent(symbol);

  return (
    <PageShell
      title={`Single-Stock Workspace: ${decodedSymbol}`}
      description="Follow the main chain in order: profile, factor snapshot, review-report v2 (primary research artifact), debate-review (structured adjudication), strategy plan, and trigger snapshot."
    >
      <StockWorkspace symbol={decodedSymbol} />
    </PageShell>
  );
}

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
      title={`单票工作台：${decodedSymbol}`}
      description="按主链路依次查看：基础信息、因子快照、review-report v2（主研究产物）、debate-review（结构化裁决）、策略计划（strategy plan）与触发快照（trigger snapshot）。"
    >
      <StockWorkspace symbol={decodedSymbol} />
    </PageShell>
  );
}

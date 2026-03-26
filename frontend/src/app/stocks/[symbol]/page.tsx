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
      description="按固定顺序查看基础信息、因子快照、review-report v2、debate-review、strategy plan 和 trigger snapshot，并可直接运行 single_stock_full_review。"
    >
      <StockWorkspace symbol={decodedSymbol} />
    </PageShell>
  );
}

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
      title={`单票研究：${decodedSymbol}`}
      description="页面会同时展示结构化研究报告与结构化策略计划，方便快速判断当前是否值得继续跟踪。"
    >
      <StockWorkspace symbol={decodedSymbol} />
    </PageShell>
  );
}

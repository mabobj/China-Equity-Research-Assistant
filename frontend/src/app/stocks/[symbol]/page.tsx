import { PageShell } from "@/components/page-shell";

type StockPageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

export default async function StockPage({ params }: StockPageProps) {
  const { symbol } = await params;

  return (
    <PageShell
      title={`Stock ${symbol.toUpperCase()}`}
      description="单票研究页面占位。后续将展示结构化研究报告、评分、触发条件和失效条件。"
    >
      <p className="text-base leading-7 text-slate-600">
        当前仅显示动态路由骨架，不接入任何研究、行情、公告或策略逻辑。
      </p>
    </PageShell>
  );
}

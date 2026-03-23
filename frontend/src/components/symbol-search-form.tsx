"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { normalizeSymbolInput } from "@/lib/api";

type SymbolSearchFormProps = {
  initialValue?: string;
  buttonLabel?: string;
  className?: string;
};

export function SymbolSearchForm({
  initialValue = "",
  buttonLabel = "查看研究",
  className,
}: SymbolSearchFormProps) {
  const router = useRouter();
  const [symbol, setSymbol] = useState(initialValue);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedSymbol = normalizeSymbolInput(symbol);
    if (!normalizedSymbol) {
      return;
    }

    router.push(`/stocks/${encodeURIComponent(normalizedSymbol)}`);
  };

  return (
    <form className={className} onSubmit={handleSubmit}>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="输入股票代码，例如 600519 或 600519.SH"
          className="min-h-11 flex-1 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
        <button
          type="submit"
          className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800"
        >
          {buttonLabel}
        </button>
      </div>
    </form>
  );
}

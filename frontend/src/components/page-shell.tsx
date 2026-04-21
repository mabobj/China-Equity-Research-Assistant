"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

type NavItem = {
  href: string;
  label: string;
};

type PageShellProps = {
  title: string;
  description: string;
  children?: ReactNode;
};

const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "首页" },
  { href: "/screener", label: "选股工作台" },
  { href: "/stocks/600519.SH", label: "单票工作台" },
  { href: "/trades", label: "交易记录" },
  { href: "/reviews", label: "复盘记录" },
];

export function PageShell({ title, description, children }: PageShellProps) {
  const pathname = usePathname();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-5 py-8 sm:px-8 lg:px-10">
      <header className="rounded-[2rem] border border-emerald-950/10 bg-white/90 p-6 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-6">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.28em] text-emerald-700">
              China Equity Research Assistant
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
              {title}
            </h1>
            <p className="max-w-3xl text-base leading-7 text-slate-600">
              {description}
            </p>
          </div>
          <nav className="flex flex-wrap gap-3 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={
                  pathname === item.href
                    ? "rounded-full border border-emerald-300 bg-emerald-100 px-4 py-2 font-semibold text-emerald-900 transition"
                    : "rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-slate-700 transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-800"
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      {children}
    </main>
  );
}

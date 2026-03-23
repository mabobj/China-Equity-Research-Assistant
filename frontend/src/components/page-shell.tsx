import Link from "next/link";
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
  { href: "/screener", label: "选股器" },
  { href: "/stocks/600519.SH", label: "单票研究" },
  { href: "/trades", label: "交易记录" },
  { href: "/reviews", label: "复盘" },
];

export function PageShell({
  title,
  description,
  children,
}: PageShellProps) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-5 py-8 sm:px-8 lg:px-10">
      <header className="rounded-[2rem] border border-emerald-950/10 bg-white/90 p-6 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-6">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.28em] text-emerald-700">
              Phase 5-A
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
                className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-slate-700 transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-800"
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

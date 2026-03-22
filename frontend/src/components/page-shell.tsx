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
  { href: "/", label: "Overview" },
  { href: "/screener", label: "Screener" },
  { href: "/stocks/600519", label: "Stock" },
  { href: "/trades", label: "Trades" },
  { href: "/reviews", label: "Reviews" },
];

export function PageShell({
  title,
  description,
  children,
}: PageShellProps) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-10 sm:px-10">
      <header className="flex flex-col gap-6 rounded-3xl border border-emerald-950/10 bg-white/90 p-6 shadow-sm">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium uppercase tracking-[0.28em] text-emerald-700">
            Phase 0
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
      </header>
      <section className="grid gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        {children}
      </section>
    </main>
  );
}

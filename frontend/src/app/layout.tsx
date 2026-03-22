import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "A-Share Research Assistant",
    template: "%s | A-Share Research Assistant",
  },
  description: "Phase 0 frontend scaffold for the A-share research assistant.",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="min-h-full bg-[var(--page-background)] font-sans text-[var(--page-foreground)] antialiased">
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.16),_transparent_45%),linear-gradient(180deg,_#f5f8f4_0%,_#eef3ef_100%)]">
          {children}
        </div>
      </body>
    </html>
  );
}

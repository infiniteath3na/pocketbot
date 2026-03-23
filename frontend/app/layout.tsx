"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  History,
  Settings,
  BarChart2,
  Bot,
} from "lucide-react";
import { getBotStatus } from "@/lib/api";
import "./globals.css";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scanner", label: "Scanner", icon: Search },
  { href: "/trades", label: "Trades", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/backtest", label: "Backtest", icon: BarChart2 },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [botRunning, setBotRunning] = useState(false);

  useEffect(() => {
    getBotStatus()
      .then((s) => setBotRunning(s.running))
      .catch(() => {});

    const interval = setInterval(() => {
      getBotStatus()
        .then((s) => setBotRunning(s.running))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <html lang="en">
      <head>
        <title>PocketBot - Automated Trading</title>
        <meta name="description" content="PocketBot automated binary options trading" />
      </head>
      <body style={{ margin: 0, backgroundColor: "#0a0b0e", color: "#f0f2f5" }}>
        <div className="flex h-screen overflow-hidden bg-background text-text-primary">
          {/* Sidebar */}
          <aside className="flex flex-col w-56 min-w-[14rem] bg-surface border-r border-border">
            {/* Brand */}
            <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent/20">
                <Bot size={18} className="text-accent" />
              </div>
              <div>
                <span className="font-bold text-base text-text-primary tracking-tight">PocketBot</span>
                <p className="text-xs text-muted leading-none mt-0.5">Auto Trader</p>
              </div>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-3 py-4 space-y-1">
              {navItems.map(({ href, label, icon: Icon }) => {
                const isActive = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    className={[
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                      isActive
                        ? "bg-accent/15 text-accent"
                        : "text-text-secondary hover:text-text-primary hover:bg-white/5",
                    ].join(" ")}
                  >
                    <Icon size={16} />
                    {label}
                  </Link>
                );
              })}
            </nav>

            {/* Bot Status */}
            <div className="px-5 py-4 border-t border-border">
              <div className="flex items-center gap-2">
                <span
                  className={[
                    "inline-block w-2 h-2 rounded-full",
                    botRunning ? "bg-accent animate-pulse" : "bg-muted",
                  ].join(" ")}
                />
                <span className="text-xs text-text-secondary">
                  Bot: {botRunning ? "Running" : "Stopped"}
                </span>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto bg-background">{children}</main>
        </div>
      </body>
    </html>
  );
}

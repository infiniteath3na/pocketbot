"use client";

import { useState, useEffect, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  DollarSign,
  Target,
} from "lucide-react";
import {
  getAssets,
  getStats,
  getTrades,
  getSettings,
  Asset,
  Stats,
  Trade,
  Settings,
  WSMessage,
  createReconnectingWebSocket,
} from "@/lib/api";
import AssetCard from "@/components/AssetCard";
import BalanceDisplay from "@/components/BalanceDisplay";
import BotControls from "@/components/BotControls";
import TradeLog from "@/components/TradeLog";

function StatCard({
  label,
  value,
  sub,
  positive,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  icon: React.ElementType;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted uppercase tracking-wide">{label}</span>
        <Icon size={16} className="text-muted" />
      </div>
      <div
        className={[
          "text-2xl font-bold",
          positive === true
            ? "text-accent"
            : positive === false
            ? "text-danger"
            : "text-text-primary",
        ].join(" ")}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [activeTrades, setActiveTrades] = useState<Trade[]>([]);
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [assetsRes, statsRes, tradesRes, settingsRes] = await Promise.allSettled([
        getAssets(),
        getStats(),
        getTrades({ limit: 10 }),
        getSettings(),
      ]);
      if (assetsRes.status === "fulfilled") setAssets(assetsRes.value.assets);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      if (tradesRes.status === "fulfilled") {
        const all = tradesRes.value.trades;
        setRecentTrades(all);
        setActiveTrades(all.filter((t) => t.result === "PENDING"));
      }
      if (settingsRes.status === "fulfilled") setSettings(settingsRes.value);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    const ws = createReconnectingWebSocket(
      (msg: WSMessage) => {
        if (msg.type === "confidence_update") {
          setAssets((prev) =>
            prev.map((a) => (a.asset === msg.data.asset ? { ...a, ...msg.data } : a))
          );
        } else if (msg.type === "price_update") {
          setAssets((prev) =>
            prev.map((a) =>
              a.asset === msg.data.asset
                ? { ...a, price: msg.data.price, price_change_pct: msg.data.price_change_pct }
                : a
            )
          );
        } else if (msg.type === "trade_opened") {
          setActiveTrades((prev) => [msg.data, ...prev]);
          setRecentTrades((prev) => [msg.data, ...prev.slice(0, 9)]);
          loadData();
        } else if (msg.type === "trade_closed") {
          setActiveTrades((prev) => prev.filter((t) => t.id !== msg.data.id));
          setRecentTrades((prev) => prev.map((t) => (t.id === msg.data.id ? msg.data : t)));
          loadData();
        } else if (msg.type === "daily_limit_hit") {
          // Could show a notification
        }
      },
      (connected) => setWsConnected(connected)
    );
    return () => ws.disconnect();
  }, [loadData]);

  const threshold = parseFloat(settings.confidence_threshold || "70");

  const sortedAssets = [...assets].sort((a, b) => b.confidence - a.confidence);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary">PocketBot Dashboard</h1>
          <p className="text-sm text-muted mt-0.5">
            Real-time confidence analysis across {assets.length} assets
            {wsConnected ? (
              <span className="ml-2 inline-flex items-center gap-1 text-accent text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                Live
              </span>
            ) : (
              <span className="ml-2 text-muted text-xs">(Connecting…)</span>
            )}
          </p>
        </div>
        <BotControls />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Daily P&L"
          value={`${(stats?.daily_pnl ?? 0) >= 0 ? "+" : ""}$${(stats?.daily_pnl ?? 0).toFixed(2)}`}
          sub="Today's performance"
          positive={stats ? stats.daily_pnl >= 0 : undefined}
          icon={DollarSign}
        />
        <StatCard
          label="Win Rate"
          value={`${(stats?.win_rate ?? 0).toFixed(1)}%`}
          sub={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L`}
          positive={stats ? stats.win_rate >= 50 : undefined}
          icon={Target}
        />
        <StatCard
          label="Active Trades"
          value={String(activeTrades.length)}
          sub="Currently open"
          icon={Activity}
        />
        <StatCard
          label="Trades Today"
          value={String(stats?.total_trades ?? 0)}
          sub={`Best: $${(stats?.best_trade ?? 0).toFixed(2)}`}
          icon={BarChart3}
        />
      </div>

      {/* Balance Display */}
      <BalanceDisplay />

      {/* Asset Grid */}
      <div>
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
          Asset Scanner — {sortedAssets.filter((a) => a.confidence >= threshold).length} signals
        </h2>
        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {Array.from({ length: 16 }).map((_, i) => (
              <div key={i} className="card p-4 h-44 animate-pulse bg-surface" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {sortedAssets.map((asset) => (
              <AssetCard
                key={asset.asset}
                asset={asset}
                confidenceThreshold={threshold}
              />
            ))}
          </div>
        )}
      </div>

      {/* Active Trades Panel */}
      {activeTrades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
            Active Trades
          </h2>
          <div className="card p-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted uppercase">
                    <th className="text-left pb-2 pr-4">Asset</th>
                    <th className="text-left pb-2 pr-4">Direction</th>
                    <th className="text-right pb-2 pr-4">Amount</th>
                    <th className="text-right pb-2 pr-4">Expiry</th>
                    <th className="text-left pb-2">Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {activeTrades.map((trade) => (
                    <tr key={trade.id} className="border-b border-border/50">
                      <td className="py-2.5 pr-4 font-medium">{trade.asset}</td>
                      <td className="py-2.5 pr-4">
                        <span
                          className={[
                            "text-xs font-bold px-2 py-0.5 rounded-full",
                            trade.direction === "CALL" ? "badge-call" : "badge-put",
                          ].join(" ")}
                        >
                          {trade.direction}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-text-secondary">
                        ${trade.amount.toFixed(2)}
                      </td>
                      <td className="py-2.5 pr-4 text-right text-muted text-xs">
                        {trade.expiry_seconds >= 60
                          ? `${trade.expiry_seconds / 60}m`
                          : `${trade.expiry_seconds}s`}
                      </td>
                      <td className="py-2.5">
                        <span
                          className={[
                            "text-xs px-2 py-0.5 rounded border",
                            trade.mode === "live"
                              ? "text-orange-400 bg-orange-400/10 border-orange-400/30"
                              : "text-blue-400 bg-blue-400/10 border-blue-400/30",
                          ].join(" ")}
                        >
                          {trade.mode.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div>
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
          Recent Trades
        </h2>
        <div className="card p-4">
          <TradeLog trades={recentTrades} limit={10} />
        </div>
      </div>
    </div>
  );
}

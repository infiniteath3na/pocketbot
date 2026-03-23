"use client";

import { useState, useEffect, useCallback } from "react";
import { Download, TrendingUp, TrendingDown, BarChart3, Target, DollarSign, Zap } from "lucide-react";
import {
  getTrades,
  getStats,
  Trade,
  Stats,
  TradeFilters,
} from "@/lib/api";
import TradeLog from "@/components/TradeLog";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";

const ASSETS = [
  "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURGBP","NZDUSD","USDCHF",
  "EURJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD","LTCUSD","SOLUSD","XRPUSD",
];

const PAGE_SIZE = 50;

function StatCard({ label, value, positive, icon: Icon }: {
  label: string; value: string; positive?: boolean; icon: React.ElementType;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-muted" />
        <span className="text-xs text-muted uppercase tracking-wide">{label}</span>
      </div>
      <div className={[
        "text-xl font-bold",
        positive === true ? "text-accent" : positive === false ? "text-danger" : "text-text-primary",
      ].join(" ")}>
        {value}
      </div>
    </div>
  );
}

function exportCSV(trades: Trade[]) {
  const header = "ID,Asset,Direction,Amount,Entry Time,Expiry(s),Result,P&L,Mode\n";
  const rows = trades.map((t) =>
    [
      t.id, t.asset, t.direction, t.amount,
      t.entry_time, t.expiry_seconds, t.result, t.pnl, t.mode,
    ].join(",")
  );
  const csv = header + rows.join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `pocketbot_trades_${format(new Date(), "yyyyMMdd_HHmmss")}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  // Filters
  const [filterAsset, setFilterAsset] = useState("all");
  const [filterMode, setFilterMode] = useState("all");
  const [filterResult, setFilterResult] = useState("all");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const filters: TradeFilters = { limit: 500 };
      if (filterAsset !== "all") filters.asset = filterAsset;
      if (filterMode !== "all") filters.mode = filterMode;
      if (filterResult !== "all") filters.result = filterResult;

      const [tradesRes, statsRes] = await Promise.allSettled([
        getTrades(filters),
        getStats(),
      ]);

      if (tradesRes.status === "fulfilled") {
        let t = tradesRes.value.trades;
        if (filterStartDate) t = t.filter((tr) => tr.entry_time >= filterStartDate);
        if (filterEndDate) t = t.filter((tr) => tr.entry_time <= filterEndDate + "T23:59:59");
        setTrades(t);
        setTotal(t.length);
      }
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
    } catch {}
    setLoading(false);
  }, [filterAsset, filterMode, filterResult, filterStartDate, filterEndDate]);

  useEffect(() => {
    loadData();
    setPage(0);
  }, [loadData]);

  // P&L curve data
  const closedTrades = trades.filter((t) => t.result !== "PENDING");
  let running = 0;
  const pnlCurve = closedTrades
    .slice()
    .reverse()
    .map((t) => {
      running += t.pnl;
      return {
        time: t.entry_time ? format(new Date(t.entry_time), "MM/dd HH:mm") : "",
        pnl: parseFloat(running.toFixed(2)),
      };
    });

  const paginated = trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const bestTrade = Math.max(...closedTrades.map((t) => t.pnl), 0);
  const worstTrade = Math.min(...closedTrades.map((t) => t.pnl), 0);
  const totalPnl = closedTrades.reduce((acc, t) => acc + t.pnl, 0);
  const wins = closedTrades.filter((t) => t.result === "WIN").length;
  const winRate = closedTrades.length ? (wins / closedTrades.length) * 100 : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-text-primary">Trade History</h1>
        <button
          onClick={() => exportCSV(trades)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm text-text-secondary hover:text-text-primary hover:border-accent/40 transition-colors"
        >
          <Download size={14} />
          Export CSV
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Total Trades" value={String(total)} icon={BarChart3} />
        <StatCard
          label="Win Rate"
          value={`${winRate.toFixed(1)}%`}
          positive={winRate >= 50}
          icon={Target}
        />
        <StatCard
          label="Total P&L"
          value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`}
          positive={totalPnl >= 0}
          icon={DollarSign}
        />
        <StatCard
          label="Best Trade"
          value={`+$${bestTrade.toFixed(2)}`}
          positive={true}
          icon={TrendingUp}
        />
        <StatCard
          label="Worst Trade"
          value={`-$${Math.abs(worstTrade).toFixed(2)}`}
          positive={false}
          icon={TrendingDown}
        />
      </div>

      {/* P&L Chart */}
      {pnlCurve.length > 1 && (
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
            Cumulative P&L
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={pnlCurve}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2029" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: "#6b7280" }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
              <Tooltip
                contentStyle={{
                  background: "#111318",
                  border: "1px solid #1e2029",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "#f0f2f5",
                }}
                formatter={(val: number) => [`$${val.toFixed(2)}`, "P&L"]}
              />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke={totalPnl >= 0 ? "#00d4aa" : "#ff3b5c"}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Asset</label>
            <select
              value={filterAsset}
              onChange={(e) => setFilterAsset(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
            >
              <option value="all">All Assets</option>
              {ASSETS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Mode</label>
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
            >
              <option value="all">All Modes</option>
              <option value="demo">Demo</option>
              <option value="live">Live</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Result</label>
            <select
              value={filterResult}
              onChange={(e) => setFilterResult(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
            >
              <option value="all">All Results</option>
              <option value="WIN">WIN</option>
              <option value="LOSS">LOSS</option>
              <option value="PENDING">PENDING</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">From</label>
            <input
              type="date"
              value={filterStartDate}
              onChange={(e) => setFilterStartDate(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">To</label>
            <input
              type="date"
              value={filterEndDate}
              onChange={(e) => setFilterEndDate(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-8 text-center text-muted">Loading trades…</div>
        ) : (
          <TradeLog trades={paginated} />
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <span className="text-xs text-muted">
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded border border-border text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Prev
              </button>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded border border-border text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  Play,
  BarChart3,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Target,
  DollarSign,
  Activity,
} from "lucide-react";
import { runBacktest, BacktestResult } from "@/lib/api";
import TradeLog from "@/components/TradeLog";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { format, subDays } from "date-fns";

const ASSETS = [
  "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURGBP","NZDUSD","USDCHF",
  "EURJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD","LTCUSD","SOLUSD","XRPUSD",
];

function StatCard({
  label,
  value,
  positive,
  icon: Icon,
  sub,
}: {
  label: string;
  value: string;
  positive?: boolean;
  icon: React.ElementType;
  sub?: string;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-muted" />
        <span className="text-xs text-muted uppercase tracking-wide">{label}</span>
      </div>
      <div
        className={[
          "text-2xl font-bold",
          positive === true ? "text-accent" : positive === false ? "text-danger" : "text-text-primary",
        ].join(" ")}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function BacktestPage() {
  const defaultEnd = format(new Date(), "yyyy-MM-dd");
  const defaultStart = format(subDays(new Date(), 90), "yyyy-MM-dd");

  const [asset, setAsset] = useState("EURUSD");
  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    if (!asset || !startDate || !endDate) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runBacktest(asset, startDate, endDate);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Backtest failed");
    }
    setLoading(false);
  }

  // Build P&L curve with timestamps
  const pnlCurveData =
    result?.pnl_curve.map((pnl, i) => ({
      i: i + 1,
      pnl: parseFloat(pnl.toFixed(2)),
    })) ?? [];

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-text-primary">Strategy Backtester</h1>
        <p className="text-sm text-muted mt-0.5">
          Simulate PocketBot's indicator strategy on historical data
        </p>
      </div>

      {/* Configuration */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          Backtest Configuration
        </h2>
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="text-xs text-muted block mb-1.5">Asset</label>
            <select
              value={asset}
              onChange={(e) => setAsset(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            >
              {ASSETS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted block mb-1.5">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1.5">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate}
              max={format(new Date(), "yyyy-MM-dd")}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>
          <button
            onClick={handleRun}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent border border-accent/40 text-sm font-semibold transition-all disabled:opacity-50"
          >
            <Play size={14} />
            {loading ? "Running…" : "Run Backtest"}
          </button>
        </div>

        {/* Date presets */}
        <div className="flex gap-2 mt-3">
          {[
            { label: "7 days", days: 7 },
            { label: "30 days", days: 30 },
            { label: "90 days", days: 90 },
          ].map(({ label, days }) => (
            <button
              key={days}
              onClick={() => {
                setStartDate(format(subDays(new Date(), days), "yyyy-MM-dd"));
                setEndDate(format(new Date(), "yyyy-MM-dd"));
              }}
              className="text-xs px-3 py-1 rounded border border-border text-text-secondary hover:text-accent hover:border-accent/40 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="card p-8 text-center">
          <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin mx-auto mb-3" />
          <div className="text-sm text-text-secondary">
            Fetching historical data and running simulation…
          </div>
          <div className="text-xs text-muted mt-1">This may take 30–60 seconds</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card p-4 border-danger/30 bg-danger/5">
          <div className="flex items-center gap-2 text-danger text-sm">
            <AlertTriangle size={16} />
            {error}
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-5 animate-[fadeIn_0.3s_ease-in-out]">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Simulated Trades"
              value={String(result.total_trades)}
              icon={BarChart3}
              sub={`${result.wins}W / ${result.losses}L`}
            />
            <StatCard
              label="Win Rate"
              value={`${result.win_rate.toFixed(1)}%`}
              positive={result.win_rate >= 50}
              icon={Target}
            />
            <StatCard
              label="Total P&L"
              value={`${result.total_pnl >= 0 ? "+" : ""}$${result.total_pnl.toFixed(2)}`}
              positive={result.total_pnl >= 0}
              icon={DollarSign}
              sub="At $10/trade, 85% payout"
            />
            <StatCard
              label="Max Drawdown"
              value={`-$${result.max_drawdown.toFixed(2)}`}
              positive={false}
              icon={Activity}
              sub="Peak-to-trough loss"
            />
          </div>

          {/* P&L Curve */}
          {pnlCurveData.length > 1 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
                Cumulative P&L Curve
              </h2>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={pnlCurveData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2029" />
                  <XAxis
                    dataKey="i"
                    tick={{ fontSize: 10, fill: "#6b7280" }}
                    label={{ value: "Trade #", position: "insideBottomRight", fontSize: 10, fill: "#6b7280" }}
                  />
                  <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
                  <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="4 4" />
                  <Tooltip
                    contentStyle={{
                      background: "#111318",
                      border: "1px solid #1e2029",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "#f0f2f5",
                    }}
                    formatter={(val: number) => [`$${val.toFixed(2)}`, "Cumulative P&L"]}
                    labelFormatter={(i) => `Trade #${i}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="pnl"
                    stroke={result.total_pnl >= 0 ? "#00d4aa" : "#ff3b5c"}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade results table */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
              Simulated Trades ({result.total_trades})
            </h2>
            <TradeLog trades={result.trades} limit={100} />
          </div>

          {/* Disclaimer */}
          <div className="bg-warning/5 border border-warning/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="text-warning mt-0.5 flex-shrink-0" />
              <div className="text-sm text-warning/90 space-y-1">
                <p className="font-semibold">Backtest Limitations</p>
                <p>
                  This backtest uses 1-hour OHLCV candles from Yahoo Finance and simulates trades at
                  the close of each bar. Real trading involves slippage, variable payouts, and
                  execution delays not captured here.
                </p>
                <p>
                  <strong>Past performance does not guarantee future results.</strong> Binary options
                  carry significant risk of capital loss. Only trade with funds you can afford to lose.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Initial info state */}
      {!result && !loading && !error && (
        <div className="card p-8 text-center">
          <BarChart3 size={40} className="text-muted mx-auto mb-3" />
          <div className="text-text-secondary font-medium">Configure and run a backtest</div>
          <div className="text-sm text-muted mt-1">
            Select an asset and date range, then click Run Backtest to simulate the strategy
          </div>
        </div>
      )}
    </div>
  );
}

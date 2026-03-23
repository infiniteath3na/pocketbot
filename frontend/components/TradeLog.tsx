"use client";

import { useState, useEffect } from "react";
import { Trade } from "@/lib/api";
import { format } from "date-fns";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";

interface TradeLogProps {
  trades: Trade[];
  showFilters?: boolean;
  limit?: number;
}

function useNow() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  return now;
}

function CountdownTimer({ entryTime, expirySecs, result }: {
  entryTime: string;
  expirySecs: number;
  result: string;
}) {
  const now = useNow();

  if (result !== "PENDING") {
    return (
      <span className="text-xs text-muted">
        {expirySecs >= 60 ? `${expirySecs / 60}m` : `${expirySecs}s`}
      </span>
    );
  }

  try {
    const utcStr = entryTime.endsWith("Z") || entryTime.includes("+") ? entryTime : entryTime + "Z";
    const entry = new Date(utcStr).getTime();
    const expiry = entry + expirySecs * 1000;
    const remaining = Math.max(0, Math.floor((expiry - now) / 1000));

    if (remaining === 0) {
      return <span className="text-xs text-yellow-400 font-bold animate-pulse">EXPIRING</span>;
    }

    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    const display = mins > 0
      ? `${mins}:${secs.toString().padStart(2, "0")}`
      : `${secs}s`;

    const pct = remaining / expirySecs;
    const color = pct > 0.5 ? "text-accent" : pct > 0.25 ? "text-yellow-400" : "text-danger";

    return (
      <span className={`text-xs font-mono font-bold ${color} flex items-center gap-1`}>
        <Clock size={10} className="animate-pulse" />
        {display}
      </span>
    );
  } catch {
    return <span className="text-xs text-muted">{expirySecs}s</span>;
  }
}

function formatEntryTime(entryTime: string): string {
  try {
    // Backend stores UTC — append Z if no timezone info present so JS parses as UTC
    const utcStr = entryTime.endsWith("Z") || entryTime.includes("+") ? entryTime : entryTime + "Z";
    const date = new Date(utcStr);
    // format() uses local system timezone automatically
    return format(date, "MM/dd h:mm:ss aa");
  } catch {
    return entryTime;
  }
}

export default function TradeLog({ trades, showFilters = false, limit }: TradeLogProps) {
  const [filterResult, setFilterResult] = useState<string>("all");
  const [filterAsset, setFilterAsset] = useState<string>("all");

  const assets = Array.from(new Set(trades.map((t) => t.asset))).sort();

  let filtered = trades;
  if (filterResult !== "all") {
    filtered = filtered.filter((t) => t.result === filterResult.toUpperCase());
  }
  if (filterAsset !== "all") {
    filtered = filtered.filter((t) => t.asset === filterAsset);
  }

  const displayed = limit ? filtered.slice(0, limit) : filtered;

  function resultBadge(result: string) {
    const classes: Record<string, string> = {
      WIN: "badge-win text-xs px-2 py-0.5 rounded font-semibold",
      LOSS: "badge-loss text-xs px-2 py-0.5 rounded font-semibold",
      PENDING: "badge-pending text-xs px-2 py-0.5 rounded font-semibold",
    };
    return <span className={classes[result] || "text-muted text-xs"}>{result}</span>;
  }

  function directionBadge(direction: string) {
    return (
      <span className={[
        "text-xs font-bold px-2 py-0.5 rounded-full",
        direction === "CALL" ? "badge-call" : "badge-put",
      ].join(" ")}>
        {direction}
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {showFilters && (
        <div className="flex gap-2 flex-wrap">
          <select
            value={filterResult}
            onChange={(e) => setFilterResult(e.target.value)}
            className="text-xs bg-surface border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
          >
            <option value="all">All Results</option>
            <option value="win">WIN</option>
            <option value="loss">LOSS</option>
            <option value="pending">PENDING</option>
          </select>
          <select
            value={filterAsset}
            onChange={(e) => setFilterAsset(e.target.value)}
            className="text-xs bg-surface border border-border rounded px-2 py-1.5 text-text-secondary focus:outline-none focus:border-accent/50"
          >
            <option value="all">All Assets</option>
            {assets.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      )}

      {displayed.length === 0 ? (
        <div className="text-center py-8 text-muted text-sm">No trades found</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted uppercase tracking-wide">
                <th className="text-left pb-2 pr-4">#</th>
                <th className="text-left pb-2 pr-4">Asset</th>
                <th className="text-left pb-2 pr-4">Dir</th>
                <th className="text-right pb-2 pr-4">Amount</th>
                <th className="text-left pb-2 pr-4">Entry Time</th>
                <th className="text-left pb-2 pr-4">Expires</th>
                <th className="text-left pb-2 pr-4">Result</th>
                <th className="text-right pb-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((trade) => (
                <tr
                  key={trade.id}
                  className={[
                    "border-b border-border/50 hover:bg-white/2 transition-colors",
                    trade.result === "PENDING" ? "bg-yellow-500/3" : "",
                  ].join(" ")}
                >
                  <td className="py-2.5 pr-4 text-muted text-xs">{trade.id}</td>
                  <td className="py-2.5 pr-4 font-medium">{trade.asset}</td>
                  <td className="py-2.5 pr-4">{directionBadge(trade.direction)}</td>
                  <td className="py-2.5 pr-4 text-right font-mono text-text-secondary">
                    ${trade.amount.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-muted font-mono">
                    {trade.entry_time ? formatEntryTime(trade.entry_time) : "—"}
                  </td>
                  <td className="py-2.5 pr-4">
                    <CountdownTimer
                      entryTime={trade.entry_time || ""}
                      expirySecs={trade.expiry_seconds}
                      result={trade.result}
                    />
                  </td>
                  <td className="py-2.5 pr-4">{resultBadge(trade.result)}</td>
                  <td className={[
                    "py-2.5 text-right font-mono font-semibold",
                    trade.pnl > 0 ? "text-accent" : trade.pnl < 0 ? "text-danger" : "text-muted",
                  ].join(" ")}>
                    {trade.pnl >= 0 ? "+" : ""}{trade.pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { Trade } from "@/lib/api";
import { formatDistanceToNow, format } from "date-fns";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";

interface TradeLogProps {
  trades: Trade[];
  showFilters?: boolean;
  limit?: number;
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
      <span
        className={[
          "text-xs font-bold px-2 py-0.5 rounded-full",
          direction === "CALL" ? "badge-call" : "badge-put",
        ].join(" ")}
      >
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
              <option key={a} value={a}>
                {a}
              </option>
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
                <th className="text-left pb-2 pr-4">Time</th>
                <th className="text-left pb-2 pr-4">Expiry</th>
                <th className="text-left pb-2 pr-4">Result</th>
                <th className="text-right pb-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((trade, idx) => (
                <tr
                  key={trade.id}
                  className="border-b border-border/50 hover:bg-white/2 transition-colors"
                >
                  <td className="py-2.5 pr-4 text-muted text-xs">{trade.id}</td>
                  <td className="py-2.5 pr-4 font-medium">{trade.asset}</td>
                  <td className="py-2.5 pr-4">{directionBadge(trade.direction)}</td>
                  <td className="py-2.5 pr-4 text-right font-mono text-text-secondary">
                    ${trade.amount.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-muted">
                    {trade.entry_time
                      ? (() => {
                          try {
                            return format(new Date(trade.entry_time), "MM/dd HH:mm");
                          } catch {
                            return trade.entry_time;
                          }
                        })()
                      : "—"}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-muted">
                    {trade.expiry_seconds >= 60
                      ? `${trade.expiry_seconds / 60}m`
                      : `${trade.expiry_seconds}s`}
                  </td>
                  <td className="py-2.5 pr-4">{resultBadge(trade.result)}</td>
                  <td
                    className={[
                      "py-2.5 text-right font-mono font-semibold",
                      trade.pnl > 0 ? "text-accent" : trade.pnl < 0 ? "text-danger" : "text-muted",
                    ].join(" ")}
                  >
                    {trade.pnl >= 0 ? "+" : ""}
                    {trade.pnl.toFixed(2)}
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

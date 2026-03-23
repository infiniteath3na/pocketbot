"use client";

import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Zap,
} from "lucide-react";
import { getAssets, getSettings, placeTrade, Asset, Settings } from "@/lib/api";
import { format } from "date-fns";

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 70 ? "#00d4aa" : value >= 50 ? "#f59e0b" : "#ff3b5c";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono font-bold w-8 text-right" style={{ color }}>
        {value.toFixed(0)}
      </span>
    </div>
  );
}

function IndicatorDot({ score }: { score: number }) {
  const color = score >= 65 ? "#00d4aa" : score >= 45 ? "#f59e0b" : "#ff3b5c";
  return (
    <span className="text-xs font-mono font-semibold" style={{ color }}>
      {score.toFixed(0)}
    </span>
  );
}

export default function ScannerPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [sortKey, setSortKey] = useState<"confidence" | "price_change_pct">("confidence");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [expandedAsset, setExpandedAsset] = useState<string | null>(null);
  const [tradingAsset, setTradingAsset] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [assetsRes, settingsRes] = await Promise.allSettled([getAssets(), getSettings()]);
      if (assetsRes.status === "fulfilled") setAssets(assetsRes.value.assets);
      if (settingsRes.status === "fulfilled") setSettings(settingsRes.value);
      setLastUpdated(new Date());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const threshold = parseFloat(settings.confidence_threshold || "70");

  const sorted = [...assets].sort((a, b) => {
    const va = a[sortKey] ?? 0;
    const vb = b[sortKey] ?? 0;
    return sortDir === "desc" ? (vb as number) - (va as number) : (va as number) - (vb as number);
  });

  function toggleSort(key: "confidence" | "price_change_pct") {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  async function handleTrade(asset: Asset) {
    if (asset.confidence < threshold) return;
    setTradingAsset(asset.asset);
    try {
      await placeTrade(asset.asset, asset.direction, parseFloat(settings.trade_size || "10"));
    } catch (e) {
      console.error(e);
    } finally {
      setTradingAsset(null);
    }
  }

  function rowBg(confidence: number) {
    if (confidence >= 75) return "hover:bg-accent/5";
    if (confidence >= 55) return "hover:bg-warning/5";
    return "hover:bg-danger/5";
  }

  function SortIcon({ column }: { column: string }) {
    if (sortKey !== column) return null;
    return sortDir === "desc" ? <ChevronDown size={12} /> : <ChevronUp size={12} />;
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Asset Scanner</h1>
          <p className="text-sm text-muted mt-0.5">
            {assets.filter((a) => a.confidence >= threshold).length} signals above{" "}
            {threshold}% threshold
            {lastUpdated && (
              <span className="ml-2">
                · Updated {format(lastUpdated, "HH:mm:ss")}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted uppercase tracking-wide">
                <th className="text-left px-4 py-3">Asset</th>
                <th className="text-right px-4 py-3">Price</th>
                <th
                  className="text-left px-4 py-3 cursor-pointer select-none"
                  onClick={() => toggleSort("confidence")}
                >
                  <span className="flex items-center gap-1">
                    Confidence <SortIcon column="confidence" />
                  </span>
                </th>
                <th className="text-left px-4 py-3">Direction</th>
                <th className="text-right px-4 py-3">RSI</th>
                <th className="text-right px-4 py-3">MACD</th>
                <th className="text-right px-4 py-3">BB</th>
                <th className="text-right px-4 py-3">EMA</th>
                <th className="text-right px-4 py-3">Vol</th>
                <th className="text-right px-4 py-3">Candle</th>
                <th className="text-left px-4 py-3">Signal</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && assets.length === 0 ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-border/50">
                    {Array.from({ length: 12 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-border/50 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (
                sorted.map((asset) => {
                  const isExpanded = expandedAsset === asset.asset;
                  const canTrade = asset.confidence >= threshold;
                  const priceUp = asset.price_change_pct >= 0;

                  return (
                    <>
                      <tr
                        key={asset.asset}
                        className={[
                          "border-b border-border/50 cursor-pointer transition-colors",
                          rowBg(asset.confidence),
                          isExpanded ? "bg-white/3" : "",
                        ].join(" ")}
                        onClick={() => setExpandedAsset(isExpanded ? null : asset.asset)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span>{asset.flag}</span>
                            <div>
                              <div className="font-semibold text-text-primary">{asset.display_name}</div>
                              <div className="text-xs text-muted">{asset.asset}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="font-mono text-text-primary">{asset.price.toFixed(5)}</div>
                          <div
                            className={[
                              "text-xs flex items-center justify-end gap-0.5",
                              priceUp ? "text-accent" : "text-danger",
                            ].join(" ")}
                          >
                            {priceUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                            {priceUp ? "+" : ""}{asset.price_change_pct.toFixed(3)}%
                          </div>
                        </td>
                        <td className="px-4 py-3 min-w-[140px]">
                          <ConfidenceBar value={asset.confidence} />
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={[
                              "text-xs font-bold px-2 py-0.5 rounded-full",
                              asset.direction === "CALL" ? "badge-call" : "badge-put",
                            ].join(" ")}
                          >
                            {asset.direction}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.RSI ?? 50} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.MACD ?? 50} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.Bollinger ?? 50} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.EMA ?? 50} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.Volume ?? 50} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <IndicatorDot score={asset.indicators?.Candlestick ?? 50} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1 flex-wrap">
                            {asset.top_indicators.slice(0, 2).map((ind) => (
                              <span
                                key={ind}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20"
                              >
                                {ind}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTrade(asset);
                            }}
                            disabled={!canTrade || tradingAsset === asset.asset}
                            className={[
                              "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border",
                              canTrade
                                ? asset.direction === "CALL"
                                  ? "badge-call hover:bg-accent/25"
                                  : "badge-put hover:bg-danger/25"
                                : "bg-white/5 text-muted border-border cursor-not-allowed",
                            ].join(" ")}
                          >
                            {tradingAsset === asset.asset ? "…" : "Trade Now"}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded row */}
                      {isExpanded && (
                        <tr key={`${asset.asset}-expanded`} className="border-b border-border/50 bg-white/2">
                          <td colSpan={12} className="px-6 py-4">
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                              {[
                                {
                                  name: "RSI",
                                  score: asset.indicators?.RSI,
                                  detail: `Value: ${asset.indicators?.rsi_value?.toFixed(1) ?? "—"}`,
                                },
                                {
                                  name: "MACD",
                                  score: asset.indicators?.MACD,
                                  detail: `Hist: ${asset.indicators?.macd_histogram?.toFixed(6) ?? "—"}`,
                                },
                                {
                                  name: "Bollinger Bands",
                                  score: asset.indicators?.Bollinger,
                                  detail: `Upper: ${asset.indicators?.bb_upper?.toFixed(4) ?? "—"}`,
                                },
                                {
                                  name: "EMA 9/21",
                                  score: asset.indicators?.EMA,
                                  detail: `9: ${asset.indicators?.ema9?.toFixed(5) ?? "—"} / 21: ${asset.indicators?.ema21?.toFixed(5) ?? "—"}`,
                                },
                                {
                                  name: "Volume",
                                  score: asset.indicators?.Volume,
                                  detail: "vs 20-period avg",
                                },
                                {
                                  name: "Candlestick",
                                  score: asset.indicators?.Candlestick,
                                  detail: "Pattern analysis",
                                },
                              ].map(({ name, score, detail }) => {
                                const s = score ?? 50;
                                const col = s >= 65 ? "#00d4aa" : s >= 45 ? "#f59e0b" : "#ff3b5c";
                                return (
                                  <div key={name} className="bg-surface rounded-lg p-3 border border-border">
                                    <div className="text-xs text-muted mb-1">{name}</div>
                                    <div className="text-lg font-bold" style={{ color: col }}>
                                      {s.toFixed(0)}
                                    </div>
                                    <div className="text-[10px] text-muted mt-1">{detail}</div>
                                    <div className="mt-2 h-1 bg-border rounded-full overflow-hidden">
                                      <div
                                        className="h-full rounded-full"
                                        style={{ width: `${s}%`, background: col }}
                                      />
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                            {asset.error && (
                              <p className="mt-2 text-xs text-danger">{asset.error}</p>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

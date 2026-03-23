"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";
import { Asset, placeTrade } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

interface AssetCardProps {
  asset: Asset;
  onTrade?: (asset: Asset, direction: "CALL" | "PUT") => void;
  confidenceThreshold?: number;
}

function formatPrice(price: number, asset: string): string {
  if (price === 0) return "—";
  if (asset.includes("JPY") || asset === "USDJPY" || asset === "EURJPY") {
    return price.toFixed(3);
  }
  if (["BTCUSD", "ETHUSD", "XAUUSD"].includes(asset)) {
    return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return price.toFixed(5);
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 70) return "#00d4aa";
  if (confidence >= 50) return "#f59e0b";
  return "#ff3b5c";
}

export default function AssetCard({
  asset,
  onTrade,
  confidenceThreshold = 70,
}: AssetCardProps) {
  const [trading, setTrading] = useState(false);
  const [tradeMsg, setTradeMsg] = useState<string | null>(null);

  const color = getConfidenceColor(asset.confidence);
  const canTrade = asset.confidence >= confidenceThreshold && !trading;

  async function handleTrade() {
    if (!canTrade) return;
    setTrading(true);
    setTradeMsg(null);
    try {
      await placeTrade(asset.asset, asset.direction, 10);
      setTradeMsg("Placed!");
      onTrade?.(asset, asset.direction);
    } catch (e: any) {
      setTradeMsg("Error");
    } finally {
      setTrading(false);
      setTimeout(() => setTradeMsg(null), 2000);
    }
  }

  const priceUp = asset.price_change_pct >= 0;

  return (
    <div className="card p-4 flex flex-col gap-3 hover:border-white/10 transition-all duration-200">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none">{asset.flag}</span>
          <div>
            <div className="font-semibold text-sm text-text-primary">{asset.display_name}</div>
            <div className="text-xs text-muted">{asset.asset}</div>
          </div>
        </div>
        {/* Direction badge */}
        <span
          className={[
            "text-xs font-bold px-2 py-0.5 rounded-full",
            asset.direction === "CALL" ? "badge-call" : "badge-put",
          ].join(" ")}
        >
          {asset.direction}
        </span>
      </div>

      {/* Price */}
      <div className="flex items-end justify-between">
        <div>
          <div className="font-mono text-base font-bold text-text-primary">
            {formatPrice(asset.price, asset.asset)}
          </div>
          <div
            className={[
              "flex items-center gap-1 text-xs font-medium mt-0.5",
              priceUp ? "text-accent" : "text-danger",
            ].join(" ")}
          >
            {priceUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {priceUp ? "+" : ""}
            {asset.price_change_pct.toFixed(3)}%
          </div>
        </div>
        {/* Expiry badge */}
        <div className="flex items-center gap-1 text-xs text-muted">
          <Clock size={11} />
          {asset.expiry}
        </div>
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-muted">Confidence</span>
          <span className="text-xs font-bold" style={{ color }}>
            {asset.confidence.toFixed(1)}%
          </span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${asset.confidence}%`, background: color }}
          />
        </div>
      </div>

      {/* Top indicators */}
      {asset.top_indicators.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {asset.top_indicators.slice(0, 3).map((ind) => (
            <span
              key={ind}
              className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-text-secondary border border-border"
            >
              {ind}
            </span>
          ))}
        </div>
      )}

      {/* Trade button */}
      <button
        onClick={handleTrade}
        disabled={!canTrade}
        className={[
          "w-full py-2 rounded-lg text-sm font-semibold transition-all duration-150",
          canTrade
            ? asset.direction === "CALL"
              ? "bg-accent/20 hover:bg-accent/30 text-accent border border-accent/40"
              : "bg-danger/20 hover:bg-danger/30 text-danger border border-danger/40"
            : "bg-white/5 text-muted cursor-not-allowed border border-border",
        ].join(" ")}
      >
        {trading ? "Placing…" : tradeMsg || (canTrade ? `Trade ${asset.direction}` : "Low Signal")}
      </button>
    </div>
  );
}

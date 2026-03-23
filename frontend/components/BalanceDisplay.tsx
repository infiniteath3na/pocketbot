"use client";
import { useEffect, useState } from "react";

interface BalanceData {
  demo_balance: number | null;
  live_balance: number | null;
  active_mode: string;
  demo_connected: boolean;
  live_connected: boolean;
  last_updated: string;
}

export default function BalanceDisplay() {
  const [balance, setBalance] = useState<BalanceData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchBalance = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/balance`);
      if (res.ok) {
        const data = await res.json();
        setBalance(data);
      }
    } catch (e) {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBalance();
    const interval = setInterval(fetchBalance, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const formatBalance = (val: number | null) => {
    if (val === null) return "—";
    return `$${val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-700 rounded-xl p-4 animate-pulse">
            <div className="h-3 bg-gray-700 rounded w-20 mb-3" />
            <div className="h-8 bg-gray-700 rounded w-32" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Demo Balance */}
      <div className={`bg-gray-900 border rounded-xl p-4 transition-all ${
        balance?.active_mode === "demo"
          ? "border-yellow-500/50 shadow-lg shadow-yellow-500/10"
          : "border-gray-700"
      }`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400 uppercase tracking-wider font-medium">Demo</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            balance?.active_mode === "demo"
              ? "bg-yellow-500/20 text-yellow-400"
              : "bg-gray-700 text-gray-500"
          }`}>
            {balance?.active_mode === "demo" ? "ACTIVE" : "INACTIVE"}
          </span>
        </div>
        <div className="text-2xl font-bold text-white mt-1">
          {formatBalance(balance?.demo_balance ?? null)}
        </div>
        <div className={`text-xs mt-1 ${balance?.demo_connected ? "text-green-400" : "text-gray-500"}`}>
          {balance?.demo_connected ? "● Connected" : "○ Not connected"}
        </div>
      </div>

      {/* Live Balance */}
      <div className={`bg-gray-900 border rounded-xl p-4 transition-all ${
        balance?.active_mode === "live"
          ? "border-green-500/50 shadow-lg shadow-green-500/10"
          : "border-gray-700"
      }`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400 uppercase tracking-wider font-medium">Live</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            balance?.active_mode === "live"
              ? "bg-green-500/20 text-green-400"
              : "bg-gray-700 text-gray-500"
          }`}>
            {balance?.active_mode === "live" ? "ACTIVE" : "INACTIVE"}
          </span>
        </div>
        <div className={`text-2xl font-bold mt-1 ${
          balance?.active_mode === "live" ? "text-green-400" : "text-gray-400"
        }`}>
          {formatBalance(balance?.live_balance ?? null)}
        </div>
        <div className={`text-xs mt-1 ${balance?.live_connected ? "text-green-400" : "text-gray-500"}`}>
          {balance?.live_connected ? "● Connected" : "○ No SSID configured"}
        </div>
      </div>
    </div>
  );
}

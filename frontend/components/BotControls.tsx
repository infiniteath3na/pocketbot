"use client";

import { useState, useEffect } from "react";
import { Play, Square, AlertTriangle, Activity, CheckCircle, XCircle } from "lucide-react";
import { BotStatus, startBot, stopBot, getBotStatus, updateSettings } from "@/lib/api";

interface BotControlsProps {
  onStatusChange?: (status: BotStatus) => void;
}

export default function BotControls({ onStatusChange }: BotControlsProps) {
  const [status, setStatus] = useState<BotStatus>({
    running: false,
    mode: "demo",
    active_trades: 0,
    auto_trade: false,
  });
  const [loading, setLoading] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const [tradeCount, setTradeCount] = useState(0);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadStatus() {
    try {
      const s = await getBotStatus();
      setStatus(s);
      onStatusChange?.(s);
    } catch {}
  }

  async function handleStartStop() {
    setLoading(true);
    try {
      if (status.running) {
        await stopBot();
      } else {
        await startBot();
      }
      await loadStatus();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSwitchToLive() {
    setShowLiveModal(true);
  }

  async function confirmSwitchToLive() {
    setShowLiveModal(false);
    try {
      await updateSettings({ mode: "live" });
      await loadStatus();
    } catch (e) {
      console.error(e);
    }
  }

  async function switchToDemo() {
    try {
      await updateSettings({ mode: "demo" });
      await loadStatus();
    } catch (e) {
      console.error(e);
    }
  }

  const isRunning = status.running;
  const isLive = status.mode === "live";

  return (
    <>
      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-border">
          {isRunning ? (
            <>
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <Activity size={13} className="text-accent" />
              <span className="text-xs font-medium text-accent">Running</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-muted" />
              <span className="text-xs font-medium text-muted">Stopped</span>
            </>
          )}
        </div>

        {/* Active trades */}
        {isRunning && (
          <div className="text-xs text-text-secondary px-2 py-1.5 bg-surface border border-border rounded-lg">
            <span className="font-semibold text-text-primary">{status.active_trades}</span> active
          </div>
        )}

        {/* Mode badge */}
        <span
          className={[
            "text-xs font-bold px-2.5 py-1 rounded-full border",
            isLive
              ? "text-orange-400 bg-orange-400/15 border-orange-400/30"
              : "text-blue-400 bg-blue-400/15 border-blue-400/30",
          ].join(" ")}
        >
          {isLive ? "LIVE" : "DEMO"}
        </span>

        {/* Start/Stop button */}
        <button
          onClick={handleStartStop}
          disabled={loading}
          className={[
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-150 border",
            isRunning
              ? "bg-danger/20 hover:bg-danger/30 text-danger border-danger/40"
              : "bg-accent/20 hover:bg-accent/30 text-accent border-accent/40",
            loading ? "opacity-50 cursor-not-allowed" : "",
          ].join(" ")}
        >
          {isRunning ? <Square size={14} /> : <Play size={14} />}
          {loading ? "…" : isRunning ? "Stop Bot" : "Start Bot"}
        </button>

        {/* Mode switch */}
        {!isLive ? (
          <button
            onClick={handleSwitchToLive}
            className="text-xs px-3 py-2 rounded-lg border border-orange-400/30 text-orange-400 bg-orange-400/10 hover:bg-orange-400/20 transition-colors"
          >
            Switch to Live
          </button>
        ) : (
          <button
            onClick={switchToDemo}
            className="text-xs px-3 py-2 rounded-lg border border-blue-400/30 text-blue-400 bg-blue-400/10 hover:bg-blue-400/20 transition-colors"
          >
            Switch to Demo
          </button>
        )}
      </div>

      {/* Live mode confirmation modal */}
      {showLiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="card max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-orange-400/20 flex items-center justify-center">
                <AlertTriangle size={20} className="text-orange-400" />
              </div>
              <div>
                <h3 className="font-bold text-text-primary">Switch to Live Trading?</h3>
                <p className="text-xs text-muted mt-0.5">This will use real money</p>
              </div>
            </div>
            <div className="bg-orange-400/10 border border-orange-400/30 rounded-lg p-3 mb-5">
              <p className="text-sm text-orange-300">
                <strong>Warning:</strong> Live trading uses real money. You can lose your entire
                investment. Only proceed if you understand the risks and have configured your Live
                SSID in Settings.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowLiveModal(false)}
                className="flex-1 py-2 rounded-lg border border-border text-text-secondary hover:bg-white/5 text-sm transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmSwitchToLive}
                className="flex-1 py-2 rounded-lg bg-orange-400/20 text-orange-400 border border-orange-400/40 hover:bg-orange-400/30 text-sm font-semibold transition-colors"
              >
                Confirm Live Mode
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

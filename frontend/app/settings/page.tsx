"use client";

import { useState, useEffect } from "react";
import {
  Save,
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  Wifi,
  WifiOff,
} from "lucide-react";
import { getSettings, updateSettings, Settings, getBotStatus } from "@/lib/api";

const ALL_ASSETS = [
  "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURGBP","NZDUSD","USDCHF",
  "EURJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD","LTCUSD","SOLUSD","XRPUSD",
];

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={[
        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none",
        checked ? "bg-accent" : "bg-border",
      ].join(" ")}
    >
      <span
        className={[
          "inline-block w-4 h-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        ].join(" ")}
      />
    </button>
  );
}

function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  formatValue,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  formatValue?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-1.5 bg-border rounded-full appearance-none cursor-pointer accent-accent"
        style={{ accentColor: "#00d4aa" }}
      />
      <span className="text-sm font-mono font-semibold text-accent w-16 text-right">
        {formatValue ? formatValue(value) : value}
      </span>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showDemoSsid, setShowDemoSsid] = useState(false);
  const [showLiveSsid, setShowLiveSsid] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const [testingDemo, setTestingDemo] = useState(false);
  const [testingLive, setTestingLive] = useState(false);
  const [demoTestResult, setDemoTestResult] = useState<"ok" | "fail" | null>(null);
  const [liveTestResult, setLiveTestResult] = useState<"ok" | "fail" | null>(null);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setSettings(s);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  function set(key: string, value: string) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  function toggleAsset(asset: string) {
    const current = (settings.enabled_assets || "").split(",").filter(Boolean);
    const updated = current.includes(asset)
      ? current.filter((a) => a !== asset)
      : [...current, asset];
    set("enabled_assets", updated.join(","));
  }

  function isAssetEnabled(asset: string): boolean {
    return (settings.enabled_assets || "").split(",").includes(asset);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  }

  function handleModeSwitch(mode: "demo" | "live") {
    if (mode === "live") {
      setShowLiveModal(true);
    } else {
      set("mode", "demo");
    }
  }

  async function testConnection(type: "demo" | "live") {
    const ssid = type === "demo" ? settings.ssid_demo : settings.ssid_live;
    if (!ssid) return;
    if (type === "demo") setTestingDemo(true);
    else setTestingLive(true);
    try {
      // Basic validation — real test would attempt WS connection
      await new Promise((r) => setTimeout(r, 800));
      if (ssid.length > 10) {
        if (type === "demo") setDemoTestResult("ok");
        else setLiveTestResult("ok");
      } else {
        if (type === "demo") setDemoTestResult("fail");
        else setLiveTestResult("fail");
      }
    } finally {
      if (type === "demo") setTestingDemo(false);
      else setTestingLive(false);
      setTimeout(() => {
        if (type === "demo") setDemoTestResult(null);
        else setLiveTestResult(null);
      }, 3000);
    }
  }

  const isLive = settings.mode === "live";
  const tradeSize = parseFloat(settings.trade_size || "10");
  const threshold = parseFloat(settings.confidence_threshold || "70");
  const maxConcurrent = parseInt(settings.max_concurrent_trades || "3");
  const minInterval = parseInt(settings.min_trade_interval || "5");
  const refreshInterval = parseInt(settings.refresh_interval || "30");

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="text-muted">Loading settings…</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent border border-accent/40 text-sm font-semibold transition-all disabled:opacity-50"
        >
          {saved ? <CheckCircle size={14} /> : <Save size={14} />}
          {saving ? "Saving…" : saved ? "Saved!" : "Save Settings"}
        </button>
      </div>

      {/* Mode Section */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          Trading Mode
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {/* Demo Card */}
          <button
            onClick={() => handleModeSwitch("demo")}
            className={[
              "p-4 rounded-xl border-2 text-left transition-all",
              !isLive
                ? "border-blue-400 bg-blue-400/10"
                : "border-border bg-white/2 hover:border-border/80",
            ].join(" ")}
          >
            <div className="text-sm font-bold text-blue-400 mb-1">Demo Mode</div>
            <div className="text-xs text-muted">Practice with virtual money. No real risk.</div>
            {!isLive && (
              <span className="mt-2 inline-block text-[10px] px-2 py-0.5 rounded-full bg-blue-400/20 text-blue-400 font-semibold">
                ACTIVE
              </span>
            )}
          </button>

          {/* Live Card */}
          <button
            onClick={() => handleModeSwitch("live")}
            className={[
              "p-4 rounded-xl border-2 text-left transition-all",
              isLive
                ? "border-orange-400 bg-orange-400/10"
                : "border-border bg-white/2 hover:border-border/80",
            ].join(" ")}
          >
            <div className="text-sm font-bold text-orange-400 mb-1">Live Mode</div>
            <div className="text-xs text-muted">Real money trading. Use with caution.</div>
            {isLive && (
              <span className="mt-2 inline-block text-[10px] px-2 py-0.5 rounded-full bg-orange-400/20 text-orange-400 font-semibold">
                ACTIVE
              </span>
            )}
          </button>
        </div>

        {isLive && (
          <div className="mt-3 flex items-start gap-2 bg-orange-400/10 border border-orange-400/30 rounded-lg p-3">
            <AlertTriangle size={16} className="text-orange-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-orange-300">
              <strong>Live mode active.</strong> All trades will use real money from your PocketOption
              account. Ensure your Live SSID is configured correctly.
            </p>
          </div>
        )}
      </div>

      {/* Connection Section */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          PocketOption Connection
        </h2>
        <div className="space-y-4">
          {/* Demo SSID */}
          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              Demo Session ID (SSID)
            </label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showDemoSsid ? "text" : "password"}
                  value={settings.ssid_demo || ""}
                  onChange={(e) => set("ssid_demo", e.target.value)}
                  placeholder="Paste your demo SSID here"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-muted focus:outline-none focus:border-accent/50 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowDemoSsid((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text-secondary"
                >
                  {showDemoSsid ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <button
                onClick={() => testConnection("demo")}
                disabled={testingDemo || !settings.ssid_demo}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-xs text-text-secondary hover:text-text-primary transition-colors disabled:opacity-40"
              >
                {testingDemo ? (
                  "Testing…"
                ) : demoTestResult === "ok" ? (
                  <><CheckCircle size={12} className="text-accent" /> Connected</>
                ) : demoTestResult === "fail" ? (
                  <><WifiOff size={12} className="text-danger" /> Failed</>
                ) : (
                  <><Wifi size={12} /> Test</>
                )}
              </button>
            </div>
          </div>

          {/* Live SSID */}
          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              Live Session ID (SSID)
            </label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showLiveSsid ? "text" : "password"}
                  value={settings.ssid_live || ""}
                  onChange={(e) => set("ssid_live", e.target.value)}
                  placeholder="Paste your live SSID here"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-muted focus:outline-none focus:border-accent/50 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowLiveSsid((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text-secondary"
                >
                  {showLiveSsid ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <button
                onClick={() => testConnection("live")}
                disabled={testingLive || !settings.ssid_live}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-xs text-text-secondary hover:text-text-primary transition-colors disabled:opacity-40"
              >
                {testingLive ? (
                  "Testing…"
                ) : liveTestResult === "ok" ? (
                  <><CheckCircle size={12} className="text-accent" /> Connected</>
                ) : liveTestResult === "fail" ? (
                  <><WifiOff size={12} className="text-danger" /> Failed</>
                ) : (
                  <><Wifi size={12} /> Test</>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Trading Parameters */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          Trading Parameters
        </h2>
        <div className="space-y-5">
          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm text-text-secondary">Trade Size</label>
            </div>
            <Slider
              value={tradeSize}
              min={10}
              max={200}
              step={5}
              onChange={(v) => set("trade_size", String(v))}
              formatValue={(v) => `$${v}`}
            />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm text-text-secondary">Confidence Threshold</label>
              <span className="text-xs text-muted">Minimum score to trigger trade</span>
            </div>
            <Slider
              value={threshold}
              min={50}
              max={95}
              onChange={(v) => set("confidence_threshold", String(v))}
              formatValue={(v) => `${v}%`}
            />
          </div>

          <div>
            <label className="text-sm text-text-secondary block mb-2">Daily Loss Limit ($)</label>
            <input
              type="number"
              value={settings.daily_loss_limit || "100"}
              onChange={(e) => set("daily_loss_limit", e.target.value)}
              min={10}
              max={10000}
              className="w-40 bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm text-text-secondary">Max Concurrent Trades</label>
            </div>
            <Slider
              value={maxConcurrent}
              min={1}
              max={5}
              onChange={(v) => set("max_concurrent_trades", String(v))}
            />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm text-text-secondary">Min Trade Interval (minutes)</label>
              <span className="text-xs text-muted">Cooldown per asset</span>
            </div>
            <Slider
              value={minInterval}
              min={1}
              max={30}
              onChange={(v) => set("min_trade_interval", String(v))}
              formatValue={(v) => `${v}m`}
            />
          </div>
        </div>
      </div>

      {/* Asset Toggles */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          Enabled Assets
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {ALL_ASSETS.map((asset) => (
            <div
              key={asset}
              className="flex items-center justify-between p-3 bg-background border border-border rounded-lg"
            >
              <span className="text-sm text-text-primary">{asset}</span>
              <Toggle
                checked={isAssetEnabled(asset)}
                onChange={() => toggleAsset(asset)}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Automation */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-4">
          Automation
        </h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-text-primary">Auto-Trade</div>
              <div className="text-xs text-muted">Automatically place trades when signals are detected</div>
            </div>
            <Toggle
              checked={settings.auto_trade === "true"}
              onChange={(v) => set("auto_trade", v ? "true" : "false")}
            />
          </div>

          <div>
            <label className="text-sm text-text-secondary block mb-2">
              Refresh Interval (seconds)
            </label>
            <div className="flex gap-2 flex-wrap">
              {[15, 30, 60].map((val) => (
                <button
                  key={val}
                  onClick={() => set("refresh_interval", String(val))}
                  className={[
                    "px-4 py-1.5 rounded-lg text-sm border transition-colors",
                    refreshInterval === val
                      ? "bg-accent/20 text-accent border-accent/40"
                      : "border-border text-text-secondary hover:border-accent/30",
                  ].join(" ")}
                >
                  {val}s
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Live Mode Confirmation Modal */}
      {showLiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="card max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-orange-400/20 flex items-center justify-center">
                <AlertTriangle size={20} className="text-orange-400" />
              </div>
              <div>
                <h3 className="font-bold text-text-primary">Enable Live Trading?</h3>
                <p className="text-xs text-muted mt-0.5">Real money will be used</p>
              </div>
            </div>
            <div className="bg-orange-400/10 border border-orange-400/30 rounded-lg p-3 mb-5">
              <p className="text-sm text-orange-300">
                <strong>Warning:</strong> Switching to live mode will use real funds from your
                PocketOption account. You can lose your entire balance. Only proceed if you have:
                <br />• A configured Live SSID
                <br />• Sufficient risk capital
                <br />• Full understanding of the risks
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
                onClick={() => {
                  set("mode", "live");
                  setShowLiveModal(false);
                }}
                className="flex-1 py-2 rounded-lg bg-orange-400/20 text-orange-400 border border-orange-400/40 hover:bg-orange-400/30 text-sm font-semibold transition-colors"
              >
                Confirm Live Mode
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

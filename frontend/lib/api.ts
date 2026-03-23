const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// ─────────────────────────── Types ───────────────────────────────────
export interface IndicatorScores {
  RSI: number;
  MACD: number;
  Bollinger: number;
  EMA: number;
  Volume: number;
  Candlestick: number;
  rsi_value?: number;
  macd_value?: number;
  macd_signal?: number;
  macd_histogram?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  ema9?: number;
  ema21?: number;
}

export interface Asset {
  asset: string;
  display_name: string;
  flag: string;
  confidence: number;
  direction: "CALL" | "PUT";
  expiry: "1min" | "5min" | "15min";
  top_indicators: string[];
  indicators: IndicatorScores;
  price: number;
  price_change_pct: number;
  error?: string;
}

export interface Trade {
  id: number;
  asset: string;
  direction: "CALL" | "PUT";
  amount: number;
  entry_time: string;
  expiry_seconds: number;
  result: "WIN" | "LOSS" | "PENDING";
  pnl: number;
  mode: "demo" | "live" | "backtest";
  order_id?: string;
  entry_price?: number;
  confidence?: number;
  created_at?: string;
}

export interface Stats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  daily_pnl: number;
  best_trade: number;
  worst_trade: number;
  active_trades: number;
}

export interface BotStatus {
  running: boolean;
  mode: "demo" | "live";
  active_trades: number;
  auto_trade: boolean;
}

export interface Settings {
  mode?: string;
  trade_size?: string;
  confidence_threshold?: string;
  daily_loss_limit?: string;
  max_concurrent_trades?: string;
  min_trade_interval?: string;
  auto_trade?: string;
  refresh_interval?: string;
  enabled_assets?: string;
  ssid_demo?: string;
  ssid_live?: string;
  bot_running?: string;
  [key: string]: string | undefined;
}

export interface BacktestResult {
  asset: string;
  start_date: string;
  end_date: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  max_drawdown: number;
  trades: Trade[];
  pnl_curve: number[];
}

export type WSMessage =
  | { type: "price_update"; data: { asset: string; price: number; price_change_pct: number } }
  | { type: "confidence_update"; data: Asset }
  | { type: "trade_opened"; data: Trade }
  | { type: "trade_closed"; data: Trade }
  | { type: "bot_status"; data: Partial<BotStatus> & { settings_updated?: boolean } }
  | { type: "daily_limit_hit"; data: { current_loss: number; limit: number } }
  | { type: "pong" };

// ─────────────────────────── Fetch Helper ────────────────────────────
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ─────────────────────────── API Functions ───────────────────────────
export async function getAssets(): Promise<{ assets: Asset[]; cached_at: string }> {
  return apiFetch("/api/assets");
}

export async function getAsset(symbol: string): Promise<Asset> {
  return apiFetch(`/api/asset/${symbol}`);
}

export interface TradeFilters {
  limit?: number;
  asset?: string;
  mode?: string;
  result?: string;
}

export async function getTrades(filters?: TradeFilters): Promise<{ trades: Trade[] }> {
  const params = new URLSearchParams();
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.asset) params.set("asset", filters.asset);
  if (filters?.mode) params.set("mode", filters.mode);
  if (filters?.result) params.set("result", filters.result);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch(`/api/trades${qs}`);
}

export async function getStats(): Promise<Stats> {
  return apiFetch("/api/stats");
}

export async function getSettings(): Promise<Settings> {
  return apiFetch("/api/settings");
}

export async function updateSettings(settings: Settings): Promise<Settings> {
  return apiFetch("/api/settings", {
    method: "POST",
    body: JSON.stringify({ settings }),
  });
}

export async function placeTrade(
  asset: string,
  direction: "CALL" | "PUT",
  amount: number
): Promise<Trade> {
  return apiFetch("/api/trade", {
    method: "POST",
    body: JSON.stringify({ asset, direction, amount }),
  });
}

export async function startBot(): Promise<{ status: string; running: boolean }> {
  return apiFetch("/api/bot/start", { method: "POST" });
}

export async function stopBot(): Promise<{ status: string; running: boolean }> {
  return apiFetch("/api/bot/stop", { method: "POST" });
}

export async function getBotStatus(): Promise<BotStatus> {
  return apiFetch("/api/bot/status");
}

export async function runBacktest(
  asset: string,
  startDate: string,
  endDate: string
): Promise<BacktestResult> {
  const params = new URLSearchParams({ asset, start_date: startDate, end_date: endDate });
  return apiFetch(`/api/backtest?${params.toString()}`);
}

// ─────────────────────────── WebSocket ───────────────────────────────
export function createWebSocket(
  onMessage: (msg: WSMessage) => void,
  onOpen?: () => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws`);

  ws.onopen = () => {
    onOpen?.();
    // Send ping every 20 seconds to keep alive
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      } else {
        clearInterval(interval);
      }
    }, 20000);
  };

  ws.onmessage = (event) => {
    try {
      const msg: WSMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      // ignore non-JSON
    }
  };

  ws.onclose = () => {
    onClose?.();
  };

  return ws;
}

export function createReconnectingWebSocket(
  onMessage: (msg: WSMessage) => void,
  onStatusChange?: (connected: boolean) => void
): { disconnect: () => void } {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  function connect() {
    if (stopped) return;
    ws = createWebSocket(
      onMessage,
      () => onStatusChange?.(true),
      () => {
        onStatusChange?.(false);
        if (!stopped) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      }
    );
  }

  connect();

  return {
    disconnect: () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    },
  };
}

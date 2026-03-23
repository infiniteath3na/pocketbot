# PocketBot — Automated Binary Options Trading

PocketBot is a full-stack automated trading application for PocketOption. It uses technical indicators (RSI, MACD, Bollinger Bands, EMA crossover, Volume, Candlestick patterns) to generate a 0–100 confidence score for 16 assets and automatically executes trades when signal strength exceeds your configured threshold.

---

## **RISK WARNING**

> **Trading binary options involves significant risk of capital loss. This software is provided for educational purposes only. Never trade with money you cannot afford to lose. Past performance of any strategy does not guarantee future results. The authors assume no liability for financial losses incurred through use of this software.**

---

## Features

- Real-time confidence scoring across 16 assets (forex, crypto, commodities)
- Weighted indicator engine: RSI · MACD · Bollinger Bands · EMA crossover · Volume · Candlestick patterns
- Auto-trading bot with configurable thresholds, cooldowns, and daily loss limits
- Demo and Live mode support via PocketOption WebSocket API
- Historical backtester using Yahoo Finance data
- Dark-themed dashboard with live WebSocket updates
- Trade history with CSV export and P&L charting

---

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later
- A PocketOption account (free demo available)

---

## Installation

### 1. Clone / navigate to the project

```bash
cd /path/to/pocketbot
```

### 2. Backend setup

```bash
cd backend
pip install -r requirements.txt
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

### 4. Environment configuration

```bash
cp .env.example .env
```

Edit `.env` and fill in your PocketOption SSIDs (see below for how to obtain them).

### 5. Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive Swagger UI.

### 6. Run the frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## How to get your PocketOption SSID

Your SSID (Session ID) is the authentication token used to connect PocketBot to your PocketOption account via WebSocket.

**Method 1 — Network tab:**
1. Log in to [PocketOption](https://pocketoption.com) in Chrome
2. Press `F12` to open DevTools
3. Go to the **Network** tab
4. Filter by **WS** (WebSocket)
5. Refresh the page and look for a connection to `api.po.market`
6. Click the connection and view the **Messages** tab
7. Find the message that looks like `42["auth",{"session":"YOUR_SSID_HERE",...}]`
8. Copy the session value

**Method 2 — Cookies:**
1. Log in to PocketOption in Chrome
2. Press `F12` → **Application** tab → **Cookies** → `https://pocketoption.com`
3. Find the cookie named `user_auth` or `session`
4. Copy its value

Paste the value into the **Settings** page of PocketBot, or directly into your `.env` file:
- Demo account SSID → `POCKET_OPTION_SSID_DEMO`
- Live account SSID → `POCKET_OPTION_SSID_LIVE`

---

## Demo Mode Walkthrough

1. Launch both backend and frontend (steps 5–6 above)
2. Open `http://localhost:3000`
3. The dashboard loads confidence scores for all 16 assets using Yahoo Finance data
4. Go to **Settings** → paste your Demo SSID → click **Test Connection**
5. Enable the assets you want to trade
6. Set your **Confidence Threshold** (default 70%) and **Trade Size** (default $10)
7. Enable **Auto-Trade** and click **Start Bot** on the dashboard
8. The bot scans all enabled assets on your configured refresh interval and places demo trades automatically
9. View results in the **Trades** page and analyse historical performance in the **Backtest** page

---

## Project Structure

```
pocketbot/
├── backend/
│   ├── main.py              # FastAPI app — all REST + WebSocket endpoints
│   ├── indicators.py        # Confidence index engine (RSI, MACD, BB, EMA, Volume, Candle)
│   ├── pocket_api.py        # PocketOption WebSocket client
│   ├── trade_manager.py     # Trade execution, risk management, auto-trading loop
│   ├── models.py            # SQLAlchemy models (Trade, Settings, PriceSnapshot)
│   ├── database.py          # SQLite setup and default settings initialization
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx       # Root layout with sidebar navigation
│   │   ├── page.tsx         # Dashboard
│   │   ├── scanner/page.tsx # Full asset scanner table
│   │   ├── trades/page.tsx  # Trade history with filters and P&L chart
│   │   ├── settings/page.tsx
│   │   └── backtest/page.tsx
│   ├── components/
│   │   ├── ConfidenceGauge.tsx  # SVG semi-circular gauge
│   │   ├── AssetCard.tsx        # Per-asset card with mini gauge
│   │   ├── TradeLog.tsx         # Reusable trade table
│   │   ├── PriceChart.tsx       # TradingView Lightweight Charts integration
│   │   └── BotControls.tsx      # Start/Stop + mode switcher
│   ├── lib/
│   │   └── api.ts           # Typed API client + WebSocket helpers
│   └── ...config files
├── .env.example
└── README.md
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/assets` | All assets with confidence scores (30s cache) |
| GET | `/api/asset/{symbol}` | Detailed analysis for one asset |
| GET | `/api/trades` | Trade history with optional filters |
| GET | `/api/stats` | Daily statistics |
| POST | `/api/trade` | Manually trigger a trade |
| GET | `/api/settings` | Get all settings |
| POST | `/api/settings` | Update settings |
| POST | `/api/bot/start` | Start auto-trading |
| POST | `/api/bot/stop` | Stop auto-trading |
| GET | `/api/bot/status` | Bot running state |
| GET | `/api/backtest` | Run historical backtest |
| WS | `/ws` | Real-time updates |

---

## Configuration Reference

All settings are stored in the SQLite database and can be changed via the Settings UI or `POST /api/settings`.

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `demo` | Trading mode: `demo` or `live` |
| `trade_size` | `10` | Trade amount in USD |
| `confidence_threshold` | `70` | Minimum confidence score (0–100) to trigger a trade |
| `daily_loss_limit` | `100` | Stop trading if daily losses exceed this amount |
| `max_concurrent_trades` | `3` | Maximum simultaneous open trades |
| `min_trade_interval` | `5` | Cooldown in minutes between trades on the same asset |
| `auto_trade` | `false` | Enable automatic trade execution |
| `refresh_interval` | `30` | Asset scan interval in seconds |
| `enabled_assets` | 7 assets | Comma-separated list of enabled asset symbols |

---

## Supported Assets

| Symbol | Description |
|--------|-------------|
| EURUSD | Euro / US Dollar |
| GBPUSD | British Pound / US Dollar |
| USDJPY | US Dollar / Japanese Yen |
| AUDUSD | Australian Dollar / US Dollar |
| USDCAD | US Dollar / Canadian Dollar |
| EURGBP | Euro / British Pound |
| NZDUSD | New Zealand Dollar / US Dollar |
| USDCHF | US Dollar / Swiss Franc |
| EURJPY | Euro / Japanese Yen |
| XAUUSD | Gold / US Dollar |
| XAGUSD | Silver / US Dollar |
| BTCUSD | Bitcoin / US Dollar |
| ETHUSD | Ethereum / US Dollar |
| LTCUSD | Litecoin / US Dollar |
| SOLUSD | Solana / US Dollar |
| XRPUSD | XRP / US Dollar |

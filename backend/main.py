import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import create_tables, get_db, init_default_settings, SessionLocal
from indicators import (
    ASSET_SYMBOLS,
    ASSET_DISPLAY,
    ASSET_FLAGS,
    compute_all_assets,
    compute_confidence,
    confidence_result_to_dict,
)
from models import Trade, Settings, PriceSnapshot
from trade_manager import TradeManager

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

# ────────────────────────────── App Init ──────────────────────────────
app = FastAPI(title="PocketBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trade_manager = TradeManager()

# In-memory cache
_asset_cache: Dict[str, dict] = {}
_cache_timestamp: float = 0
CACHE_TTL = 30  # seconds

# Connected WebSocket clients
_ws_clients: List[WebSocket] = []


# ─────────────────────────── Startup / Shutdown ──────────────────────────
@app.on_event("startup")
async def startup():
    create_tables()
    db = SessionLocal()
    try:
        init_default_settings(db)
    finally:
        db.close()
    logger.info("PocketBot backend started")


@app.on_event("shutdown")
async def shutdown():
    await trade_manager.stop_auto_trading()
    if trade_manager.pocket_client:
        await trade_manager.pocket_client.disconnect()


# ─────────────────────────── WebSocket Broadcast ─────────────────────────
async def broadcast(message: dict):
    if not _ws_clients:
        return
    dead = []
    for client in _ws_clients:
        try:
            await client.send_json(message)
        except Exception:
            dead.append(client)
    for c in dead:
        _ws_clients.remove(c)


# ─────────────────────────── Pydantic Schemas ─────────────────────────────
class ManualTradeRequest(BaseModel):
    asset: str
    direction: str  # "CALL" or "PUT"
    amount: float = 10.0


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, str]


# ─────────────────────────── Helper Functions ─────────────────────────────
async def _get_assets_with_cache() -> List[dict]:
    global _asset_cache, _cache_timestamp
    now = time.time()
    if now - _cache_timestamp < CACHE_TTL and _asset_cache:
        return list(_asset_cache.values())

    all_assets = list(ASSET_SYMBOLS.keys())
    results = await compute_all_assets(all_assets)

    _asset_cache = {asset: confidence_result_to_dict(r) for asset, r in results.items()}
    _cache_timestamp = now
    return list(_asset_cache.values())


def _get_settings_dict(db: Session) -> dict:
    settings = db.query(Settings).all()
    return {s.key: s.value for s in settings}


# ─────────────────────────── Endpoints ───────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "bot_running": trade_manager.is_running,
    }


@app.get("/api/assets")
async def get_assets():
    """Return all assets with current confidence scores and prices."""
    assets = await _get_assets_with_cache()
    return {"assets": assets, "cached_at": datetime.utcfromtimestamp(_cache_timestamp).isoformat()}


@app.get("/api/asset/{symbol}")
async def get_asset(symbol: str):
    """Detailed analysis for a single asset."""
    symbol = symbol.upper()
    if symbol not in ASSET_SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Asset '{symbol}' not found")
    result = await compute_confidence(symbol)
    return confidence_result_to_dict(result)


@app.get("/api/trades")
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    asset: Optional[str] = None,
    mode: Optional[str] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List trades with optional filters."""
    query = db.query(Trade)
    if asset:
        query = query.filter(Trade.asset == asset.upper())
    if mode:
        query = query.filter(Trade.mode == mode.lower())
    if result:
        query = query.filter(Trade.result == result.upper())
    trades = query.order_by(Trade.created_at.desc()).limit(limit).all()
    return {"trades": [t.to_dict() for t in trades]}


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Daily and overall trading statistics."""
    stats = trade_manager.get_stats()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades = db.query(Trade).filter(Trade.created_at >= today_start).all()
    today_closed = [t for t in today_trades if t.result != "PENDING"]

    pnl_values = [t.pnl for t in today_closed if t.pnl is not None]
    best_trade = max(pnl_values, default=0.0)
    worst_trade = min(pnl_values, default=0.0)

    return {
        **stats,
        "total_trades": stats["today_trades"],
        "wins": stats["today_wins"],
        "losses": stats["today_trades"] - stats["today_wins"],
        "win_rate": round(stats["today_wins"] / max(len(today_closed), 1) * 100, 2),
        "total_pnl": stats["daily_pnl"],
        "daily_pnl": stats["daily_pnl"],
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "active_trades": trade_manager.active_trade_count,
    }


@app.post("/api/trade")
async def manual_trade(request: ManualTradeRequest, db: Session = Depends(get_db)):
    """Manually trigger a trade."""
    symbol = request.asset.upper()
    if symbol not in ASSET_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown asset: {symbol}")

    direction = request.direction.upper()
    if direction not in ("CALL", "PUT"):
        raise HTTPException(status_code=400, detail="direction must be CALL or PUT")

    settings = _get_settings_dict(db)

    # Get current confidence for this asset
    result = await compute_confidence(symbol)
    result.direction = direction  # Override with manual direction

    trade = await trade_manager.execute_trade(symbol, result, settings)
    if not trade:
        raise HTTPException(status_code=500, detail="Trade execution failed")

    await broadcast({"type": "trade_opened", "data": trade.to_dict()})
    return trade.to_dict()


@app.get("/api/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Get all settings."""
    return _get_settings_dict(db)


@app.post("/api/settings")
async def update_settings(request: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Update settings."""
    for key, value in request.settings.items():
        existing = db.query(Settings).filter(Settings.key == key).first()
        if existing:
            existing.value = value
        else:
            db.add(Settings(key=key, value=value))
    db.commit()
    await broadcast({"type": "bot_status", "data": {"settings_updated": True}})
    return _get_settings_dict(db)


@app.post("/api/bot/start")
async def start_bot(db: Session = Depends(get_db)):
    """Start the auto-trading bot."""
    if trade_manager.is_running:
        return {"status": "already_running", "running": True}

    await trade_manager.start_auto_trading(broadcast_callback=broadcast)
    await broadcast({"type": "bot_status", "data": {"running": True}})
    return {"status": "started", "running": True}


@app.post("/api/bot/stop")
async def stop_bot():
    """Stop the auto-trading bot."""
    await trade_manager.stop_auto_trading()
    await broadcast({"type": "bot_status", "data": {"running": False}})
    return {"status": "stopped", "running": False}


@app.get("/api/bot/status")
async def bot_status(db: Session = Depends(get_db)):
    """Get bot running state."""
    settings = _get_settings_dict(db)
    return {
        "running": trade_manager.is_running,
        "mode": settings.get("mode", "demo"),
        "active_trades": trade_manager.active_trade_count,
        "auto_trade": settings.get("auto_trade", "false") == "true",
    }


@app.get("/api/backtest")
async def backtest(
    asset: str = Query(..., description="Asset symbol e.g. EURUSD"),
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Run a historical backtest using yfinance data + indicator logic."""
    symbol = asset.upper()
    if symbol not in ASSET_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown asset: {symbol}")

    yf_symbol = ASSET_SYMBOLS[symbol]

    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(
                yf_symbol,
                start=start_date,
                end=end_date,
                interval="1h",
                progress=False,
                auto_adjust=True,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch error: {e}")

    if df is None or len(df) < 30:
        raise HTTPException(status_code=400, detail="Insufficient historical data for backtest")

    if isinstance(df.columns, pd.MultiIndex if False else type(df.columns)):
        pass
    try:
        import pandas as pd
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except Exception:
        pass

    simulated_trades = []
    total_pnl = 0.0
    wins = 0
    losses = 0
    running_pnl = []
    max_drawdown = 0.0
    peak_pnl = 0.0

    # Step through each bar with enough history
    import pandas as pd
    import numpy as np

    from indicators import (
        _compute_rsi, _rsi_score, _compute_macd, _macd_score,
        _compute_bollinger, _bollinger_score, _compute_ema, _ema_score,
        _volume_score, _candlestick_score, _safe_float
    )

    closes = df["Close"]
    opens = df["Open"]
    highs = df["High"]
    lows = df["Low"]
    volumes = df["Volume"] if "Volume" in df.columns else pd.Series([1] * len(df), index=df.index)

    weights = {"RSI": 0.20, "MACD": 0.25, "Bollinger": 0.20, "EMA": 0.20, "Volume": 0.10, "Candlestick": 0.05}

    for i in range(30, len(df) - 1):
        window_closes = closes.iloc[:i]
        window_vols = volumes.iloc[:i]
        window_df = df.iloc[:i]

        rsi = _compute_rsi(window_closes)
        rsi_score, rsi_dir = _rsi_score(rsi)
        macd, sig, hist = _compute_macd(window_closes)
        macd_score, macd_dir = _macd_score(macd, sig, hist)
        bb_u, bb_m, bb_l = _compute_bollinger(window_closes)
        current_price = _safe_float(closes.iloc[i])
        bb_score, bb_dir = _bollinger_score(current_price, bb_u, bb_m, bb_l)
        ema9 = _compute_ema(window_closes, 9)
        ema21 = _compute_ema(window_closes, 21)
        ema_score, ema_dir = _ema_score(ema9, ema21)
        vol_score, vol_dir = _volume_score(window_vols)
        candle_score, candle_dir = _candlestick_score(window_df)

        scores = {
            "RSI": rsi_score, "MACD": macd_score, "Bollinger": bb_score,
            "EMA": ema_score, "Volume": vol_score, "Candlestick": candle_score,
        }
        directions = {
            "RSI": rsi_dir, "MACD": macd_dir, "Bollinger": bb_dir,
            "EMA": ema_dir, "Volume": vol_dir, "Candlestick": candle_dir,
        }

        bullish_w = sum(weights[n] for n, d in directions.items() if d == "CALL")
        bearish_w = sum(weights[n] for n, d in directions.items() if d == "PUT")
        overall_dir = "CALL" if bullish_w >= bearish_w else "PUT"

        directional = {}
        for name, score in scores.items():
            d = directions[name]
            if d == "CALL":
                directional[name] = score
            elif d == "PUT":
                directional[name] = 100.0 - score
            else:
                directional[name] = 50.0

        confidence = sum(directional[n] * weights[n] for n in weights)
        confidence = max(0.0, min(100.0, confidence))

        # Only trade when confidence >= 65
        if confidence < 65:
            continue

        # Determine result from next candle
        next_close = _safe_float(closes.iloc[i + 1])
        if overall_dir == "CALL":
            win = next_close > current_price
        else:
            win = next_close < current_price

        trade_amount = 10.0
        payout = trade_amount * 0.85 if win else -trade_amount
        total_pnl += payout

        if win:
            wins += 1
            result_str = "WIN"
        else:
            losses += 1
            result_str = "LOSS"

        running_pnl.append(total_pnl)
        if total_pnl > peak_pnl:
            peak_pnl = total_pnl
        drawdown = peak_pnl - total_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        entry_time = df.index[i]
        simulated_trades.append({
            "id": len(simulated_trades) + 1,
            "asset": symbol,
            "direction": overall_dir,
            "amount": trade_amount,
            "entry_time": entry_time.isoformat() if hasattr(entry_time, "isoformat") else str(entry_time),
            "expiry_seconds": 3600,
            "result": result_str,
            "pnl": round(payout, 2),
            "entry_price": round(current_price, 6),
            "confidence": round(confidence, 2),
            "mode": "backtest",
        })

    total_count = wins + losses
    win_rate = (wins / total_count * 100) if total_count > 0 else 0.0

    return {
        "asset": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "total_trades": total_count,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "trades": simulated_trades,
        "pnl_curve": running_pnl,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_ws_clients)}")

    try:
        # Send initial status
        await websocket.send_json({
            "type": "bot_status",
            "data": {
                "running": trade_manager.is_running,
                "active_trades": trade_manager.active_trade_count,
            },
        })

        while True:
            # Keep connection alive by receiving any messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)

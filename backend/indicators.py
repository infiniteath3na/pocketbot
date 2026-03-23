import asyncio
import csv
import io
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from xml.etree import ElementTree as ET

import aiohttp
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Asset mappings (unchanged)
# ---------------------------------------------------------------------------

ASSET_SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "EURGBP": "EURGBP=X",
    "NZDUSD": "NZDUSD=X",
    "USDCHF": "USDCHF=X",
    "EURJPY": "EURJPY=X",
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "LTCUSD": "LTC-USD",
    "SOLUSD": "SOL-USD",
    "XRPUSD": "XRP-USD",
}

ASSET_DISPLAY = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "EURGBP": "EUR/GBP",
    "NZDUSD": "NZD/USD",
    "USDCHF": "USD/CHF",
    "EURJPY": "EUR/JPY",
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "LTCUSD": "LTC/USD",
    "SOLUSD": "SOL/USD",
    "XRPUSD": "XRP/USD",
}

ASSET_FLAGS = {
    "EURUSD": "🇪🇺🇺🇸",
    "GBPUSD": "🇬🇧🇺🇸",
    "USDJPY": "🇺🇸🇯🇵",
    "AUDUSD": "🇦🇺🇺🇸",
    "USDCAD": "🇺🇸🇨🇦",
    "EURGBP": "🇪🇺🇬🇧",
    "NZDUSD": "🇳🇿🇺🇸",
    "USDCHF": "🇺🇸🇨🇭",
    "EURJPY": "🇪🇺🇯🇵",
    "XAUUSD": "🥇",
    "XAGUSD": "🥈",
    "BTCUSD": "₿",
    "ETHUSD": "Ξ",
    "LTCUSD": "Ł",
    "SOLUSD": "◎",
    "XRPUSD": "✕",
}

# ---------------------------------------------------------------------------
# Asset type classification
# ---------------------------------------------------------------------------

CRYPTO_ASSETS = {"BTCUSD", "ETHUSD", "LTCUSD", "SOLUSD", "XRPUSD"}
METALS_ASSETS = {"XAUUSD", "XAGUSD"}
FOREX_ASSETS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP", "NZDUSD", "USDCHF", "EURJPY"}

# DXY inverse: rising DXY hurts these assets
DXY_INVERSE_ASSETS = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "XAUUSD", "XAGUSD"}
# DXY direct: rising DXY helps these assets
DXY_DIRECT_ASSETS = {"USDJPY", "USDCAD", "USDCHF"}

# Binance perpetual futures symbols for crypto
CRYPTO_BINANCE_SYMBOLS = {
    "BTCUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT",
    "SOLUSD": "SOLUSDT",
    "XRPUSD": "XRPUSDT",
    "LTCUSD": "LTCUSDT",
}

# OKX perpetual swap symbols
CRYPTO_OKX_SYMBOLS = {
    "BTCUSD": "BTC-USD-SWAP",
    "ETHUSD": "ETH-USD-SWAP",
    "SOLUSD": "SOL-USD-SWAP",
    "XRPUSD": "XRP-USD-SWAP",
    "LTCUSD": "LTC-USD-SWAP",
}

# Bybit linear perpetual symbols
CRYPTO_BYBIT_SYMBOLS = {
    "BTCUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT",
    "SOLUSD": "SOLUSDT",
    "XRPUSD": "XRPUSDT",
    "LTCUSD": "LTCUSDT",
}

# COT report market name keywords (CFTC disaggregated)
COT_MARKET_KEYWORDS = {
    "XAUUSD": "GOLD",
    "EURUSD": "EURO FX",
    "GBPUSD": "BRITISH POUND",
    "USDJPY": "JAPANESE YEN",
    "AUDUSD": "AUSTRALIAN DOLLAR",
    "USDCAD": "CANADIAN DOLLAR",
    "USDCHF": "SWISS FRANC",
    "NZDUSD": "NEW ZEALAND DOLLAR",
}

# Yahoo Finance RSS tickers
NEWS_RSS_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "LTCUSD": "LTC-USD",
    "SOLUSD": "SOL-USD",
    "XRPUSD": "XRP-USD",
}

_BULLISH_KEYWORDS = {"surge", "rally", "breakout", "bullish", "gain", "rise", "soar", "strong", "buy"}
_BEARISH_KEYWORDS = {"crash", "drop", "fall", "bearish", "decline", "plunge", "weak", "sell", "fear"}

# ---------------------------------------------------------------------------
# Weight tables — raw values normalized to sum to 1.0
# ---------------------------------------------------------------------------

def _normalize_weights(raw: Dict[str, float]) -> Dict[str, float]:
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


FOREX_WEIGHTS = _normalize_weights({
    "RSI": 13, "MACD": 13, "Bollinger": 11, "EMA": 11, "Volume": 6, "Candlestick": 4,
    "DXY": 8, "COT": 8, "News": 8,
})

METALS_WEIGHTS = _normalize_weights({
    "RSI": 12, "MACD": 12, "Bollinger": 10, "EMA": 10, "Volume": 5, "Candlestick": 4,
    "DXY": 10, "COT": 8, "News": 8, "VIX": 7,
})

CRYPTO_WEIGHTS = _normalize_weights({
    "RSI": 11, "MACD": 11, "Bollinger": 9, "EMA": 9, "Volume": 5, "Candlestick": 4,
    "FearGreed": 10, "FundingRate": 8, "News": 8, "DXY": 4, "VIX": 5,
})

# ---------------------------------------------------------------------------
# In-memory cache with TTL
# ---------------------------------------------------------------------------

_cache: Dict[str, Tuple[float, Any]] = {}

# Module-level econ calendar cache — shared across all assets to avoid per-asset 429s
_econ_cache: Dict[str, Any] = {"data": None, "ts": 0.0}


def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[0]:
        return entry[1]
    return None


def _cache_set(key: str, value: Any, ttl: int) -> None:
    _cache[key] = (time.monotonic() + ttl, value)


# ---------------------------------------------------------------------------
# ConfidenceResult dataclass — new fields added with defaults
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceResult:
    confidence: float
    direction: str  # "CALL" or "PUT"
    expiry: str  # "1min", "5min", "15min"
    top_indicators: List[str]
    indicators: Dict[str, float]
    price: float
    asset: str
    display_name: str
    flag: str
    price_change_pct: float = 0.0
    error: Optional[str] = None
    # New smart money / macro / sentiment fields
    smart_money_score: float = 50.0
    macro_score: float = 50.0
    sentiment_score: float = 50.0
    session_multiplier: float = 1.0
    econ_gate_active: bool = False
    econ_gate_reason: Optional[str] = None
    liquidity_sweep_detected: bool = False


# ---------------------------------------------------------------------------
# Helpers (unchanged)
# ---------------------------------------------------------------------------

def _safe_float(val, default=50.0) -> float:
    try:
        v = float(val)
        if np.isnan(v) or np.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Technical indicators (all unchanged)
# ---------------------------------------------------------------------------

def _compute_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = float(gain.rolling(window=period).mean().iloc[-1])
    avg_loss = float(loss.rolling(window=period).mean().iloc[-1])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return _safe_float(rsi)


def _rsi_score(rsi: float) -> Tuple[float, str]:
    """Returns (score 0-100, direction hint)"""
    if rsi < 30:
        score = 80 + (30 - rsi) / 30 * 20  # 80-100
        return min(100.0, score), "CALL"
    elif rsi > 70:
        score = 80 + (rsi - 70) / 30 * 20  # 80-100 bearish
        return min(100.0, score), "PUT"
    else:
        return 50.0, "NEUTRAL"


def _compute_macd(closes: pd.Series) -> Tuple[float, float, float]:
    """Returns (macd_line, signal_line, histogram)"""
    if len(closes) < 26:
        return 0.0, 0.0, 0.0
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        _safe_float(macd_line.iloc[-1], 0.0),
        _safe_float(signal_line.iloc[-1], 0.0),
        _safe_float(histogram.iloc[-1], 0.0),
    )


def _macd_score(macd: float, signal: float, histogram: float) -> Tuple[float, str]:
    """Returns (score 0-100, direction)"""
    if macd > signal and histogram > 0:
        strength = min(abs(histogram) / (abs(macd) + 1e-10), 1.0)
        score = 60 + strength * 40
        return _safe_float(score), "CALL"
    elif macd < signal and histogram < 0:
        strength = min(abs(histogram) / (abs(macd) + 1e-10), 1.0)
        score = 60 + strength * 40
        return _safe_float(score), "PUT"
    else:
        return 50.0, "NEUTRAL"


def _compute_bollinger(closes: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
    """Returns (upper, middle, lower)"""
    if len(closes) < period:
        return closes.iloc[-1], closes.iloc[-1], closes.iloc[-1]
    sma = closes.rolling(window=period).mean().iloc[-1]
    std = closes.rolling(window=period).std().iloc[-1]
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return _safe_float(upper, closes.iloc[-1]), _safe_float(sma, closes.iloc[-1]), _safe_float(lower, closes.iloc[-1])


def _bollinger_score(price: float, upper: float, middle: float, lower: float) -> Tuple[float, str]:
    """Returns (score 0-100, direction)"""
    band_width = upper - lower
    if band_width == 0:
        return 50.0, "NEUTRAL"
    position = (price - lower) / band_width  # 0 = at lower, 1 = at upper
    if position <= 0.1:
        score = 80 + (0.1 - position) / 0.1 * 20
        return min(100.0, _safe_float(score)), "CALL"
    elif position >= 0.9:
        score = 80 + (position - 0.9) / 0.1 * 20
        return min(100.0, _safe_float(score)), "PUT"
    else:
        return 50.0, "NEUTRAL"


def _compute_ema(closes: pd.Series, period: int) -> float:
    if len(closes) < period:
        return _safe_float(closes.iloc[-1])
    return _safe_float(closes.ewm(span=period, adjust=False).mean().iloc[-1])


def _ema_score(ema9: float, ema21: float) -> Tuple[float, str]:
    """Returns (score 0-100, direction)"""
    if ema9 > ema21:
        diff_pct = (ema9 - ema21) / ema21 * 100
        score = 60 + min(diff_pct * 100, 40)
        return _safe_float(score), "CALL"
    elif ema9 < ema21:
        diff_pct = (ema21 - ema9) / ema21 * 100
        score = 60 + min(diff_pct * 100, 40)
        return _safe_float(score), "PUT"
    else:
        return 50.0, "NEUTRAL"


def _volume_score(volumes: pd.Series) -> Tuple[float, str]:
    """Returns (score 0-100, confirmation)"""
    if len(volumes) < 20:
        return 50.0, "NEUTRAL"
    avg_vol = volumes.rolling(window=20).mean().iloc[-1]
    current_vol = volumes.iloc[-1]
    if avg_vol == 0:
        return 50.0, "NEUTRAL"
    ratio = current_vol / avg_vol
    if ratio >= 1.0:
        score = 60 + min((ratio - 1.0) * 20, 20)
        return _safe_float(score), "CONFIRM"
    else:
        score = 40 + ratio * 20
        return _safe_float(score), "WEAK"


def _candlestick_score(df: pd.DataFrame) -> Tuple[float, str]:
    """Detect candlestick patterns from last 3 candles. Returns (score 0-100, direction)."""
    if len(df) < 3:
        return 50.0, "NEUTRAL"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = _safe_float(last["Open"])
    close_ = _safe_float(last["Close"])
    high_ = _safe_float(last["High"])
    low_ = _safe_float(last["Low"])
    body = abs(close_ - open_)
    full_range = high_ - low_
    if full_range == 0:
        return 50.0, "NEUTRAL"

    upper_shadow = high_ - max(open_, close_)
    lower_shadow = min(open_, close_) - low_

    is_doji = body < full_range * 0.1

    is_hammer = (
        lower_shadow > body * 2
        and upper_shadow < body * 0.5
        and close_ > open_
    )

    is_shooting_star = (
        upper_shadow > body * 2
        and lower_shadow < body * 0.5
        and close_ < open_
    )

    prev_open = _safe_float(prev["Open"])
    prev_close = _safe_float(prev["Close"])
    is_bullish_engulfing = (
        prev_close < prev_open
        and close_ > open_
        and open_ < prev_close
        and close_ > prev_open
    )

    is_bearish_engulfing = (
        prev_close > prev_open
        and close_ < open_
        and open_ > prev_close
        and close_ < prev_open
    )

    if is_bullish_engulfing:
        return 85.0, "CALL"
    elif is_bearish_engulfing:
        return 85.0, "PUT"
    elif is_hammer:
        return 75.0, "CALL"
    elif is_shooting_star:
        return 75.0, "PUT"
    elif is_doji:
        return 50.0, "NEUTRAL"
    elif close_ > open_:
        return 60.0, "CALL"
    else:
        return 40.0, "PUT"


def _determine_expiry(confidence: float, volatility: str = "normal") -> str:
    """
    Map confidence score to optimal expiry duration.
    
    Full duration range: 5s, 10s, 15s, 30s, 1min, 2min, 3min, 5min, 10min, 15min
    
    Logic:
    - Very high confidence (>=90): short duration (5s-30s) — signal is strong, get in/out fast
    - High confidence (>=80): medium-short (1min-2min)
    - Good confidence (>=70): medium (3min-5min)
    - Moderate (>=60): longer (10min)
    - Lower confidence: max duration (15min) — wait for bigger move
    """
    if confidence >= 92:
        return "5s"
    elif confidence >= 88:
        return "10s"
    elif confidence >= 85:
        return "15s"
    elif confidence >= 82:
        return "30s"
    elif confidence >= 78:
        return "1min"
    elif confidence >= 74:
        return "2min"
    elif confidence >= 70:
        return "3min"
    elif confidence >= 65:
        return "5min"
    elif confidence >= 55:
        return "10min"
    else:
        return "15min"


# ---------------------------------------------------------------------------
# Session timing multiplier (sync — based on current UTC time)
# ---------------------------------------------------------------------------

def _get_session_multiplier() -> float:
    hour = datetime.now(timezone.utc).hour
    # London/NY overlap: 13:00–16:00 UTC
    if 13 <= hour < 16:
        return 1.25
    # London: 08:00–16:00 UTC
    if 8 <= hour < 16:
        return 1.15
    # New York: 13:00–21:00 UTC
    if 13 <= hour < 21:
        return 1.15
    # Asian: 00:00–08:00 UTC
    if 0 <= hour < 8:
        return 0.85
    return 1.0


# ---------------------------------------------------------------------------
# New external data fetchers — all async with TTL cache + neutral fallback
# ---------------------------------------------------------------------------

async def _fetch_fear_greed() -> float:
    """Fetch Alternative.me Fear & Greed Index. Returns raw 0-100 value."""
    cached = _cache_get("fear_greed")
    if cached is not None:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json(content_type=None)
        value = float(data["data"][0]["value"])
        _cache_set("fear_greed", value, 3600)  # 1 hour TTL
        return value
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return 50.0


def _fear_greed_score(fg_value: float) -> Tuple[float, str]:
    if fg_value < 25:
        return 75.0, "CALL"   # extreme fear → contrarian bullish
    elif fg_value > 75:
        return 75.0, "PUT"    # extreme greed → contrarian bearish
    else:
        return 50.0, "NEUTRAL"


async def _fetch_dxy_change() -> float:
    """Fetch DXY 5-day % change via yfinance. Returns percent change."""
    cached = _cache_get("dxy_change")
    if cached is not None:
        return cached
    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download("DX-Y.NYB", period="10d", interval="1d", progress=False, auto_adjust=True),
        )
        if df is None or len(df) < 2:
            raise ValueError("Insufficient DXY data")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        closes = df["Close"].dropna()
        if len(closes) < 2:
            raise ValueError("Not enough DXY closes")
        _last = _safe_float(closes.iloc[-1], default=0.0)
        _prev = _safe_float(closes.iloc[-min(5, len(closes) - 1)], default=0.0)
        change = ((_last - _prev) / _prev * 100) if _prev != 0 else 0.0
        _cache_set("dxy_change", change, 900)  # 15 min TTL
        return change
    except Exception as e:
        logger.warning(f"DXY fetch failed: {e}")
        return 0.0


def _dxy_score(dxy_change_pct: float, asset: str) -> Tuple[float, str]:
    if asset in DXY_INVERSE_ASSETS:
        if dxy_change_pct > 0.5:
            return 70.0, "PUT"
        elif dxy_change_pct < -0.5:
            return 70.0, "CALL"
        else:
            return 50.0, "NEUTRAL"
    elif asset in DXY_DIRECT_ASSETS:
        if dxy_change_pct > 0.5:
            return 70.0, "CALL"
        elif dxy_change_pct < -0.5:
            return 70.0, "PUT"
        else:
            return 50.0, "NEUTRAL"
    else:
        return 50.0, "NEUTRAL"


def _parse_cot_csv(text: str, keyword: str) -> float:
    """Parse CFTC disaggregated COT text and return directional score 0-100."""
    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return 50.0

        header = [h.strip().strip('"') for h in rows[0]]
        long_col = next((i for i, h in enumerate(header) if "NonComm_Positions_Long_All" in h), None)
        short_col = next((i for i, h in enumerate(header) if "NonComm_Positions_Short_All" in h), None)

        if long_col is None or short_col is None:
            return 50.0

        kw_upper = keyword.upper()
        for row in rows[1:]:
            if not row:
                continue
            market = row[0].strip().strip('"').upper()
            if kw_upper in market:
                try:
                    long_pos = float(row[long_col].strip().strip('"').replace(",", ""))
                    short_pos = float(row[short_col].strip().strip('"').replace(",", ""))
                    net = long_pos - short_pos
                    # Score via net position magnitude (thresholds are market-agnostic heuristics)
                    if net > 75_000:
                        return 75.0
                    elif net > 25_000:
                        return 62.0
                    elif net < -75_000:
                        return 25.0
                    elif net < -25_000:
                        return 38.0
                    else:
                        return 50.0
                except (ValueError, IndexError):
                    return 50.0
        return 50.0
    except Exception:
        return 50.0


async def _fetch_cot_score(asset: str) -> float:
    """Fetch CFTC COT large speculator net position score (0-100). Cached 7 days."""
    cache_key = f"cot_{asset}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    keyword = COT_MARKET_KEYWORDS.get(asset)
    if not keyword:
        return 50.0

    _COT_URLS = [
        "https://raw.githubusercontent.com/datasets/cot-reports/main/data/futures-and-options-combined.csv",
        "https://raw.githubusercontent.com/datasets/cot-reports/main/data/futures-only.csv",
        "https://www.cftc.gov/dea/newcot/f_disagg.txt",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PocketBot/1.0)"}
    last_err: Exception = ValueError("no URLs tried")
    async with aiohttp.ClientSession() as session:
        for url in _COT_URLS:
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        raise ValueError(f"HTTP {resp.status}")
                    text = await resp.text(encoding="latin-1")
                score = _parse_cot_csv(text, keyword)
                _cache_set(cache_key, score, 7 * 24 * 3600)
                return score
            except Exception as e:
                last_err = e
                logger.warning(f"COT URL {url} failed for {asset}: {e}")
    logger.warning(f"All COT sources failed for {asset}: {last_err} — returning neutral 50.0")
    _cache_set(cache_key, 50.0, 7 * 24 * 3600)
    return 50.0


def _cot_score_to_direction(score: float) -> Tuple[float, str]:
    """Convert COT 0-100 score to (strength, direction)."""
    if score > 60:
        return score, "CALL"
    elif score < 40:
        return 100.0 - score, "PUT"
    else:
        return 50.0, "NEUTRAL"


async def _fetch_funding_rate(asset: str) -> float:
    """Fetch Binance perpetuals funding rate. Returns raw rate (e.g. 0.0001)."""
    cache_key = f"funding_{asset}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if asset not in CRYPTO_OKX_SYMBOLS:
        return 0.0

    async with aiohttp.ClientSession() as session:
        # Try OKX first
        try:
            okx_sym = CRYPTO_OKX_SYMBOLS[asset]
            url = f"https://www.okx.com/api/v5/public/funding-rate?instId={okx_sym}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"OKX HTTP {resp.status}")
                data = await resp.json()
            rate = float(data["data"][0]["fundingRate"])
            _cache_set(cache_key, rate, 300)
            return rate
        except Exception as e:
            logger.warning(f"OKX funding rate failed for {asset}: {e}")

        # Try Bybit
        try:
            bybit_sym = CRYPTO_BYBIT_SYMBOLS[asset]
            url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={bybit_sym}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"Bybit HTTP {resp.status}")
                data = await resp.json()
            rate = float(data["result"]["list"][0]["fundingRate"])
            _cache_set(cache_key, rate, 300)
            return rate
        except Exception as e:
            logger.warning(f"Bybit funding rate failed for {asset}: {e}")

    logger.warning(f"All funding rate sources failed for {asset} — returning neutral 0.0")
    return 0.0


def _funding_rate_score(rate: float) -> Tuple[float, str]:
    if rate > 0.0005:   # >0.05% — overleveraged longs
        return 70.0, "PUT"
    elif rate < -0.0005:  # <-0.05% — overleveraged shorts
        return 70.0, "CALL"
    else:
        return 50.0, "NEUTRAL"


async def _fetch_oi_adjustment(asset: str, price_change_pct: float) -> float:
    """
    Fetch open interest history and return a confidence adjustment.
    +5.0 if rising price + rising OI (strong trend), -5.0 if rising price + falling OI (weak).
    """
    binance_sym = CRYPTO_BINANCE_SYMBOLS.get(asset)
    if not binance_sym:
        return 0.0

    try:
        url = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={binance_sym}&period=5m&limit=2"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return 0.0
                data = await resp.json()

        if len(data) < 2:
            return 0.0

        oi_current = float(data[-1]["sumOpenInterest"])
        oi_prev = float(data[-2]["sumOpenInterest"])
        oi_rising = oi_current > oi_prev
        price_rising = price_change_pct > 0

        if price_rising and oi_rising:
            return 5.0
        elif price_rising and not oi_rising:
            return -5.0
        else:
            return 0.0
    except Exception as e:
        logger.warning(f"OI fetch failed for {asset}: {e}")
        return 0.0


async def _fetch_liquidation_sweep(asset: str) -> Tuple[bool, str, float]:
    """
    Check for recent liquidation cascades on Binance.
    Returns (sweep_detected, sweep_direction, confidence_boost).
    sweep_direction: "CALL" (long sweep → potential bounce up) or "PUT".
    """
    binance_sym = CRYPTO_BINANCE_SYMBOLS.get(asset)
    if not binance_sym:
        return False, "NEUTRAL", 0.0

    try:
        url = f"https://fapi.binance.com/fapi/v1/allForceOrders?symbol={binance_sym}&limit=10"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return False, "NEUTRAL", 0.0
                data = await resp.json()

        if not data:
            return False, "NEUTRAL", 0.0

        now_ms = time.time() * 1000
        long_liq_usd = 0.0
        short_liq_usd = 0.0

        for order in data:
            order_time = float(order.get("time", 0))
            if now_ms - order_time > 5 * 60 * 1000:  # only last 5 minutes
                continue
            qty = float(order.get("origQty", 0))
            price = float(order.get("price", 0))
            value = qty * price
            side = order.get("side", "")
            if side == "SELL":    # forced sell = long liquidated
                long_liq_usd += value
            elif side == "BUY":   # forced buy = short liquidated
                short_liq_usd += value

        total_liq = long_liq_usd + short_liq_usd
        THRESHOLD = 10_000_000  # $10M

        if total_liq > THRESHOLD:
            # Long sweep → expect bounce upward (CALL)
            # Short sweep → expect bounce downward (PUT)
            direction = "CALL" if long_liq_usd >= short_liq_usd else "PUT"
            return True, direction, 10.0

        return False, "NEUTRAL", 0.0
    except Exception as e:
        logger.warning(f"Liquidation sweep fetch failed for {asset}: {e}")
        return False, "NEUTRAL", 0.0


async def _fetch_news_sentiment(asset: str) -> float:
    """
    Fetch Yahoo Finance RSS news and score by bullish/bearish keywords.
    Returns normalized score 0-100 (50 = neutral).
    Cached 15 minutes.
    """
    cache_key = f"news_{asset}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    ticker = NEWS_RSS_TICKERS.get(asset, "")
    if not ticker:
        return 50.0

    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote(ticker, safe='')}&region=US&lang=en-US"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                text = await resp.text()

        root = ET.fromstring(text)
        bullish = 0
        bearish = 0
        for item in root.iter("item"):
            title_el = item.find("title")
            desc_el = item.find("description")
            text_blob = " ".join(filter(None, [
                title_el.text if title_el is not None else "",
                desc_el.text if desc_el is not None else "",
            ])).lower()
            words = set(text_blob.split())
            bullish += len(words & _BULLISH_KEYWORDS)
            bearish += len(words & _BEARISH_KEYWORDS)

        total = bullish + bearish
        if total == 0:
            score = 50.0
        else:
            raw = (bullish - bearish) / total  # -1 to +1
            score = (raw + 1) / 2 * 100        # normalize to 0-100

        _cache_set(cache_key, score, 900)  # 15 min TTL
        return score
    except Exception as e:
        logger.warning(f"News sentiment fetch failed for {asset}: {e}")
        return 50.0


def _news_sentiment_score(norm: float) -> Tuple[float, str]:
    if norm > 60:
        return norm, "CALL"
    elif norm < 40:
        return 100.0 - norm, "PUT"
    else:
        return 50.0, "NEUTRAL"


async def _fetch_econ_calendar() -> Tuple[bool, Optional[str]]:
    """
    Fetch economic calendar and check for HIGH impact events within 30 minutes.
    Returns (gate_active, reason_string).
    Cached 2 hours via module-level _econ_cache (shared across all assets to avoid 429s).
    """
    now_mono = time.monotonic()
    if _econ_cache["data"] is not None and now_mono - _econ_cache["ts"] < 7200:
        return _econ_cache["data"]

    # Set placeholder immediately (before any await) so concurrent coroutines skip the fetch
    _econ_cache["data"] = (False, None)
    _econ_cache["ts"] = now_mono

    _ECON_URLS = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    ]

    try:
        events = None
        async with aiohttp.ClientSession() as session:
            for url in _ECON_URLS:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            raise ValueError(f"HTTP {resp.status}")
                        events = await resp.json(content_type=None)
                    break
                except Exception as e:
                    logger.warning(f"Econ calendar URL {url} failed: {e}")

        if events is None:
            raise ValueError("All econ calendar sources failed")

        now = datetime.now(timezone.utc)
        high_soon = []

        for ev in events:
            if ev.get("impact", "").lower() != "high":
                continue
            date_str = ev.get("date", "")
            if not date_str:
                continue
            try:
                ev_time = datetime.fromisoformat(date_str)
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)
                diff_minutes = (ev_time - now).total_seconds() / 60
                if 0 <= diff_minutes <= 30:
                    high_soon.append(ev.get("title", "High Impact Event"))
            except (ValueError, TypeError):
                continue

        if high_soon:
            reason = f"HIGH impact event(s) within 30min: {', '.join(high_soon[:3])}"
            result: Tuple[bool, Optional[str]] = (True, reason)
        else:
            result = (False, None)

        _econ_cache["data"] = result
        _econ_cache["ts"] = time.monotonic()
        return result
    except Exception as e:
        logger.warning(f"Econ calendar fetch failed: {e}")
        # Leave placeholder so we don't retry for another 2 hours
        return (False, None)


async def _fetch_vix() -> float:
    """Fetch VIX level via yfinance. Cached 15 minutes."""
    cached = _cache_get("vix")
    if cached is not None:
        return cached
    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download("^VIX", period="2d", interval="1d", progress=False, auto_adjust=True),
        )
        if df is None or len(df) == 0:
            raise ValueError("No VIX data")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        vix = _safe_float(df["Close"].dropna().iloc[-1], default=20.0)
        _cache_set("vix", vix, 900)  # 15 min TTL
        return vix
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
        return 20.0  # neutral fallback


def _vix_score(vix: float, asset: str) -> Tuple[float, str]:
    if vix > 30:
        if asset in METALS_ASSETS:
            return 70.0, "CALL"   # fear → gold safe haven
        else:
            return 65.0, "PUT"   # fear → crypto risk-off
    elif vix < 15:
        return 55.0, "NEUTRAL"   # complacency — slight caution
    else:
        return 50.0, "NEUTRAL"


# ---------------------------------------------------------------------------
# Helper: compute weighted directional score from scores + directions + weights
# ---------------------------------------------------------------------------

def _weighted_directional_score(
    scores: Dict[str, float],
    directions: Dict[str, str],
    weights: Dict[str, float],
) -> Tuple[float, str, Dict[str, float]]:
    """
    Returns (weighted_confidence 0-100, overall_direction, directional_scores dict).
    """
    directional_scores: Dict[str, float] = {}
    bullish_weight = 0.0
    bearish_weight = 0.0

    for name, w in weights.items():
        d = directions.get(name, "NEUTRAL")
        s = scores.get(name, 50.0)
        if d == "CALL":
            directional_scores[name] = s
            bullish_weight += w
        elif d == "PUT":
            directional_scores[name] = 100.0 - s
            bearish_weight += w
        else:
            directional_scores[name] = 50.0

    overall_direction = "CALL" if bullish_weight >= bearish_weight else "PUT"
    confidence = sum(directional_scores.get(name, 50.0) * w for name, w in weights.items())
    confidence = max(0.0, min(100.0, confidence))
    return confidence, overall_direction, directional_scores


# ---------------------------------------------------------------------------
# Main compute_confidence — upgraded with smart money + macro layers
# ---------------------------------------------------------------------------

async def compute_confidence(asset: str) -> ConfidenceResult:
    """Compute confidence score for the given asset using yfinance + external data."""
    yf_symbol = ASSET_SYMBOLS.get(asset)
    display_name = ASSET_DISPLAY.get(asset, asset)
    flag = ASSET_FLAGS.get(asset, "")

    if not yf_symbol:
        return ConfidenceResult(
            confidence=50.0,
            direction="CALL",
            expiry="5min",
            top_indicators=[],
            indicators={},
            price=0.0,
            asset=asset,
            display_name=display_name,
            flag=flag,
            error=f"Unknown asset: {asset}",
        )

    # Determine asset type
    if asset in CRYPTO_ASSETS:
        asset_type = "crypto"
        weights = CRYPTO_WEIGHTS
    elif asset in METALS_ASSETS:
        asset_type = "metals"
        weights = METALS_WEIGHTS
    else:
        asset_type = "forex"
        weights = FOREX_WEIGHTS

    try:
        # --- Fetch price data ---
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(yf_symbol, period="5d", interval="5m", progress=False, auto_adjust=True),
        )

        if df is None or len(df) < 30:
            df = await loop.run_in_executor(
                None,
                lambda: yf.download(yf_symbol, period="10d", interval="15m", progress=False, auto_adjust=True),
            )

        if df is None or len(df) < 10:
            return ConfidenceResult(
                confidence=50.0,
                direction="CALL",
                expiry="5min",
                top_indicators=[],
                indicators={},
                price=0.0,
                asset=asset,
                display_name=display_name,
                flag=flag,
                error="Insufficient data from yfinance",
            )

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        closes = df["Close"].dropna()
        volumes = df["Volume"].dropna() if "Volume" in df.columns else pd.Series([1] * len(closes))

        if len(closes) < 10:
            return ConfidenceResult(
                confidence=50.0,
                direction="CALL",
                expiry="5min",
                top_indicators=[],
                indicators={},
                price=0.0,
                asset=asset,
                display_name=display_name,
                flag=flag,
                error="Insufficient close data",
            )

        current_price = _safe_float(closes.iloc[-1])
        prev_price = _safe_float(closes.iloc[-2]) if len(closes) > 1 else current_price
        price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0.0

        # --- Technical indicators ---
        rsi_val = _compute_rsi(closes)
        rsi_score_val, rsi_dir = _rsi_score(rsi_val)

        macd_val, macd_signal, macd_hist = _compute_macd(closes)
        macd_score_val, macd_dir = _macd_score(macd_val, macd_signal, macd_hist)

        bb_upper, bb_mid, bb_lower = _compute_bollinger(closes)
        bb_score_val, bb_dir = _bollinger_score(current_price, bb_upper, bb_mid, bb_lower)

        ema9 = _compute_ema(closes, 9)
        ema21 = _compute_ema(closes, 21)
        ema_score_val, ema_dir = _ema_score(ema9, ema21)

        vol_score_val, vol_dir = _volume_score(volumes)
        candle_score_val, candle_dir = _candlestick_score(df)

        # --- Launch all external fetches concurrently ---
        fetch_coros: Dict[str, Any] = {
            "news": _fetch_news_sentiment(asset),
            "econ": _fetch_econ_calendar(),
        }

        if asset_type == "crypto":
            fetch_coros["fear_greed"] = _fetch_fear_greed()
            fetch_coros["funding"] = _fetch_funding_rate(asset)
            fetch_coros["oi_adj"] = _fetch_oi_adjustment(asset, price_change_pct)
            fetch_coros["sweep"] = _fetch_liquidation_sweep(asset)
            fetch_coros["vix"] = _fetch_vix()
            fetch_coros["dxy"] = _fetch_dxy_change()

        elif asset_type == "metals":
            fetch_coros["dxy"] = _fetch_dxy_change()
            fetch_coros["cot"] = _fetch_cot_score(asset)
            fetch_coros["vix"] = _fetch_vix()

        else:  # forex
            fetch_coros["dxy"] = _fetch_dxy_change()
            if asset in COT_MARKET_KEYWORDS:
                fetch_coros["cot"] = _fetch_cot_score(asset)

        coro_names = list(fetch_coros.keys())
        coro_list = list(fetch_coros.values())
        raw_results = await asyncio.gather(*coro_list, return_exceptions=True)

        ext: Dict[str, Any] = {}
        for name, result in zip(coro_names, raw_results):
            if isinstance(result, Exception):
                logger.warning(f"External fetch '{name}' error for {asset}: {result}")
                ext[name] = None
            else:
                ext[name] = result

        # --- Score external indicators ---
        scores: Dict[str, float] = {
            "RSI": rsi_score_val,
            "MACD": macd_score_val,
            "Bollinger": bb_score_val,
            "EMA": ema_score_val,
            "Volume": vol_score_val,
            "Candlestick": candle_score_val,
        }
        directions: Dict[str, str] = {
            "RSI": rsi_dir,
            "MACD": macd_dir,
            "Bollinger": bb_dir,
            "EMA": ema_dir,
            "Volume": vol_dir,
            "Candlestick": candle_dir,
        }

        # News sentiment
        news_norm = ext.get("news") if ext.get("news") is not None else 50.0
        news_s, news_d = _news_sentiment_score(float(news_norm))
        scores["News"] = news_s
        directions["News"] = news_d

        # DXY
        if "dxy" in ext and ext["dxy"] is not None:
            dxy_change = float(ext["dxy"])
            dxy_s, dxy_d = _dxy_score(dxy_change, asset)
        else:
            dxy_s, dxy_d = 50.0, "NEUTRAL"
        scores["DXY"] = dxy_s
        directions["DXY"] = dxy_d

        # VIX
        vix_val = 20.0
        if "vix" in ext and ext["vix"] is not None:
            vix_val = float(ext["vix"])
        vix_s, vix_d = _vix_score(vix_val, asset)
        scores["VIX"] = vix_s
        directions["VIX"] = vix_d

        # COT
        if "cot" in ext and ext["cot"] is not None:
            cot_raw = float(ext["cot"])
            cot_s, cot_d = _cot_score_to_direction(cot_raw)
        else:
            cot_s, cot_d = 50.0, "NEUTRAL"
        scores["COT"] = cot_s
        directions["COT"] = cot_d

        # Fear & Greed (crypto only)
        fg_val = 50.0
        if "fear_greed" in ext and ext["fear_greed"] is not None:
            fg_val = float(ext["fear_greed"])
        fg_s, fg_d = _fear_greed_score(fg_val)
        scores["FearGreed"] = fg_s
        directions["FearGreed"] = fg_d

        # Funding Rate (crypto only)
        funding_val = 0.0
        if "funding" in ext and ext["funding"] is not None:
            funding_val = float(ext["funding"])
        fund_s, fund_d = _funding_rate_score(funding_val)
        scores["FundingRate"] = fund_s
        directions["FundingRate"] = fund_d

        # --- Weighted confidence ---
        weighted_confidence, overall_direction, directional_scores = _weighted_directional_score(
            scores, directions, weights
        )

        # --- Open interest adjustment (crypto only — post-weighting modifier) ---
        oi_adj = 0.0
        if "oi_adj" in ext and ext["oi_adj"] is not None:
            oi_adj = float(ext["oi_adj"])
        # Apply OI adjustment to deviation from 50
        if oi_adj != 0.0:
            dev = weighted_confidence - 50.0
            dev += oi_adj if overall_direction == "CALL" else -oi_adj
            weighted_confidence = max(0.0, min(100.0, 50.0 + dev))

        # --- Liquidation sweep boost (crypto only) ---
        sweep_detected = False
        if "sweep" in ext and ext["sweep"] is not None:
            sweep_detected, sweep_dir, sweep_boost = ext["sweep"]
            if sweep_detected and sweep_dir == candle_dir and sweep_boost > 0:
                dev = weighted_confidence - 50.0
                dev_boost = sweep_boost if overall_direction == "CALL" else -sweep_boost
                weighted_confidence = max(0.0, min(100.0, 50.0 + dev + dev_boost))

        # --- Economic calendar gate ---
        econ_gate_active = False
        econ_gate_reason: Optional[str] = None
        econ_result = ext.get("econ")
        if econ_result is not None:
            econ_gate_active, econ_gate_reason = econ_result
        if econ_gate_active:
            # Reduce signal strength by 20% (compress deviation from 50)
            dev = weighted_confidence - 50.0
            weighted_confidence = max(0.0, min(100.0, 50.0 + dev * 0.8))

        # --- Session timing multiplier ---
        session_multiplier = _get_session_multiplier()
        dev = weighted_confidence - 50.0
        weighted_confidence = max(0.0, min(100.0, 50.0 + dev * session_multiplier))

        # --- Summary scores for display ---
        smart_money_parts = []
        if "FundingRate" in directional_scores:
            smart_money_parts.append(directional_scores["FundingRate"])
        if "COT" in directional_scores:
            smart_money_parts.append(directional_scores["COT"])
        smart_money_score = float(np.mean(smart_money_parts)) if smart_money_parts else 50.0

        macro_parts = []
        if "DXY" in directional_scores:
            macro_parts.append(directional_scores["DXY"])
        if "VIX" in directional_scores:
            macro_parts.append(directional_scores["VIX"])
        macro_score = float(np.mean(macro_parts)) if macro_parts else 50.0

        sentiment_parts = []
        if "News" in directional_scores:
            sentiment_parts.append(directional_scores["News"])
        if "FearGreed" in directional_scores:
            sentiment_parts.append(directional_scores["FearGreed"])
        sentiment_score = float(np.mean(sentiment_parts)) if sentiment_parts else 50.0

        # --- Top indicators by signal strength ---
        deviations = {name: abs(directional_scores.get(name, 50.0) - 50.0) for name in weights}
        top_indicators = sorted(deviations, key=deviations.get, reverse=True)[:3]

        expiry = _determine_expiry(weighted_confidence)

        return ConfidenceResult(
            confidence=round(weighted_confidence, 2),
            direction=overall_direction,
            expiry=expiry,
            top_indicators=top_indicators,
            indicators={
                "RSI": round(rsi_score_val, 2),
                "MACD": round(macd_score_val, 2),
                "Bollinger": round(bb_score_val, 2),
                "EMA": round(ema_score_val, 2),
                "Volume": round(vol_score_val, 2),
                "Candlestick": round(candle_score_val, 2),
                "DXY": round(dxy_s, 2),
                "COT": round(cot_s, 2),
                "News": round(news_s, 2),
                "FearGreed": round(fg_s, 2),
                "FundingRate": round(fund_s, 2),
                "VIX": round(vix_s, 2),
                "rsi_value": round(rsi_val, 2),
                "macd_value": round(macd_val, 6),
                "macd_signal": round(macd_signal, 6),
                "macd_histogram": round(macd_hist, 6),
                "bb_upper": round(bb_upper, 6),
                "bb_middle": round(bb_mid, 6),
                "bb_lower": round(bb_lower, 6),
                "ema9": round(ema9, 6),
                "ema21": round(ema21, 6),
                "vix_value": round(vix_val, 2),
                "fg_value": round(fg_val, 2),
                "funding_rate": round(funding_val, 6),
            },
            price=round(current_price, 6),
            asset=asset,
            display_name=display_name,
            flag=flag,
            price_change_pct=round(price_change_pct, 4),
            smart_money_score=round(smart_money_score, 2),
            macro_score=round(macro_score, 2),
            sentiment_score=round(sentiment_score, 2),
            session_multiplier=session_multiplier,
            econ_gate_active=econ_gate_active,
            econ_gate_reason=econ_gate_reason,
            liquidity_sweep_detected=sweep_detected,
        )

    except Exception as e:
        logger.error(f"Error computing confidence for {asset}: {e}")
        return ConfidenceResult(
            confidence=50.0,
            direction="CALL",
            expiry="5min",
            top_indicators=[],
            indicators={},
            price=0.0,
            asset=asset,
            display_name=display_name,
            flag=flag,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Batch compute (unchanged logic)
# ---------------------------------------------------------------------------

async def compute_all_assets(assets: List[str]) -> Dict[str, ConfidenceResult]:
    """Compute confidence for multiple assets concurrently."""
    tasks = [compute_confidence(asset) for asset in assets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = {}
    for asset, result in zip(assets, results):
        if isinstance(result, Exception):
            display_name = ASSET_DISPLAY.get(asset, asset)
            flag = ASSET_FLAGS.get(asset, "")
            output[asset] = ConfidenceResult(
                confidence=50.0,
                direction="CALL",
                expiry="5min",
                top_indicators=[],
                indicators={},
                price=0.0,
                asset=asset,
                display_name=display_name,
                flag=flag,
                error=str(result),
            )
        else:
            output[asset] = result
    return output


# ---------------------------------------------------------------------------
# Serialization — updated with new fields
# ---------------------------------------------------------------------------

def confidence_result_to_dict(result: ConfidenceResult) -> dict:
    return {
        "asset": result.asset,
        "display_name": result.display_name,
        "flag": result.flag,
        "confidence": result.confidence,
        "direction": result.direction,
        "expiry": result.expiry,
        "top_indicators": result.top_indicators,
        "indicators": result.indicators,
        "price": result.price,
        "price_change_pct": result.price_change_pct,
        "error": result.error,
        # Smart money / macro / sentiment layers
        "smart_money_score": result.smart_money_score,
        "macro_score": result.macro_score,
        "sentiment_score": result.sentiment_score,
        "session_multiplier": result.session_multiplier,
        "econ_gate_active": result.econ_gate_active,
        "econ_gate_reason": result.econ_gate_reason,
        "liquidity_sweep_detected": result.liquidity_sweep_detected,
    }

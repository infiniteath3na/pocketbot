import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

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


def _safe_float(val, default=50.0) -> float:
    try:
        v = float(val)
        if np.isnan(v) or np.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def _compute_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return _safe_float(rsi)


def _rsi_score(rsi: float) -> Tuple[float, str]:
    """Returns (score 0-100, direction hint)"""
    if rsi < 30:
        # Oversold — bullish
        score = 80 + (30 - rsi) / 30 * 20  # 80-100
        return min(100.0, score), "CALL"
    elif rsi > 70:
        # Overbought — bearish
        score = 80 + (rsi - 70) / 30 * 20  # 80-100 bearish
        return min(100.0, score), "PUT"
    else:
        # Neutral
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
        # Bullish crossover
        strength = min(abs(histogram) / (abs(macd) + 1e-10), 1.0)
        score = 60 + strength * 40
        return _safe_float(score), "CALL"
    elif macd < signal and histogram < 0:
        # Bearish crossover
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
        # Near lower band — bullish
        score = 80 + (0.1 - position) / 0.1 * 20
        return min(100.0, _safe_float(score)), "CALL"
    elif position >= 0.9:
        # Near upper band — bearish
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

    # Get last 3 candles
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

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

    # Doji: body < 10% of range
    is_doji = body < full_range * 0.1

    # Hammer: small body at top, long lower shadow (bullish)
    is_hammer = (
        lower_shadow > body * 2
        and upper_shadow < body * 0.5
        and close_ > open_  # green candle ideally
    )

    # Shooting star: small body at bottom, long upper shadow (bearish)
    is_shooting_star = (
        upper_shadow > body * 2
        and lower_shadow < body * 0.5
        and close_ < open_
    )

    # Bullish engulfing
    prev_open = _safe_float(prev["Open"])
    prev_close = _safe_float(prev["Close"])
    is_bullish_engulfing = (
        prev_close < prev_open  # prev candle was red
        and close_ > open_  # current is green
        and open_ < prev_close
        and close_ > prev_open
    )

    # Bearish engulfing
    is_bearish_engulfing = (
        prev_close > prev_open  # prev candle was green
        and close_ < open_  # current is red
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


def _determine_expiry(confidence: float) -> str:
    if confidence >= 80:
        return "1min"
    elif confidence >= 65:
        return "5min"
    else:
        return "15min"


async def compute_confidence(asset: str) -> ConfidenceResult:
    """Compute confidence score for the given asset using yfinance data."""
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

    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(yf_symbol, period="5d", interval="5m", progress=False, auto_adjust=True),
        )

        if df is None or len(df) < 30:
            # Try with longer period
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

        # Flatten multi-level columns if present
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

        # --- RSI ---
        rsi_val = _compute_rsi(closes)
        rsi_score_val, rsi_dir = _rsi_score(rsi_val)

        # --- MACD ---
        macd_val, macd_signal, macd_hist = _compute_macd(closes)
        macd_score_val, macd_dir = _macd_score(macd_val, macd_signal, macd_hist)

        # --- Bollinger Bands ---
        bb_upper, bb_mid, bb_lower = _compute_bollinger(closes)
        bb_score_val, bb_dir = _bollinger_score(current_price, bb_upper, bb_mid, bb_lower)

        # --- EMA crossover ---
        ema9 = _compute_ema(closes, 9)
        ema21 = _compute_ema(closes, 21)
        ema_score_val, ema_dir = _ema_score(ema9, ema21)

        # --- Volume ---
        vol_score_val, vol_dir = _volume_score(volumes)

        # --- Candlestick patterns ---
        candle_score_val, candle_dir = _candlestick_score(df)

        # --- Weighted confidence ---
        weights = {
            "RSI": 0.20,
            "MACD": 0.25,
            "Bollinger": 0.20,
            "EMA": 0.20,
            "Volume": 0.10,
            "Candlestick": 0.05,
        }

        scores = {
            "RSI": rsi_score_val,
            "MACD": macd_score_val,
            "Bollinger": bb_score_val,
            "EMA": ema_score_val,
            "Volume": vol_score_val,
            "Candlestick": candle_score_val,
        }

        directions = {
            "RSI": rsi_dir,
            "MACD": macd_dir,
            "Bollinger": bb_dir,
            "EMA": ema_dir,
            "Volume": vol_dir,
            "Candlestick": candle_dir,
        }

        # Determine overall direction: count bullish vs bearish signals
        bullish_weight = 0.0
        bearish_weight = 0.0
        for name, w in weights.items():
            d = directions[name]
            if d == "CALL":
                bullish_weight += w
            elif d == "PUT":
                bearish_weight += w

        overall_direction = "CALL" if bullish_weight >= bearish_weight else "PUT"

        # Convert scores to directional scores (>50 = bullish, <50 = bearish)
        directional_scores = {}
        for name, score in scores.items():
            d = directions[name]
            if d == "CALL":
                directional_scores[name] = score
            elif d == "PUT":
                directional_scores[name] = 100.0 - score
            else:
                directional_scores[name] = 50.0

        weighted_confidence = sum(directional_scores[name] * weights[name] for name in weights)
        weighted_confidence = max(0.0, min(100.0, weighted_confidence))

        # Top 3 contributing indicators (by deviation from 50)
        deviations = {name: abs(directional_scores[name] - 50.0) for name in scores}
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
                "rsi_value": round(rsi_val, 2),
                "macd_value": round(macd_val, 6),
                "macd_signal": round(macd_signal, 6),
                "macd_histogram": round(macd_hist, 6),
                "bb_upper": round(bb_upper, 6),
                "bb_middle": round(bb_mid, 6),
                "bb_lower": round(bb_lower, 6),
                "ema9": round(ema9, 6),
                "ema21": round(ema21, 6),
            },
            price=round(current_price, 6),
            asset=asset,
            display_name=display_name,
            flag=flag,
            price_change_pct=round(price_change_pct, 4),
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
    }

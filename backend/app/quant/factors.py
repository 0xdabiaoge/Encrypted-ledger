"""
Encrypted Ledger - Five-Pillar Factor Library & Composite Alpha Matrix
Computes trend momentum, volatility channels, volume flow, micro-orderbook, and derivatives.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple
from app.quant.calculus import calculate_calculus_dynamics, calculate_definite_integral_energy


def _compute_rsi(closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _compute_atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> Tuple[float, float]:
    if len(closes) < period + 1:
        return 0.0, 0.0
    trs = []
    for i in range(1, len(closes)):
        h, l, prev_c = highs[i], lows[i], closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    atr = sum(trs[-period:]) / period
    atr_pct = (atr / closes[-1]) * 100.0 if closes[-1] > 0 else 0.0
    return round(atr, 4), round(atr_pct, 2)


def _compute_adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < period * 2:
        return 20.0
    plus_dms, minus_dms, trs = [], [], []
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)
        trs.append(tr)

    smooth_tr = sum(trs[:period])
    smooth_plus = sum(plus_dms[:period])
    smooth_minus = sum(minus_dms[:period])
    dx_list = []

    for i in range(period, len(trs)):
        smooth_tr = smooth_tr - (smooth_tr / period) + trs[i]
        smooth_plus = smooth_plus - (smooth_plus / period) + plus_dms[i]
        smooth_minus = smooth_minus - (smooth_minus / period) + minus_dms[i]
        plus_di = (smooth_plus / smooth_tr * 100) if smooth_tr > 0 else 0.0
        minus_di = (smooth_minus / smooth_tr * 100) if smooth_tr > 0 else 0.0
        di_sum = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / di_sum * 100) if di_sum > 0 else 0.0
        dx_list.append(dx)

    if not dx_list:
        return 20.0
    adx = sum(dx_list[-period:]) / len(dx_list[-period:])
    return round(adx, 2)


def compute_factor_matrix(
    candles_15m: List[Dict[str, Any]],
    orderbook_imbalance: float = 0.0,
    long_short_ratio: float = 1.0,
    funding_rate: float = 0.0
) -> Dict[str, Any]:
    """
    Computes all 5 Pillars and composite Alpha Score.
    """
    if len(candles_15m) < 30:
        return {
            "alpha_score": 50.0,
            "signal": "NEUTRAL",
            "confidence": 50.0,
            "error": "insufficient_candles"
        }

    closes = [c["close"] for c in candles_15m]
    highs = [c["high"] for c in candles_15m]
    lows = [c["low"] for c in candles_15m]
    volumes = [c["volume"] for c in candles_15m]

    # Pillar 1: Trend & Momentum
    rsi = _compute_rsi(closes, 14)
    adx = _compute_adx(highs, lows, closes, 14)
    calculus = calculate_calculus_dynamics(closes)

    # Pillar 2: Volatility & Channels
    atr, atr_pct = _compute_atr(highs, lows, closes, 14)
    integral = calculate_definite_integral_energy(closes, 20)

    # Pillar 3: Volume & Money Flow
    avg_vol_20 = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1.0
    current_vol = volumes[-1]
    vol_surge_ratio = round(current_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

    # Pillar 4: Orderbook Microstructure
    # Imbalance from -1.0 (heavy sell) to +1.0 (heavy buy)

    # Pillar 5: Smart Money & Derivatives
    # long_short_ratio: > 1.25 is bullish crowd, < 0.8 is bearish crowd

    # Alpha Scoring Algorithm (0 ~ 100)
    score = 50.0

    # Trend component
    vel = calculus["velocity"]
    acc = calculus["acceleration"]
    if vel > 0.15:
        score += min(15.0, vel * 10)
    elif vel < -0.15:
        score -= min(15.0, abs(vel) * 10)

    if acc > 0:
        score += 5.0
    elif acc < 0:
        score -= 5.0

    # ADX Trend Filter: high ADX amplifies score, low ADX squashes to 50
    if adx > 25:
        trend_mult = 1.2
    elif adx < 18:
        trend_mult = 0.7  # choppy garbage market
    else:
        trend_mult = 1.0

    score = 50.0 + (score - 50.0) * trend_mult

    # RSI Adjustments
    if 52 <= rsi <= 68:
        score += 6.0   # Healthy bullish expansion
    elif 32 <= rsi <= 48:
        score -= 6.0   # Healthy bearish breakdown
    elif rsi > 78:
        score -= 8.0   # Overbought exhaustion risk
    elif rsi < 22:
        score += 8.0   # Oversold bounce potential

    # Orderbook Imbalance Influence
    score += orderbook_imbalance * 8.0

    # Clamp Score
    score = max(0.0, min(100.0, round(score, 2)))

    # Signal & Confidence Determination
    if score >= 75.0:
        signal = "STRONG_BUY"
        confidence = score
    elif score >= 62.0:
        signal = "BUY"
        confidence = score
    elif score <= 25.0:
        signal = "STRONG_SELL"
        confidence = 100.0 - score
    elif score <= 38.0:
        signal = "SELL"
        confidence = 100.0 - score
    else:
        signal = "HOLD"
        confidence = 50.0

    return {
        "alpha_score": score,
        "signal": signal,
        "confidence": round(confidence, 1),
        "pillar_1_trend": {
            "rsi": rsi,
            "adx": adx,
            "velocity": calculus["velocity"],
            "acceleration": calculus["acceleration"],
            "regime": calculus["regime"]
        },
        "pillar_2_volatility": {
            "atr": atr,
            "atr_pct": atr_pct,
            "integral_energy": integral["integral_energy"],
            "mean_reversion_prob": integral["mean_reversion_prob"]
        },
        "pillar_3_volume": {
            "vol_surge_ratio": vol_surge_ratio,
            "current_volume": current_vol
        },
        "pillar_4_microstructure": {
            "imbalance_ratio": round(orderbook_imbalance, 3)
        },
        "pillar_5_derivatives": {
            "long_short_ratio": round(long_short_ratio, 2),
            "funding_rate": funding_rate
        }
    }

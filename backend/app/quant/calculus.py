"""
Encrypted Ledger - Causal Calculus & Kinematic Physics Engine
Computes chronological velocity, acceleration, definite integrals, and stochastic regimes.
Strict zero lookahead bias: operates exclusively on closed historical candles.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple


def _calc_ema(series: Sequence[float], period: int) -> List[float]:
    """Causal exponential moving average."""
    if not series:
        return []
    alpha = 2.0 / (period + 1.0)
    ema = [series[0]]
    for val in series[1:]:
        ema.append(alpha * val + (1.0 - alpha) * ema[-1])
    return ema


def _normal_cdf(x: float) -> float:
    """Accurate standard normal cumulative distribution function (error function based)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def calculate_calculus_dynamics(closes: Sequence[float]) -> Dict[str, Any]:
    """
    Computes first derivative (velocity) and second derivative (acceleration) on price series.
    Returns: velocity, acceleration, jerk, and regime classification.
    """
    if len(closes) < 10:
        return {
            "velocity": 0.0,
            "acceleration": 0.0,
            "jerk": 0.0,
            "regime": "insufficient_data",
            "confidence_score": 50.0
        }

    ema9 = _calc_ema(closes, 9)
    ema21 = _calc_ema(closes, 21)

    # First Derivative: Price Velocity (dP/dt in % per bar)
    v1 = (ema9[-1] - ema9[-2]) / ema9[-2] * 100.0 if ema9[-2] != 0 else 0.0
    v2 = (ema9[-2] - ema9[-3]) / ema9[-3] * 100.0 if ema9[-3] != 0 else 0.0
    v3 = (ema9[-3] - ema9[-4]) / ema9[-4] * 100.0 if ema9[-4] != 0 else 0.0

    # Second Derivative: Price Acceleration (d^2P/dt^2 in % per bar^2)
    acc1 = v1 - v2
    acc2 = v2 - v3

    # Third Derivative: Jerk (rate of acceleration change)
    jerk = acc1 - acc2

    # Regime Classification
    if v1 > 0.3 and acc1 > 0:
        regime = "strong_bullish_expansion"  # 强势多头加速
        conf = 85.0
    elif v1 > 0.1 and acc1 <= 0:
        regime = "bullish_deceleration"       # 多头减速滞涨
        conf = 65.0
    elif v1 < -0.3 and acc1 < 0:
        regime = "strong_bearish_expansion"  # 强势空头加速
        conf = 85.0
    elif v1 < -0.1 and acc1 >= 0:
        regime = "bearish_deceleration"       # 空头动能衰竭
        conf = 65.0
    else:
        regime = "quiescent_equilibrium"     # 震荡均衡
        conf = 50.0

    return {
        "velocity": round(v1, 4),
        "acceleration": round(acc1, 4),
        "jerk": round(jerk, 4),
        "regime": regime,
        "confidence_score": conf,
        "ema9": round(ema9[-1], 4),
        "ema21": round(ema21[-1], 4)
    }


def calculate_definite_integral_energy(closes: Sequence[float], period: int = 20) -> Dict[str, Any]:
    """
    Computes definite integral of price deviation from mean: \\int |P(t) - EMA(t)| dt.
    Quantifies the accumulated thermodynamic kinetic energy and mean-reversion potential.
    """
    if len(closes) < period:
        return {"integral_energy": 0.0, "mean_reversion_prob": 0.5}

    ema = _calc_ema(closes, period)
    window_closes = closes[-period:]
    window_ema = ema[-period:]

    # Discrete trapezoidal integral of deviation
    accumulated_deviation = 0.0
    signed_deviation = 0.0
    for c, m in zip(window_closes, window_ema):
        diff = (c - m) / m
        accumulated_deviation += abs(diff)
        signed_deviation += diff

    # Normalized standard deviation for Z-score
    mean_val = sum(window_closes) / period
    variance = sum((x - mean_val) ** 2 for x in window_closes) / period
    std_dev = math.sqrt(variance) if variance > 0 else 1.0

    latest_z = (closes[-1] - mean_val) / std_dev
    # Reversion probability based on Normal CDF tails
    if latest_z > 0:
        reversion_prob = _normal_cdf(latest_z - 1.5)
    else:
        reversion_prob = _normal_cdf(-latest_z - 1.5)

    return {
        "integral_energy": round(accumulated_deviation, 4),
        "signed_integral": round(signed_deviation, 4),
        "latest_z_score": round(latest_z, 2),
        "mean_reversion_prob": round(reversion_prob, 3)
    }

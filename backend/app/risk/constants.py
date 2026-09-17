"""
Encrypted Ledger - Execution Layer 17-Factor Risk Constants
Single Source of Truth (SSOT) across LLM prompt definitions, interceptor checks, and admin UI.
"""
from __future__ import annotations

from typing import Dict, Any
from app.core.config import settings


def get_effective_daily_loss_limit(equity_usd: float) -> float:
    """Return min(MAX_DAILY_LOSS_USDT, equity * DAILY_LOSS_EQUITY_RATIO)."""
    equity_limit = equity_usd * settings.RISK_DAILY_LOSS_EQUITY_RATIO
    if settings.RISK_MAX_DAILY_LOSS_USDT > 0:
        return min(settings.RISK_MAX_DAILY_LOSS_USDT, equity_limit)
    return equity_limit


def get_effective_single_asset_margin(equity_usd: float) -> float:
    """Return min(MAX_SINGLE_ASSET_MARGIN_USDT, equity * SINGLE_ASSET_EQUITY_RATIO)."""
    ratio_limit = equity_usd * settings.RISK_SINGLE_ASSET_EQUITY_RATIO
    if settings.RISK_MAX_SINGLE_ASSET_MARGIN_USDT > 0:
        return min(settings.RISK_MAX_SINGLE_ASSET_MARGIN_USDT, ratio_limit)
    return ratio_limit


def get_effective_1r_risk_budget(equity_usd: float, pool_configured_usd: float = 15.0) -> float:
    """Return min(pool_configured_usd, equity * RISK_PER_TRADE_RATIO)."""
    equity_risk = equity_usd * settings.RISK_PER_TRADE_RATIO
    return min(pool_configured_usd, equity_risk) if pool_configured_usd > 0 else equity_risk


def dump_risk_constants_summary(equity_usd: float = 1000.0) -> Dict[str, Any]:
    """Provide structured risk parameters snapshot for LLM context injection and UI display."""
    return {
        "max_concurrent_positions": settings.RISK_MAX_CONCURRENT_POSITIONS,
        "max_same_direction_positions": settings.RISK_MAX_SAME_DIRECTION_POSITIONS,
        "max_margin_equity_ratio": settings.RISK_MAX_MARGIN_EQUITY_RATIO,
        "effective_single_asset_margin_usd": round(get_effective_single_asset_margin(equity_usd), 2),
        "min_leverage": settings.RISK_MIN_LEVERAGE,
        "max_leverage": settings.RISK_MAX_LEVERAGE,
        "effective_1r_risk_usd": round(get_effective_1r_risk_budget(equity_usd), 2),
        "min_risk_reward_ratio": settings.RISK_MIN_RISK_REWARD,
        "min_entry_confidence": settings.RISK_MIN_ENTRY_CONFIDENCE,
        "effective_daily_loss_limit_usd": round(get_effective_daily_loss_limit(equity_usd), 2),
        "time_stop_hours": settings.RISK_TIME_STOP_HOURS,
        "stop_cooldown_minutes": settings.RISK_STOP_COOLDOWN_MINUTES,
        "max_scale_in_count": settings.RISK_MAX_SCALE_IN_COUNT,
        "min_scale_in_profit_ratio": settings.RISK_MIN_SCALE_IN_PROFIT_RATIO
    }

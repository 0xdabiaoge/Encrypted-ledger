"""
Encrypted Ledger - Risk Supervisor & Active Position Sentinel
Monitors live positions for Break-even profit protection, Time-stop expiration, and daily loss circuit breaker.
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.risk.constants import get_effective_daily_loss_limit


class RiskSupervisor:
    """Supervises active trades and enforces mechanical lifecycle rules."""

    @staticmethod
    def evaluate_trailing_breakeven(
        entry_price: float,
        current_price: float,
        side: str,
        initial_sl_price: float,
        atr: float
    ) -> Optional[float]:
        """
        If trade reaches +1.5R profit, move Stop-Loss to Breakeven (Entry Price + 0.1x ATR buffer).
        Returns new stop loss price if eligible, else None.
        """
        is_long = (side.lower() == "long")
        if is_long:
            risk = entry_price - initial_sl_price
            if risk <= 0:
                return None
            profit = current_price - entry_price
            if profit >= 1.5 * risk:
                new_sl = entry_price + 0.1 * atr
                if new_sl > initial_sl_price:
                    return round(new_sl, 4)
        else:
            risk = initial_sl_price - entry_price
            if risk <= 0:
                return None
            profit = entry_price - current_price
            if profit >= 1.5 * risk:
                new_sl = entry_price - 0.1 * atr
                if new_sl < initial_sl_price:
                    return round(new_sl, 4)
        return None

    @staticmethod
    def evaluate_time_stop(
        open_time_ms: int,
        entry_price: float,
        current_price: float,
        atr: float
    ) -> Tuple[bool, str]:
        """
        Time stop: if position held > RISK_TIME_STOP_HOURS (default 8h) and price
        has moved less than 0.15 * ATR, close to free up capital from choppy dead time.
        """
        elapsed_hours = (time.time() * 1000 - open_time_ms) / (1000 * 3600)
        if elapsed_hours >= settings.RISK_TIME_STOP_HOURS:
            price_delta = abs(current_price - entry_price)
            dead_band = settings.RISK_TIME_STOP_ATR_BAND * atr
            if price_delta < dead_band:
                return True, f"持仓已达 {elapsed_hours:.1f} 小时，波动幅度 ({price_delta:.2f}) 未突破横盘带宽 ({dead_band:.2f})，触发时间止损平仓"
        return False, ""

    @staticmethod
    def check_daily_drawdown_limit(daily_realized_pnl_usd: float, total_equity_usd: float) -> Tuple[bool, str]:
        """
        Daily loss circuit breaker check.
        """
        limit = get_effective_daily_loss_limit(total_equity_usd)
        if daily_realized_pnl_usd <= -limit:
            return True, f"今日累计已实现亏损 (-{abs(daily_realized_pnl_usd):.2f}U) 已达到或超过单日熔断线 (-{limit:.2f}U)，今日禁止新开仓"
        return False, ""


risk_supervisor = RiskSupervisor()

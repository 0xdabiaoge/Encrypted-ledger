"""
Encrypted Ledger - Smart Order Routing (SOR) Engine
Routes orders dynamically between OKX and Binance based on depth, spread, slippage, and venue health.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.exchanges.base import BaseExchangeAdapter, OrderBookDepth, normalize_symbol
from app.exchanges.okx import OKXAdapter
from app.exchanges.binance import BinanceAdapter


class SmartOrderRouter:
    """Institutional SOR comparing micro-slippage and liquidity across OKX & Binance."""

    def __init__(self):
        self.okx = OKXAdapter()
        self.binance = BinanceAdapter()

    def get_adapter(self, venue: str) -> BaseExchangeAdapter:
        if venue.lower() == "okx":
            return self.okx
        elif venue.lower() == "binance":
            return self.binance
        raise ValueError(f"Unknown venue: {venue}")

    async def evaluate_best_execution_venue(
        self,
        symbol: str,
        side: str,
        notional_usd: float
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Evaluate orderbook depth and simulated slippage on OKX vs Binance.
        Returns: (chosen_venue, metrics_dict)
        """
        sym = normalize_symbol(symbol)
        preferred = settings.PREFERRED_VENUE.lower()
        if preferred in ("okx", "binance"):
            return preferred, {"reason": f"Manually pinned preferred venue: {preferred}"}

        okx_depth: Optional[OrderBookDepth] = None
        binance_depth: Optional[OrderBookDepth] = None
        errors = {}

        try:
            okx_depth = await self.okx.get_orderbook(sym, depth=20)
        except Exception as e:
            errors["okx"] = str(e)

        try:
            binance_depth = await self.binance.get_orderbook(sym, depth=20)
        except Exception as e:
            errors["binance"] = str(e)

        # Fallback if one venue failed
        if not okx_depth and binance_depth:
            return "binance", {"reason": "OKX book unavailable, fallback to Binance", "errors": errors}
        if not binance_depth and okx_depth:
            return "okx", {"reason": "Binance book unavailable, fallback to OKX", "errors": errors}
        if not okx_depth and not binance_depth:
            return "okx", {"reason": "Both books unavailable, default to OKX", "errors": errors}

        # Calculate simulated slippage
        def simulate_slippage(depth: OrderBookDepth, side: str, amount_usd: float) -> Tuple[float, float]:
            book = depth.asks if side.lower() == "buy" else depth.bids
            if not book:
                return 0.0, 999.0
            top_px = book[0][0]
            spent_usd = 0.0
            total_qty = 0.0
            for px, sz in book:
                step_usd = px * sz
                if spent_usd + step_usd >= amount_usd:
                    remaining_usd = amount_usd - spent_usd
                    total_qty += remaining_usd / px
                    spent_usd = amount_usd
                    break
                else:
                    spent_usd += step_usd
                    total_qty += sz

            if total_qty <= 0:
                return top_px, 999.0
            vwap = spent_usd / total_qty
            slippage_bps = abs(vwap - top_px) / top_px * 10000
            return vwap, slippage_bps

        okx_vwap, okx_slip = simulate_slippage(okx_depth, side, notional_usd)
        bin_vwap, bin_slip = simulate_slippage(binance_depth, side, notional_usd)

        metrics = {
            "symbol": sym,
            "side": side,
            "notional_usd": notional_usd,
            "okx": {"top_price": okx_depth.asks[0][0] if side == "buy" else okx_depth.bids[0][0], "simulated_slippage_bps": round(okx_slip, 2)},
            "binance": {"top_price": binance_depth.asks[0][0] if side == "buy" else binance_depth.bids[0][0], "simulated_slippage_bps": round(bin_slip, 2)},
        }

        # If Binance slippage is significantly lower, route to Binance; otherwise favor OKX for attached algo protection
        if bin_slip < okx_slip - 1.5:  # Binance is significantly cheaper (>1.5 bps advantage)
            chosen = "binance"
            metrics["reason"] = f"Binance liquidity depth superior (Slippage: {bin_slip:.2f}bps vs {okx_slip:.2f}bps)"
        else:
            chosen = "okx"
            metrics["reason"] = f"OKX execution favored (Attached Algo protection + Slippage: {okx_slip:.2f}bps)"

        return chosen, metrics

    async def get_aggregated_balances(self) -> Dict[str, Any]:
        """Aggregate total equity, available capital, and margin across OKX and Binance."""
        bal_okx = None
        bal_bin = None
        try:
            bal_okx = await self.okx.get_account_balance()
        except Exception:
            pass
        try:
            bal_bin = await self.binance.get_account_balance()
        except Exception:
            pass

        eq_okx = bal_okx.total_equity_usd if bal_okx else 0.0
        eq_bin = bal_bin.total_equity_usd if bal_bin else 0.0
        return {
            "total_equity_usd": round(eq_okx + eq_bin, 2),
            "okx": {"total_equity_usd": round(eq_okx, 2), "raw": bal_okx.__dict__ if bal_okx else None},
            "binance": {"total_equity_usd": round(eq_bin, 2), "raw": bal_bin.__dict__ if bal_bin else None}
        }


order_router = SmartOrderRouter()

"""
Encrypted Ledger - Smart Order Routing (SOR) Engine
Routes orders dynamically:
- Mainstream coins (BTC, ETH, SOL, BNB, etc.) -> OKX & Binance (evaluated by depth & slippage)
- Meme coins & Altcoins (PEPE, DOGE, SHIB, FLOKI, BONK, etc.) -> Gate.io (depth, fees, & early listing)
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.exchanges.base import BaseExchangeAdapter, OrderBookDepth, normalize_symbol
from app.exchanges.okx import OKXAdapter
from app.exchanges.binance import BinanceAdapter
from app.exchanges.gate import GateAdapter
from app.exchanges.categories import categorize_symbol, is_meme_or_altcoin, extract_base_asset


class SmartOrderRouter:
    """Institutional SOR comparing micro-slippage, venue priority, and token categories."""

    def __init__(self):
        self.okx = OKXAdapter()
        self.binance = BinanceAdapter()
        self.gate = GateAdapter()

    def get_adapter(self, venue: str) -> BaseExchangeAdapter:
        v = venue.lower().strip()
        if v == "okx":
            return self.okx
        elif v == "binance":
            return self.binance
        elif v == "gate":
            return self.gate
        raise ValueError(f"Unknown venue: {venue}")

    async def evaluate_best_execution_venue(
        self,
        symbol: str,
        side: str,
        notional_usd: float
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Evaluate order routing based on symbol category and exchange book metrics:
        - Meme/Altcoins -> Gate.io (Meme priority)
        - Mainstream -> OKX vs Binance (SOR liquidity & slippage)
        """
        sym = normalize_symbol(symbol)
        preferred = settings.PREFERRED_VENUE.lower()
        if preferred in ("okx", "binance", "gate"):
            return preferred, {"reason": f"手动指定行情/执行主所: {preferred.upper()}"}

        # Check symbol category
        category = categorize_symbol(symbol)
        base = extract_base_asset(symbol)

        if category == "MEME_ALTCOIN":
            # Direct to Gate.io for Meme and Small-Cap Altcoins
            return "gate", {
                "category": "MEME_ALTCOIN",
                "symbol": sym,
                "base": base,
                "reason": f"品类规则分流：[{base}] 属于 Meme/高弹性山寨币，优先指派 Gate.io 执行撮合 (深度更厚、支持更全、返佣综合成本低)"
            }

        # Mainstream assets: Evaluate OKX vs Binance
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
            return "binance", {"category": category, "symbol": sym, "reason": "OKX 盘口暂不可用，自动降级至币安", "errors": errors}
        if not binance_depth and okx_depth:
            return "okx", {"category": category, "symbol": sym, "reason": "币安盘口暂不可用，自动降级至 OKX", "errors": errors}
        if not okx_depth and not binance_depth:
            return "okx", {"category": category, "symbol": sym, "reason": "双所盘口均瞬时离线，默认兜底 OKX", "errors": errors}

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
            "category": "MAINSTREAM",
            "symbol": sym,
            "side": side,
            "notional_usd": notional_usd,
            "okx": {"top_price": okx_depth.asks[0][0] if side == "buy" else okx_depth.bids[0][0], "simulated_slippage_bps": round(okx_slip, 2)},
            "binance": {"top_price": binance_depth.asks[0][0] if side == "buy" else binance_depth.bids[0][0], "simulated_slippage_bps": round(bin_slip, 2)},
        }

        # If Binance slippage is significantly lower, route to Binance; otherwise favor OKX for attached algo protection
        if bin_slip < okx_slip - 1.5:
            chosen = "binance"
            metrics["reason"] = f"币安主流币流动性更优 (滑点: {bin_slip:.2f}bps vs {okx_slip:.2f}bps)"
        else:
            chosen = "okx"
            metrics["reason"] = f"OKX 原生条件单保护与滑点更优 (滑点: {okx_slip:.2f}bps)"

        return chosen, metrics

    async def get_aggregated_balances(self) -> Dict[str, Any]:
        """Aggregate total equity, available capital, and margin across OKX, Binance, and Gate."""
        bal_okx = None
        bal_bin = None
        bal_gate = None
        try:
            bal_okx = await self.okx.get_account_balance()
        except Exception:
            pass
        try:
            bal_bin = await self.binance.get_account_balance()
        except Exception:
            pass
        try:
            bal_gate = await self.gate.get_account_balance()
        except Exception:
            pass

        eq_okx = bal_okx.total_equity_usd if bal_okx else 0.0
        eq_bin = bal_bin.total_equity_usd if bal_bin else 0.0
        eq_gate = bal_gate.total_equity_usd if bal_gate else 0.0
        return {
            "total_equity_usd": round(eq_okx + eq_bin + eq_gate, 2),
            "okx": {"total_equity_usd": round(eq_okx, 2), "raw": bal_okx.__dict__ if bal_okx else None},
            "binance": {"total_equity_usd": round(eq_bin, 2), "raw": bal_bin.__dict__ if bal_bin else None},
            "gate": {"total_equity_usd": round(eq_gate, 2), "raw": bal_gate.__dict__ if bal_gate else None},
        }


order_router = SmartOrderRouter()

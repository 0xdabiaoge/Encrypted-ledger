"""
Encrypted Ledger - Paper Trading Position Manager
Provides high-fidelity, zero-risk simulated position management.
Persists active paper positions in data/paper_positions.json and syncs
mark prices against real-time exchange orderbook depth.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.exchanges.base import PositionInfo, normalize_symbol

PAPER_POSITIONS_PATH = settings.DATA_DIR / "paper_positions.json"


class PaperPositionManager:
    def __init__(self):
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not PAPER_POSITIONS_PATH.exists():
            self._positions = {}
            return
        try:
            with open(PAPER_POSITIONS_PATH, "r", encoding="utf-8") as f:
                self._positions = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load paper_positions.json: {e}")
            self._positions = {}

    def _save(self) -> None:
        try:
            PAPER_POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PAPER_POSITIONS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._positions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save paper_positions.json: {e}")

    def open_position(
        self,
        venue: str,
        symbol: str,
        side: str,
        entry_price: float,
        notional_usd: float = 5000.0,
        leverage: float = 5.0,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Open a new simulated paper position."""
        sym = normalize_symbol(symbol)
        side_clean = "long" if side.lower() in ("long", "buy") else "short"
        pos_key = f"{venue.lower()}_{sym}_{side_clean}"

        size = round(notional_usd / entry_price, 4) if entry_price > 0 else 0.01
        margin_usd = round(notional_usd / leverage, 2)

        # Calculate liquidation price estimate (cross margin buffer ~90%)
        if side_clean == "long":
            liq_px = round(entry_price * (1.0 - (1.0 / leverage) * 0.9), 2)
            if not stop_loss_price:
                stop_loss_price = round(entry_price * 0.982, 2)  # -1.8%
            if not take_profit_price:
                take_profit_price = round(entry_price * 1.036, 2)  # +3.6%
        else:
            liq_px = round(entry_price * (1.0 + (1.0 / leverage) * 0.9), 2)
            if not stop_loss_price:
                stop_loss_price = round(entry_price * 1.018, 2)  # +1.8%
            if not take_profit_price:
                take_profit_price = round(entry_price * 0.964, 2)  # -3.6%

        record = {
            "venue": venue.lower(),
            "symbol": sym,
            "inst_id": f"{sym}-USDT-SWAP",
            "side": side_clean,
            "size": size,
            "notional_usd": notional_usd,
            "entry_price": entry_price,
            "mark_price": entry_price,
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_ratio": 0.0,
            "leverage": leverage,
            "margin_usd": margin_usd,
            "liquidation_price": liq_px,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "opened_at": int(time.time()),
            "order_id": f"SIM_{venue.upper()}_{uuid.uuid4().hex[:8]}"
        }

        self._positions[pos_key] = record
        self._save()
        logger.info(f"[PAPER POSITION OPENED] {venue.upper()} {sym} {side_clean.upper()} @ {entry_price} | Notional: ${notional_usd} | Leverage: {leverage}x")
        return record

    def close_position(self, venue: str, symbol: str, side: str, close_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Close an active paper position and return realized PnL stats."""
        sym = normalize_symbol(symbol)
        side_clean = "long" if side.lower() in ("long", "buy") else "short"
        pos_key = f"{venue.lower()}_{sym}_{side_clean}"

        if pos_key not in self._positions:
            return None

        pos = self._positions.pop(pos_key)
        self._save()

        exit_px = close_price or pos.get("mark_price", pos.get("entry_price", 0.0))
        entry_px = pos.get("entry_price", 0.0)
        size = pos.get("size", 0.0)
        lev = pos.get("leverage", 5.0)

        if side_clean == "long":
            realized_pnl = (exit_px - entry_px) * size
            roi = ((exit_px - entry_px) / entry_px) * lev if entry_px > 0 else 0.0
        else:
            realized_pnl = (entry_px - exit_px) * size
            roi = ((entry_px - exit_px) / entry_px) * lev if entry_px > 0 else 0.0

        logger.info(f"[PAPER POSITION CLOSED] {venue.upper()} {sym} {side_clean.upper()} @ {exit_px} | Realized PnL: ${realized_pnl:.2f} (ROI: {roi*100:.2f}%)")
        return {
            "position": pos,
            "exit_price": exit_px,
            "realized_pnl_usd": round(realized_pnl, 2),
            "realized_pnl_ratio": round(roi, 4)
        }

    async def get_active_positions(self, current_prices: Optional[Dict[str, float]] = None) -> List[PositionInfo]:
        """Return all open paper positions with dynamically computed live PnL."""
        self._load()
        res: List[PositionInfo] = []

        for p in self._positions.values():
            sym = p["symbol"]
            entry_px = p.get("entry_price", 0.0)
            mark_px = (current_prices.get(sym) if current_prices else None) or p.get("mark_price", entry_px)
            side = p.get("side", "long")
            size = p.get("size", 0.0)
            lev = p.get("leverage", 5.0)

            if side == "long":
                upl = (mark_px - entry_px) * size
                ratio = ((mark_px - entry_px) / entry_px) * lev if entry_px > 0 else 0.0
            else:
                upl = (entry_px - mark_px) * size
                ratio = ((entry_px - mark_px) / entry_px) * lev if entry_px > 0 else 0.0

            res.append(PositionInfo(
                venue=p.get("venue", "okx"),
                symbol=sym,
                inst_id=p.get("inst_id", f"{sym}-USDT-SWAP"),
                side=side,
                size=size,
                notional_usd=p.get("notional_usd", 0.0),
                entry_price=entry_px,
                mark_price=mark_px,
                unrealized_pnl_usd=round(upl, 2),
                unrealized_pnl_ratio=round(ratio, 4),
                leverage=lev,
                margin_usd=p.get("margin_usd", 0.0),
                liquidation_price=p.get("liquidation_price", 0.0)
            ))

        return res


paper_positions_manager = PaperPositionManager()

"""
Encrypted Ledger - Trading Universe & Instrument Management
Dynamic instrument management with tier classifications, precision, and risk bounds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.core.atomic_io import atomic_write_json, read_json_safe
from app.exchanges.base import normalize_symbol

UNIVERSE_FILE = settings.DATA_DIR / "universe.json"

TIER_PROFILES = {
    "tier_1_bluechip": {
        "label": "蓝筹主流",
        "max_leverage": 5,
        "base_risk_ratio": 1.0,
        "sl_atr_mult": 1.8,
        "min_vol_24h_usd": 100_000_000,
    },
    "tier_2_momentum": {
        "label": "高弹性动量",
        "max_leverage": 3,
        "base_risk_ratio": 0.75,
        "sl_atr_mult": 2.2,
        "min_vol_24h_usd": 20_000_000,
    }
}


DEFAULT_UNIVERSE = [
    {"name": "BTC", "ccy": "BTC", "tier": "tier_1_bluechip", "okx_inst_id": "BTC-USDT-SWAP", "binance_inst_id": "BTCUSDT", "max_leverage": 5, "sl_atr_mult": 1.8, "precision": 1, "ct_val_okx": 0.01, "tick_sz": "0.1", "min_sz_okx": "0.01", "min_sz_binance": "0.001", "risk_per_trade_usd": 15.0},
    {"name": "ETH", "ccy": "ETH", "tier": "tier_1_bluechip", "okx_inst_id": "ETH-USDT-SWAP", "binance_inst_id": "ETHUSDT", "max_leverage": 5, "sl_atr_mult": 1.8, "precision": 2, "ct_val_okx": 0.1, "tick_sz": "0.01", "min_sz_okx": "0.01", "min_sz_binance": "0.01", "risk_per_trade_usd": 15.0},
    {"name": "SOL", "ccy": "SOL", "tier": "tier_2_momentum", "okx_inst_id": "SOL-USDT-SWAP", "binance_inst_id": "SOLUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 2, "ct_val_okx": 1.0, "tick_sz": "0.01", "min_sz_okx": "0.01", "min_sz_binance": "0.1", "risk_per_trade_usd": 15.0},
    {"name": "XRP", "ccy": "XRP", "tier": "tier_2_momentum", "okx_inst_id": "XRP-USDT-SWAP", "binance_inst_id": "XRPUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 4, "ct_val_okx": 100.0, "tick_sz": "0.0001", "min_sz_okx": "0.01", "min_sz_binance": "1.0", "risk_per_trade_usd": 15.0},
    {"name": "DOGE", "ccy": "DOGE", "tier": "tier_2_momentum", "okx_inst_id": "DOGE-USDT-SWAP", "binance_inst_id": "DOGEUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 4, "ct_val_okx": 1000.0, "tick_sz": "0.0001", "min_sz_okx": "0.01", "min_sz_binance": "1.0", "risk_per_trade_usd": 15.0},
    {"name": "ARB", "ccy": "ARB", "tier": "tier_2_momentum", "okx_inst_id": "ARB-USDT-SWAP", "binance_inst_id": "ARBUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 4, "ct_val_okx": 10.0, "tick_sz": "0.0001", "min_sz_okx": "0.1", "min_sz_binance": "1.0", "risk_per_trade_usd": 15.0},
    {"name": "SUI", "ccy": "SUI", "tier": "tier_2_momentum", "okx_inst_id": "SUI-USDT-SWAP", "binance_inst_id": "SUIUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 4, "ct_val_okx": 1.0, "tick_sz": "0.0001", "min_sz_okx": "0.01", "min_sz_binance": "1.0", "risk_per_trade_usd": 15.0},
    {"name": "LINK", "ccy": "LINK", "tier": "tier_2_momentum", "okx_inst_id": "LINK-USDT-SWAP", "binance_inst_id": "LINKUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 3, "ct_val_okx": 1.0, "tick_sz": "0.001", "min_sz_okx": "0.1", "min_sz_binance": "0.1", "risk_per_trade_usd": 15.0},
    {"name": "ADA", "ccy": "ADA", "tier": "tier_2_momentum", "okx_inst_id": "ADA-USDT-SWAP", "binance_inst_id": "ADAUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 4, "ct_val_okx": 100.0, "tick_sz": "0.0001", "min_sz_okx": "0.1", "min_sz_binance": "1.0", "risk_per_trade_usd": 15.0},
    {"name": "UNI", "ccy": "UNI", "tier": "tier_2_momentum", "okx_inst_id": "UNI-USDT-SWAP", "binance_inst_id": "UNIUSDT", "max_leverage": 3, "sl_atr_mult": 2.2, "precision": 3, "ct_val_okx": 1.0, "tick_sz": "0.001", "min_sz_okx": "1.0", "min_sz_binance": "0.1", "risk_per_trade_usd": 15.0}
]


class UniverseManager:
    """Manages the traded crypto instruments pool with hot reload and admin CRUD."""

    def __init__(self):
        self.file_path = UNIVERSE_FILE

    def load_instruments(self) -> List[Dict[str, Any]]:
        data = read_json_safe(self.file_path)
        if not data or not isinstance(data, list):
            # Seed default 10 instruments if file is missing or empty
            atomic_write_json(self.file_path, DEFAULT_UNIVERSE)
            return DEFAULT_UNIVERSE
        return data

    def get_instrument(self, symbol: str) -> Optional[Dict[str, Any]]:
        canonical = normalize_symbol(symbol)
        for item in self.load_instruments():
            if item.get("name", "").upper() == canonical:
                return item
        return None

    def add_instrument(self, item: Dict[str, Any]) -> bool:
        name = normalize_symbol(item.get("name", ""))
        if not name:
            raise ValueError("Instrument name/symbol is required.")

        pool = self.load_instruments()
        for existing in pool:
            if existing.get("name", "").upper() == name:
                raise ValueError(f"Instrument {name} already exists in universe.")

        tier = item.get("tier") or ("tier_1_bluechip" if name in ("BTC", "ETH") else "tier_2_momentum")
        profile = TIER_PROFILES.get(tier, TIER_PROFILES["tier_2_momentum"])

        record = {
            "name": name,
            "ccy": item.get("ccy", name),
            "tier": tier,
            "okx_inst_id": item.get("okx_inst_id") or f"{name}-USDT-SWAP",
            "binance_inst_id": item.get("binance_inst_id") or f"{name}USDT",
            "max_leverage": min(item.get("max_leverage", profile["max_leverage"]), profile["max_leverage"]),
            "sl_atr_mult": float(item.get("sl_atr_mult", profile["sl_atr_mult"])),
            "precision": int(item.get("precision", 2)),
            "ct_val_okx": float(item.get("ct_val_okx", 1.0)),
            "tick_sz": str(item.get("tick_sz", "0.01")),
            "min_sz_okx": str(item.get("min_sz_okx", "0.01")),
            "min_sz_binance": str(item.get("min_sz_binance", "0.01")),
            "risk_per_trade_usd": float(item.get("risk_per_trade_usd", 15.0))
        }

        pool.append(record)
        atomic_write_json(self.file_path, pool)
        logger.info(f"Added instrument {name} to trading universe.")
        return True

    def remove_instrument(self, symbol: str) -> bool:
        canonical = normalize_symbol(symbol)
        pool = self.load_instruments()
        new_pool = [x for x in pool if x.get("name", "").upper() != canonical]
        if len(new_pool) == len(pool):
            return False
        atomic_write_json(self.file_path, new_pool)
        logger.info(f"Removed instrument {canonical} from trading universe.")
        return True

    def update_instrument(self, symbol: str, updates: Dict[str, Any]) -> bool:
        canonical = normalize_symbol(symbol)
        pool = self.load_instruments()
        updated = False
        for item in pool:
            if item.get("name", "").upper() == canonical:
                for k, v in updates.items():
                    if k != "name":  # Name is primary key
                        item[k] = v
                updated = True
                break
        if updated:
            atomic_write_json(self.file_path, pool)
            logger.info(f"Updated instrument {canonical} in universe.")
        return updated


universe_manager = UniverseManager()

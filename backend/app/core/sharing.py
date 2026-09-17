"""
Encrypted Ledger - Position Sharing Manager
Enables traders/members to generate public share cards and dedicated showcase pages
with strict data masking (zero account balance or sensitive credential leakage).
"""
from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.atomic_io import atomic_write_json

SHARES_FILE = settings.DATA_DIR / "shared_positions.json"


class PositionShareManager:
    def __init__(self, storage_path: Path = SHARES_FILE):
        self.storage_path = storage_path
        self._shares: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.storage_path.exists():
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self) -> None:
        atomic_write_json(self.storage_path, self._shares)

    def create_share(
        self,
        username: str,
        symbol: str,
        side: str,
        leverage: str = "5.0x",
        entry_price: float = 0.0,
        mark_price: float = 0.0,
        unrealized_pnl_ratio: float = 0.0,
        venue: str = "okx",
        council_insight: str = "",
        custom_alias: Optional[str] = None
    ) -> Dict[str, Any]:
        share_id = f"EL-SH{secrets.token_hex(4).upper()}"
        
        # Mask username for public viewing: e.g. vip_trader_1234 -> vip***34
        if custom_alias and custom_alias.strip():
            trader_alias = custom_alias.strip()[:20]
        elif len(username) > 4:
            trader_alias = f"{username[:3]}***{username[-2:]}"
        else:
            trader_alias = f"{username}***"

        ratio = float(unrealized_pnl_ratio)
        roi_pct = f"{'+' if ratio >= 0 else ''}{round(ratio * 100, 2)}%"
        
        status_label = "保本锁利中" if ratio >= 0.015 else ("盈利奔跑中" if ratio > 0 else "严格风控防守中")

        default_insight = (
            council_insight if council_insight else 
            "顺应 4H 宏观大势通道，微积分加速度与盘口失衡度共振触发，经 4+1 投委会 CIO 终审裁决执行。"
        )

        record = {
            "share_id": share_id,
            "creator_user": username,
            "trader_alias": trader_alias,
            "symbol": symbol.upper(),
            "venue": venue.upper(),
            "side": side.upper(),
            "leverage": leverage if "x" in leverage.lower() else f"{leverage}x",
            "entry_price": round(float(entry_price), 4),
            "mark_price": round(float(mark_price), 4),
            "unrealized_pnl_ratio": round(ratio, 4),
            "roi_pct": roi_pct,
            "status": status_label,
            "council_insight": default_insight,
            "created_at_iso": datetime.now(timezone.utc).isoformat(),
            "created_at_formatted": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "is_masked": True
        }

        self._shares[share_id] = record
        self._save()
        return record

    def get_share(self, share_id: str) -> Optional[Dict[str, Any]]:
        return self._shares.get(share_id)

    def list_shares(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        shares = list(self._shares.values())
        if username:
            shares = [s for s in shares if s.get("creator_user") == username]
        return sorted(shares, key=lambda x: x.get("created_at_iso", ""), reverse=True)


position_share_manager = PositionShareManager()

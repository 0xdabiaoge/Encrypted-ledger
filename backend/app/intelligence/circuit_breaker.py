"""
Encrypted Ledger - Black-Swan Circuit Breaker Sentinel
Monitors real-time macro headlines for existential market risks and triggers automated trading freezes.
"""
from __future__ import annotations

import datetime
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.core.atomic_io import atomic_write_json, read_json_safe

CIRCUIT_BREAKER_FILE = settings.DATA_DIR / "circuit_breaker.json"

# Institutional-grade regex patterns for catastrophic systemic events
BLACK_SWAN_PATTERNS: List[Tuple[str, str, int]] = [
    (r"(USDT|USDC|DAI|FDUSD).*(严重脱锚|脱锚幅度|depeg|跌破0\.9[0-8]|脱锚超过)", "头部稳定币恶性脱锚危机", 3),
    (r"(币安|OKX|Coinbase|Kraken).*(暂停全部提现|停止提币|申请破产|破产倒闭|发生严重挤兑)", "顶级中心化交易所崩盘挤兑", 3),
    (r"(以太坊主网|比特币网络|Solana网络|BNB Chain).*(遭遇51%攻击|全网瘫痪停机|紧急硬分叉回滚)", "底层公链系统性停机/攻击", 3),
    (r"(全面取缔所有加密|宣布比特币非法|宣布数字货币交易非法|爆发核危机|宣战)", "国家级极端不可抗力/战争", 3),
    (r"(美联储紧急降息|美联储紧急加息|非农暴跌|CPI严重超预期)", "宏观突发利率冲击", 2),
]


class CircuitBreakerSentinel:
    """Manages circuit breaker state and multi-tier defensive actions."""

    def __init__(self):
        self.file_path = CIRCUIT_BREAKER_FILE

    def get_state(self) -> Dict[str, Any]:
        data = read_json_safe(self.file_path, default={})
        if not data:
            return {"active": False, "level": 0, "expires_at_ts": 0}
        
        now = time.time()
        if data.get("active") and now < data.get("expires_at_ts", 0):
            return data
        return {"active": False, "level": 0, "expires_at_ts": 0}

    def is_active(self) -> Tuple[bool, Dict[str, Any]]:
        state = self.get_state()
        return state.get("active", False), state

    def trigger(self, headline: str, keyword: str, level: int = 2) -> Dict[str, Any]:
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
        now_bj = datetime.datetime.now(tz_bj)
        now_ts = int(time.time())
        freeze_sec = settings.CIRCUIT_BREAKER_FREEZE_SECONDS if level >= 2 else 600

        action_desc = (
            "紧急红色熔断：冻结全部新开仓，存量微亏单平仓，盈利单保本平移" if level == 3
            else "橙色防御熔断：冻结新开仓 30 分钟，禁止金字塔加仓"
        )

        state = {
            "active": True,
            "level": level,
            "triggered_at": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at_ts": now_ts + freeze_sec,
            "headline": headline,
            "keyword": keyword,
            "action": action_desc
        }
        atomic_write_json(self.file_path, state)
        logger.critical(f"🚨 [CIRCUIT BREAKER ACTIVATED - Level {level}] {keyword} | {headline}")
        return state

    def trigger_circuit_breaker(self, reason: str, details: str = "", level: int = 3) -> Dict[str, Any]:
        """Structured emergency panic trigger."""
        return self.trigger(headline=details or reason, keyword=reason, level=level)

    def check_headline(self, headline: str, summary: str = "") -> Optional[Dict[str, Any]]:
        full_text = f"{headline} {summary}"
        for pattern, threat_name, level in BLACK_SWAN_PATTERNS:
            if re.search(pattern, full_text, re.IGNORECASE):
                return self.trigger(headline, threat_name, level=level)
        return None

    def manual_reset(self) -> None:
        state = {"active": False, "level": 0, "expires_at_ts": 0, "headline": "", "keyword": "", "action": "手动复位"}
        atomic_write_json(self.file_path, state)
        logger.info("Circuit breaker sentinel manually reset to normal.")


circuit_breaker = CircuitBreakerSentinel()

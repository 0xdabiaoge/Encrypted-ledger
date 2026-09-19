"""
Encrypted Ledger - User Persistent Auto-Patrol Scheduling Manager
Allows multi-user isolated auto-patrol scheduling (24h / 48h / 72h / Permanent).
Persists active patrol sessions to data/user_patrol_sessions.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger

PATROL_STORE_PATH = settings.DATA_DIR / "user_patrol_sessions.json"

DURATION_SECONDS_MAP = {
    "24h": 24 * 3600,
    "48h": 48 * 3600,
    "72h": 72 * 3600,
    "permanent": None,
}


class UserPatrolManager:
    """Manages persistent auto-patrol schedules isolated per user."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load persisted patrol sessions from disk."""
        if not PATROL_STORE_PATH.exists():
            return
        try:
            with open(PATROL_STORE_PATH, "r", encoding="utf-8") as f:
                self._sessions = json.load(f)
            logger.info(f"Loaded {len(self._sessions)} user patrol sessions from disk.")
        except Exception as e:
            logger.warning(f"Failed to load user patrol sessions: {e}")
            self._sessions = {}

    def _save_sessions(self) -> None:
        """Save sessions persistently to disk."""
        try:
            PATROL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PATROL_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save user patrol sessions: {e}")

    def start_patrol(self, username: str, duration: str = "24h", role: str = "user") -> Dict[str, Any]:
        """
        Start or update an auto-patrol schedule for a specific user.
        Durations: '24h', '48h', '72h', 'permanent'.
        """
        dur_key = duration.lower().strip()
        if dur_key not in DURATION_SECONDS_MAP:
            dur_key = "24h"

        now = time.time()
        sec_offset = DURATION_SECONDS_MAP[dur_key]
        expires_at = (now + sec_offset) if sec_offset is not None else None

        existing = self._sessions.get(username, {})
        total_cycles = existing.get("total_cycles", 0)

        session = {
            "username": username,
            "role": role,
            "status": "running",
            "duration": dur_key,
            "started_at": now,
            "expires_at": expires_at,
            "last_run_at": existing.get("last_run_at", 0),
            "total_cycles": total_cycles,
            "updated_at": now,
        }

        self._sessions[username] = session
        self._save_sessions()
        logger.info(f"User [{username}] started auto-patrol: duration={dur_key}, expires_at={expires_at}")
        return self.get_patrol_status(username)

    def stop_patrol(self, username: str) -> Dict[str, Any]:
        """Stop/pause the active patrol schedule for a specific user."""
        if username in self._sessions:
            self._sessions[username]["status"] = "stopped"
            self._sessions[username]["updated_at"] = time.time()
            self._save_sessions()
            logger.info(f"User [{username}] stopped auto-patrol.")
        return self.get_patrol_status(username)

    def get_patrol_status(self, username: str) -> Dict[str, Any]:
        """Get the current patrol status and remaining seconds for a specific user."""
        session = self._sessions.get(username)
        if not session:
            return {
                "username": username,
                "status": "idle",
                "duration": "24h",
                "is_active": False,
                "remaining_seconds": 0,
                "started_at": None,
                "expires_at": None,
                "total_cycles": 0,
                "last_run_at": 0,
            }

        now = time.time()
        expires_at = session.get("expires_at")
        status = session.get("status", "idle")

        # Check expiration
        if status == "running" and expires_at is not None:
            if now >= expires_at:
                session["status"] = "expired"
                session["updated_at"] = now
                self._save_sessions()
                status = "expired"

        is_active = (status == "running")
        if expires_at is not None:
            remaining = max(0, int(expires_at - now)) if is_active else 0
        else:
            remaining = -1  # -1 represents permanent / infinite

        return {
            "username": username,
            "status": session.get("status"),
            "duration": session.get("duration", "24h"),
            "is_active": is_active,
            "remaining_seconds": remaining,
            "started_at": session.get("started_at"),
            "expires_at": expires_at,
            "total_cycles": session.get("total_cycles", 0),
            "last_run_at": session.get("last_run_at", 0),
        }

    def has_any_active_patrol(self) -> bool:
        """Check if at least one user has an active patrol running."""
        now = time.time()
        for u, s in list(self._sessions.items()):
            if s.get("status") == "running":
                exp = s.get("expires_at")
                if exp is not None and now >= exp:
                    s["status"] = "expired"
                    self._save_sessions()
                else:
                    return True
        return False

    def record_cycle_run(self) -> None:
        """Record that a trade cycle was executed across all active sessions."""
        now = time.time()
        updated = False
        for u, s in self._sessions.items():
            if s.get("status") == "running":
                s["total_cycles"] = s.get("total_cycles", 0) + 1
                s["last_run_at"] = now
                updated = True
        if updated:
            self._save_sessions()


user_patrol_manager = UserPatrolManager()

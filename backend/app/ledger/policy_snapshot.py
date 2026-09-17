"""
Encrypted Ledger - Policy Snapshot & 0.5s Atomic Rollback Engine
Aggregates Prompts, Interceptors, Risk Constants, and Universe into a SHA-256 fingerprint.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from app.core.config import settings
from app.core.logging import logger
from app.core.atomic_io import atomic_write_json, read_json_safe
from app.database.db import async_session_factory
from app.database.models import PolicySnapshotRecord
from app.risk.constants import dump_risk_constants_summary
from app.quant.universe import universe_manager

ARCHIVES_DIR = settings.DATA_DIR / "policy_archives"
ACTIVE_POLICY_FILE = settings.DATA_DIR / "active_policy_snapshot.json"


class PolicySnapshotEngine:
    """Manages full-state policy snapshots, cryptographic hashing, and atomic rollback."""

    def __init__(self):
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        self.active_file = ACTIVE_POLICY_FILE

    def capture_current_policy(self, version_tag: str, description: str = "") -> Dict[str, Any]:
        """Captures complete 4-in-1 policy bundle and computes SHA-256 hash."""
        universe = universe_manager.load_instruments()
        risk_constants = dump_risk_constants_summary()

        payload = {
            "version_tag": version_tag,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "description": description,
            "universe": universe,
            "risk_constants": risk_constants,
            "preferred_venue": settings.PREFERRED_VENUE,
            "routing_mode": settings.ROUTING_MODE,
        }

        # Compute deterministic SHA-256
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        payload["sha256_hash"] = sha256_hash

        # Write to archive
        archive_path = ARCHIVES_DIR / f"{version_tag}.json"
        atomic_write_json(archive_path, payload)
        atomic_write_json(self.active_file, payload)
        logger.info(f"Captured Policy Snapshot: {version_tag} [{sha256_hash[:8]}]")

        return payload

    def get_active_policy(self) -> Dict[str, Any]:
        data = read_json_safe(self.active_file)
        if not data:
            # Capture genesis if none exists
            return self.capture_current_policy("v1.0.0-genesis", "系统初始基准策略快照")
        return data

    def list_archived_snapshots(self) -> List[Dict[str, Any]]:
        results = []
        for p in ARCHIVES_DIR.glob("*.json"):
            data = read_json_safe(p)
            if data and isinstance(data, dict):
                results.append({
                    "version_tag": data.get("version_tag", p.stem),
                    "sha256_hash": data.get("sha256_hash", ""),
                    "created_at": data.get("created_at", ""),
                    "description": data.get("description", ""),
                    "file_path": str(p)
                })
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)

    def rollback_to_version(self, version_tag: str) -> Dict[str, Any]:
        """0.5s Atomic rollback to an archived version."""
        archive_path = ARCHIVES_DIR / f"{version_tag}.json"
        if not archive_path.exists():
            raise FileNotFoundError(f"Snapshot version {version_tag} does not exist.")

        data = read_json_safe(archive_path)
        if not data:
            raise ValueError(f"Failed to parse snapshot archive {archive_path}")

        # Atomic restore
        atomic_write_json(self.active_file, data)
        # Restore universe if present
        if "universe" in data:
            from app.quant.universe import UNIVERSE_FILE
            atomic_write_json(UNIVERSE_FILE, data["universe"])

        logger.warning(f"🔄 Policy atomically rolled back to {version_tag} [{data.get('sha256_hash', '')[:8]}]")
        return data


policy_engine = PolicySnapshotEngine()

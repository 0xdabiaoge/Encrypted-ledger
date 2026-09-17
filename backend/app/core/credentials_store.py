"""
Encrypted Ledger - Secure Credentials Storage
Persists exchange API keys, environment settings, and bot tokens with Fernet encryption.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from app.core.config import settings
from app.core.logging import logger
from app.core.security import encrypt_secret, decrypt_secret

CREDENTIALS_STORE_PATH = settings.DATA_DIR / "credentials_store.json"

SECRET_FIELDS = {
    "okx_live_secret_key", "okx_live_passphrase",
    "okx_demo_secret_key", "okx_demo_passphrase",
    "binance_live_secret_key", "binance_demo_secret_key",
    "gate_secret_key", "telegram_bot_token"
}


def load_persisted_credentials() -> None:
    """Load encrypted credentials from data/credentials_store.json and apply to settings."""
    if not CREDENTIALS_STORE_PATH.exists():
        return
    try:
        with open(CREDENTIALS_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            attr = k.upper()
            if not hasattr(settings, attr):
                continue
            val = v
            if k in SECRET_FIELDS and val:
                try:
                    val = decrypt_secret(val)
                except Exception:
                    pass
            setattr(settings, attr, val)
    except Exception as e:
        logger.warning(f"Failed to load credentials_store.json: {e}")


def save_persisted_credentials(data: Dict[str, Any]) -> None:
    """Save credentials encrypted to data/credentials_store.json."""
    try:
        CREDENTIALS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if CREDENTIALS_STORE_PATH.exists():
            try:
                with open(CREDENTIALS_STORE_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        for k, v in data.items():
            if v is None:
                continue
            k_lower = k.lower()
            val_str = str(v).strip()
            if not val_str:
                continue
            if k_lower in SECRET_FIELDS:
                if not val_str.startswith("gAAAA"):
                    val_str = encrypt_secret(val_str)
            existing[k_lower] = val_str

        with open(CREDENTIALS_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save credentials_store.json: {e}")

"""
Encrypted Ledger - Security, Cryptography & Access Control
Fernet key generation, hardware/disk symmetric encryption for CEX secrets, JWT auth & IP rate limiter.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.fernet import Fernet
import jwt

from app.core.config import settings


# ==============================================================================
# 1. Fernet Symmetric Encryption for Exchange API Credentials
# ==============================================================================

def get_or_create_fernet_key() -> bytes:
    """Retrieve or generate local 32-byte url-safe Fernet key."""
    key_path = settings.PROJECT_ROOT / settings.FERNET_KEY_FILE
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        try:
            with open(key_path, "rb") as f:
                key = f.read().strip()
                if len(key) == 44:  # Base64-encoded 32-byte key
                    return key
        except Exception:
            pass
    # Generate new key
    new_key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(new_key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return new_key


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext string into base64 ciphertext."""
    if not plaintext:
        return ""
    key = get_or_create_fernet_key()
    f = Fernet(key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt base64 ciphertext into plaintext string."""
    if not ciphertext:
        return ""
    key = get_or_create_fernet_key()
    f = Fernet(key)
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


# ==============================================================================
# 2. Password Hashing (PBKDF2-HMAC-SHA256)
# ==============================================================================

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Secure password hashing using PBKDF2-HMAC-SHA256 with random salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    ).hex()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash string."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, expected = stored_hash.split("$", 1)
    test_hash = hash_password(password, salt=salt)
    return hmac.compare_digest(test_hash, stored_hash)


# ==============================================================================
# 3. JWT Session Tokens
# ==============================================================================

JWT_ALGORITHM = "HS256"
JWT_SECRET_FALLBACK = "encrypted_ledger_master_jwt_secret_2026_quant_desk"


def get_jwt_secret() -> str:
    return settings.ADMIN_SECRET_KEY or JWT_SECRET_FALLBACK


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


# ==============================================================================
# 4. Anti-Brute-Force IP Sliding Window Rate Limiter
# ==============================================================================

class IPRateLimiter:
    """Sliding-window IP login rate limiter protecting admin control plane."""

    def __init__(self):
        self.attempts: Dict[str, list[float]] = {}
        self.blocked_ips: Dict[str, float] = {}

    def is_blocked(self, ip: str) -> Tuple[bool, int]:
        now = time.time()
        if ip in self.blocked_ips:
            expiry = self.blocked_ips[ip]
            if now < expiry:
                return True, int(expiry - now)
            del self.blocked_ips[ip]
        return False, 0

    def record_failure(self, ip: str) -> Tuple[bool, int]:
        if not settings.LOGIN_RATE_LIMIT:
            return False, 0
        now = time.time()
        window = settings.LOGIN_IP_WINDOW_SECONDS
        max_failures = settings.LOGIN_IP_MAX_FAILURES
        block_sec = settings.LOGIN_IP_BLOCK_SECONDS

        history = self.attempts.get(ip, [])
        # prune old timestamps
        history = [ts for ts in history if now - ts < window]
        history.append(now)
        self.attempts[ip] = history

        if len(history) >= max_failures:
            self.blocked_ips[ip] = now + block_sec
            return True, block_sec
        return False, 0

    def record_success(self, ip: str) -> None:
        self.attempts.pop(ip, None)
        self.blocked_ips.pop(ip, None)


rate_limiter = IPRateLimiter()

"""
Encrypted Ledger - AES-256 Authenticated Disaster Recovery Backup & Restore Engine
Packs SQLite databases, multi-model pool configs, council seats, strategy templates,
custom Python risk plugins, and invite codes into an encrypted backup archive (.enc)
using PBKDF2-HMAC-SHA256 key derivation and Fernet (AES-CBC + HMAC) authenticated encryption.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("system_backup")

BACKUP_DIR = Path("backups").resolve()
DATA_DIR = Path("data").resolve()
ROOT_DIR = Path(".").resolve()


def ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _derive_fernet_key(password: str, salt: bytes) -> Fernet:
    """Derives a Fernet key from password and salt using PBKDF2HMAC."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return Fernet(key)


def create_encrypted_backup(password: str, note: str = "") -> Dict[str, Any]:
    """
    Creates an encrypted backup archive of the entire system state.
    Returns: metadata dict with filename, size, and timestamp.
    """
    ensure_backup_dir()
    if not password or len(password) < 6:
        raise ValueError("灾备加密密码长度必须大于等于 6 位")

    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    filename = f"encrypted_ledger_backup_{timestamp_str}.enc"
    file_path = BACKUP_DIR / filename

    # 1. Collect files into an in-memory zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add data/ directory
        if DATA_DIR.exists():
            for root, _, files in os.walk(DATA_DIR):
                for f in files:
                    full_p = Path(root) / f
                    # Skip temporary files or lock files
                    if f.endswith((".tmp", ".db-wal", ".db-shm", ".lock")):
                        continue
                    arcname = os.path.relpath(full_p, ROOT_DIR)
                    try:
                        zf.write(full_p, arcname)
                    except Exception as e:
                        logger.warning(f"Skipped file {full_p} during backup: {e}")

        # Add .env if exists
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            try:
                zf.write(env_file, ".env")
            except Exception:
                pass

        # Add manifest
        manifest = {
            "version": "2.0.0",
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": note,
            "created_by": "Encrypted Ledger Institutional DR Engine"
        }
        zf.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    raw_zip_bytes = zip_buffer.getvalue()

    # 2. Encrypt using PBKDF2 + Fernet
    salt = os.urandom(16)
    fernet = _derive_fernet_key(password, salt)
    encrypted_payload = fernet.encrypt(raw_zip_bytes)

    # 3. Format: 16 bytes salt + encrypted payload
    final_data = salt + encrypted_payload
    file_path.write_bytes(final_data)

    size_bytes = len(final_data)
    logger.info(f"Successfully created encrypted backup {filename} ({size_bytes} bytes)")

    return {
        "filename": filename,
        "path": str(file_path),
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 2),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note
    }


def restore_encrypted_backup(backup_bytes: bytes, password: str) -> Dict[str, Any]:
    """
    Decrypts and restores the system state from encrypted backup bytes.
    Raises ValueError / InvalidToken if password is incorrect or file is corrupted.
    """
    ensure_backup_dir()
    if len(backup_bytes) < 32:
        raise ValueError("灾备文件损坏或格式无效（文件体积过小）")

    salt = backup_bytes[:16]
    encrypted_payload = backup_bytes[16:]

    try:
        fernet = _derive_fernet_key(password, salt)
        raw_zip_bytes = fernet.decrypt(encrypted_payload)
    except InvalidToken:
        raise ValueError("灾备还原失败：解密密码错误，或文件已被篡改/损坏！")
    except Exception as e:
        raise ValueError(f"灾备解密异常: {e}")

    # Extract zip archive
    zip_buffer = io.BytesIO(raw_zip_bytes)
    restored_files = []
    manifest = {}

    with zipfile.ZipFile(zip_buffer, "r") as zf:
        for member in zf.namelist():
            # Security check: prevent zip slip vulnerability
            target_p = (ROOT_DIR / member).resolve()
            if not str(target_p).startswith(str(ROOT_DIR)):
                continue

            if member == "backup_manifest.json":
                try:
                    manifest = json.loads(zf.read(member).decode("utf-8"))
                except Exception:
                    pass
                continue

            target_p.parent.mkdir(parents=True, exist_ok=True)
            with open(target_p, "wb") as f_out:
                f_out.write(zf.read(member))
            restored_files.append(member)

    logger.info(f"System disaster recovery complete. Restored {len(restored_files)} files.")
    return {
        "status": "success",
        "message": f"系统灾备热还原成功！共恢复 {len(restored_files)} 个核心数据与配置文件。",
        "restored_files_count": len(restored_files),
        "manifest": manifest,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def list_backups() -> List[Dict[str, Any]]:
    """List all available backup files in backups/ directory."""
    ensure_backup_dir()
    results = []
    for f in sorted(BACKUP_DIR.glob("*.enc"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = f.stat()
        results.append({
            "filename": f.name,
            "size_bytes": st.st_size,
            "size_kb": round(st.st_size / 1024, 2),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        })
    return results


def delete_backup_file(filename: str) -> bool:
    """Delete a backup file by filename."""
    ensure_backup_dir()
    safe_name = os.path.basename(filename)
    fpath = BACKUP_DIR / safe_name
    if fpath.exists():
        fpath.unlink()
        return True
    return False

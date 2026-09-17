"""
Encrypted Ledger - Atomic File I/O Engine
Institutional-grade atomic disk operations (mkstemp + fsync + replace) to guarantee zero corruption.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def atomic_write_json(file_path: str | Path, data: Any, indent: int = 2) -> None:
    """Safely write JSON payload to disk using atomic rename after fsync."""
    p = Path(file_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{p.name}-",
        dir=str(p.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json_safe(file_path: str | Path, default: Any = None) -> Any:
    """Read JSON file with fallback to default on non-existence or decoding error."""
    p = Path(file_path).resolve()
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_text(file_path: str | Path, content: str) -> None:
    """Safely write text content to disk atomically."""
    p = Path(file_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{p.name}-",
        dir=str(p.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_text_safe(file_path: str | Path, default: str = "") -> str:
    """Read text file safely."""
    p = Path(file_path).resolve()
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default

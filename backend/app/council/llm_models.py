"""
Encrypted Ledger - Multi-Model Intelligence Pool Manager
Supports registering, updating, testing, and assigning multiple OpenAI-compatible LLM models
to different investment committee seats (Trend, Momentum, Quant, Macro, and CIO).
"""
from __future__ import annotations

import json
import time
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decrypt_secret

LLM_MODELS_PATH = settings.DATA_DIR / "llm_models.json"


def mask_api_key(key: str) -> str:
    """Safely mask API keys for frontend display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "sk-••••••••"
    return key[:4] + "••••••••" + key[-4:]


class LLMModelManager:
    """Manages the pool of multiple reasoning LLM models."""

    def __init__(self):
        self._file_path = LLM_MODELS_PATH
        self._models: Dict[str, Dict[str, Any]] = {}
        self.load_models()

    def load_models(self) -> Dict[str, Dict[str, Any]]:
        """Load configured models from disk or create default entries."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "models" in data:
                        self._models = {m["id"]: m for m in data["models"]}
                        return self._models
            except Exception as e:
                logger.warning(f"Failed to read llm_models.json ({e}), creating defaults.")

        # Initialize with default model from environment if exists
        default_id = "default_gateway"
        self._models = {
            default_id: {
                "id": default_id,
                "name": "默认基础模型 (Global Gateway)",
                "provider": "OpenAI-Compatible",
                "base_url": settings.LLM_BASE_URL,
                "model_name": settings.LLM_MODEL,
                "api_key": settings.LLM_API_KEY,
                "is_default": True,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        self.save_models()
        return self._models

    def save_models(self) -> None:
        """Save models to data/llm_models.json."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump({"models": list(self._models.values()), "version": "2.0.0"}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to write llm_models.json: {e}")

    def get_all_models(self, mask_keys: bool = True) -> List[Dict[str, Any]]:
        """Return list of all models."""
        if not self._models:
            self.load_models()

        res = []
        for m in self._models.values():
            item = dict(m)
            raw_key = item.get("api_key", "")
            if mask_keys:
                item["api_key_masked"] = mask_api_key(raw_key)
                item.pop("api_key", None)
            res.append(item)
        return res

    def get_model(self, model_id: str, unmask: bool = True) -> Optional[Dict[str, Any]]:
        """Get model by ID."""
        if not self._models:
            self.load_models()
        m = self._models.get(model_id)
        if not m:
            return None
        res = dict(m)
        if not unmask:
            res["api_key_masked"] = mask_api_key(res.get("api_key", ""))
            res.pop("api_key", None)
        return res

    def get_default_model(self) -> Optional[Dict[str, Any]]:
        """Get default model entry with unmasked API key."""
        if not self._models:
            self.load_models()
        # 1. Look for explicitly configured default model
        for m in self._models.values():
            if m.get("is_default") and m.get("api_key"):
                return dict(m)
        # 2. Look for any active model in the pool that has an API key configured
        for m in self._models.values():
            if m.get("api_key"):
                return dict(m)
        return None

    def save_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a model in the pool."""
        raw_id = data.get("id")
        model_id = str(raw_id).strip() if raw_id else ""
        if not model_id:
            model_id = f"model_{secrets.token_hex(4)}"

        existing = self._models.get(model_id, {})
        new_key = str(data.get("api_key") or "")

        # If incoming key has asterisks or is empty, retain existing secret key
        if "••" in new_key or "***" in new_key or not new_key.strip():
            final_key = existing.get("api_key", "")
        else:
            final_key = new_key.strip()

        is_default = bool(data.get("is_default", False))
        if is_default:
            for m in self._models.values():
                m["is_default"] = False

        model_entry = {
            "id": model_id,
            "name": data.get("name", "未命名模型").strip(),
            "provider": data.get("provider", "OpenAI-Compatible").strip(),
            "base_url": data.get("base_url", "https://api.openai.com/v1").strip().rstrip("/"),
            "model_name": data.get("model_name", "gpt-4o").strip(),
            "api_key": final_key,
            "is_default": is_default,
            "created_at": existing.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self._models[model_id] = model_entry
        self.save_models()

        res = dict(model_entry)
        res["api_key_masked"] = mask_api_key(final_key)
        res.pop("api_key", None)
        return res

    def delete_model(self, model_id: str) -> bool:
        """Delete a model from pool."""
        if model_id in self._models:
            del self._models[model_id]
            self.save_models()
            return True
        return False

    async def test_connection(
        self,
        base_url: str = "",
        model_name: str = "",
        api_key: str = "",
        model_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Test whether the OpenAI-compatible endpoint responds properly."""
        if not self._models:
            self.load_models()

        target_model = None
        if model_id and model_id in self._models:
            target_model = self._models[model_id]
        elif not api_key or "***" in api_key or "••" in api_key:
            for m in self._models.values():
                if m.get("base_url", "").rstrip("/") == (base_url or "").rstrip("/") and m.get("model_name") == model_name:
                    target_model = m
                    break

        if target_model:
            base_url = base_url or target_model.get("base_url", "")
            model_name = model_name or target_model.get("model_name", "")
            if not api_key or "***" in api_key or "••" in api_key:
                api_key = target_model.get("api_key", "")

        if not base_url or not model_name:
            return False, "Base URL 与 Model Name 不能为空"
        if not api_key:
            return False, "API Key 不能为空，未找到有效的已保存密钥"

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_name.strip(),
            "messages": [
                {"role": "user", "content": "Respond strictly with JSON: {\"ping\": \"pong\"}"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return True, f"连通成功！HTTP {res.status_code}，模型响应正常。"
                return False, f"HTTP {res.status_code}: {res.text[:120]}"
        except Exception as e:
            return False, f"网络请求异常: {str(e)[:120]}"


llm_model_manager = LLMModelManager()

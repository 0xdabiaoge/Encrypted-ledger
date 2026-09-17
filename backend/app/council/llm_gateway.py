"""
Encrypted Ledger - Unified LLM Reasoning Gateway
High-reliability OpenAI-compatible gateway with long-thinking timeout support and JSON schema enforcement.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decrypt_secret


class LLMGateway:
    """Unified OpenAI-compatible Gateway for institutional LLM reasoning."""

    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    def _get_api_key(self) -> str:
        key = settings.LLM_API_KEY
        if key and key.startswith("gAAAA"):
            key = decrypt_secret(key)
        return key

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format_json: bool = True
    ) -> str:
        """Calls LLM endpoint and returns raw text response."""
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("LLM_API_KEY not configured. LLM calls will fail.")
            raise RuntimeError("LLM_API_KEY is not configured.")

        selected_model = model or settings.LLM_MODEL
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
        }

        # Request JSON output if requested
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"LLM Gateway Error [{resp.status_code}]: {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()


llm_gateway = LLMGateway()

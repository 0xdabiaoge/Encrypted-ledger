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
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        response_format_json: bool = True
    ) -> str:
        """Calls LLM endpoint and returns raw text response."""
        resolved_key = api_key or self._get_api_key()
        if not resolved_key:
            logger.warning("LLM API Key not configured. LLM calls will fail.")
            raise RuntimeError("LLM API Key is not configured.")

        selected_base = (base_url or self.base_url).rstrip("/")
        selected_model = model or settings.LLM_MODEL
        url = f"{selected_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {resolved_key}",
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

    async def generate_with_model_id(
        self,
        model_id: Optional[str],
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        response_format_json: bool = True
    ) -> str:
        """Execute reasoning using a specific model assigned from the model pool."""
        from app.council.llm_models import llm_model_manager
        if model_id:
            m = llm_model_manager.get_model(model_id, unmask=True)
            if m and m.get("api_key"):
                return await self.generate_chat_completion(
                    messages=messages,
                    model=m.get("model_name"),
                    base_url=m.get("base_url"),
                    api_key=m.get("api_key"),
                    temperature=temperature,
                    response_format_json=response_format_json
                )
        # Fallback to global default model
        return await self.generate_chat_completion(
            messages=messages,
            temperature=temperature,
            response_format_json=response_format_json
        )


llm_gateway = LLMGateway()

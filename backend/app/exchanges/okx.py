"""
Encrypted Ledger - OKX V5 Institutional Exchange Adapter
Supports Dual Environment (Live / Demo Header), HMAC-SHA256 V5 signing,
native attached TP/SL algo orders (attachAlgoOrds), and Rubik sentiment metrics.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decrypt_secret
from app.exchanges.base import (
    BaseExchangeAdapter,
    ExchangeAPIError,
    ExchangeCapabilities,
    AccountBalance,
    OrderBookDepth,
    PositionInfo,
    TickerData,
    normalize_symbol,
)


class OKXAdapter(BaseExchangeAdapter):
    BASE_HOSTS = ["https://www.okx.com"]

    def __init__(self, is_demo: Optional[bool] = None):
        if is_demo is None:
            is_demo = (settings.OKX_ENV.lower() == "demo")
        super().__init__(is_demo=is_demo)
        self._client: Optional[httpx.AsyncClient] = None
        self._capabilities = ExchangeCapabilities(
            venue="okx",
            display_name="OKX 欧易 V5 永续",
            symbol_template="{base}-USDT-SWAP",
            quantity_unit="contracts",
            supports_attached_tp_sl=True,
            trigger_price_default="last",
            max_candle_limit=300,
            supports_algo_orders=True,
            supports_hedge_mode=True
        )

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return self._capabilities

    def _get_credentials(self) -> Dict[str, str]:
        if self.is_demo:
            api_key = settings.OKX_DEMO_API_KEY
            sec_key = settings.OKX_DEMO_SECRET_KEY
            passphrase = settings.OKX_DEMO_PASSPHRASE
        else:
            api_key = settings.OKX_LIVE_API_KEY
            sec_key = settings.OKX_LIVE_SECRET_KEY
            passphrase = settings.OKX_LIVE_PASSPHRASE

        # Decrypt if stored encrypted
        if sec_key and sec_key.startswith("gAAAA"):
            sec_key = decrypt_secret(sec_key)
        if passphrase and passphrase.startswith("gAAAA"):
            passphrase = decrypt_secret(passphrase)

        return {
            "api_key": api_key,
            "secret_key": sec_key,
            "passphrase": passphrase
        }

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str, secret_key: str) -> str:
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256)
        return base64.b64encode(mac.digest()).decode("utf-8")

    @property
    def client(self) -> httpx.AsyncClient:
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if self._client is None or self._client.is_closed or getattr(self, "_loop", None) != cur_loop:
            self._loop = cur_loop
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
            )
        return self._client

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None, auth_required: bool = False) -> Any:
        query_str = ""
        if params:
            import urllib.parse
            query_str = "?" + urllib.parse.urlencode(params)
        full_path = path + query_str
        body_str = json.dumps(body) if body else ""

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "EncryptedLedger-Desk/1.0"
        }
        if self.is_demo and auth_required:
            headers["x-simulated-trading"] = "1"

        if auth_required:
            creds = self._get_credentials()
            if not creds["api_key"] or not creds["secret_key"] or not creds["passphrase"]:
                raise ExchangeAPIError("okx", "AUTH_NOT_CONFIGURED", f"OKX {'Demo' if self.is_demo else 'Live'} credentials incomplete.")
            
            # ISO 8601 UTC timestamp format: 2026-09-17T06:00:00.000Z
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            sig = self._generate_signature(now_iso, method, full_path, body_str, creds["secret_key"])
            headers.update({
                "OK-ACCESS-KEY": creds["api_key"],
                "OK-ACCESS-SIGN": sig,
                "OK-ACCESS-TIMESTAMP": now_iso,
                "OK-ACCESS-PASSPHRASE": creds["passphrase"]
            })

        last_err = None
        for base_url in self.BASE_HOSTS:
            url = f"{base_url}{full_path}"
            for attempt in range(2):
                try:
                    if method.upper() == "GET":
                        resp = await self.client.get(url, headers=headers)
                    elif method.upper() == "POST":
                        resp = await self.client.post(url, headers=headers, content=body_str)
                    elif method.upper() == "DELETE":
                        resp = await self.client.request("DELETE", url, headers=headers, content=body_str)
                    else:
                        resp = await self.client.request(method, url, headers=headers, content=body_str)

                    if resp.status_code != 200:
                        raise ExchangeAPIError("okx", resp.status_code, f"HTTP status error: {resp.text}")

                    payload = resp.json()
                    code = str(payload.get("code", "0"))
                    if code != "0":
                        raise ExchangeAPIError("okx", code, payload.get("msg", "Unknown OKX API Error"))
                    return payload.get("data", [])
                except Exception as e:
                    last_err = e
                    if attempt == 0:
                        await asyncio.sleep(0.15)
                        continue
        raise last_err or ExchangeAPIError("okx", -1, "All OKX endpoints unreachable")

    def _to_inst_id(self, symbol: str) -> str:
        base = normalize_symbol(symbol)
        return f"{base}-USDT-SWAP"

    async def get_ticker(self, symbol: str) -> TickerData:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/api/v5/market/ticker", params={"instId": inst_id})
        if not data:
            raise ExchangeAPIError("okx", "NO_DATA", f"Ticker not found for {inst_id}")
        t = data[0]
        now_ms = int(t.get("ts", time.time() * 1000))
        return TickerData(
            venue="okx",
            symbol=normalize_symbol(symbol),
            inst_id=inst_id,
            last_price=float(t.get("last", 0.0)),
            bid_price=float(t.get("bidPx", 0.0)),
            ask_price=float(t.get("askPx", 0.0)),
            volume_24h_usd=float(t.get("volCcy24h", 0.0)),
            high_24h=float(t.get("high24h", 0.0)),
            low_24h=float(t.get("low24h", 0.0)),
            timestamp_ms=now_ms
        )

    async def get_candles(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> List[Dict[str, Any]]:
        # OKX timeframe format mapping: 1m, 5m, 15m, 30m, 1H, 4H, 1D
        tf_lower = timeframe.lower()
        if tf_lower == "15d":
            # Resample 1D bars into 15-day bars
            raw_limit = min(300, max(30, limit * 15))
            d1_candles = await self.get_candles(symbol, timeframe="1d", limit=raw_limit)
            if not d1_candles:
                return []
            resampled = []
            for i in range(0, len(d1_candles), 15):
                chunk = d1_candles[i:i+15]
                if not chunk:
                    continue
                resampled.append({
                    "timestamp": chunk[0]["timestamp"],
                    "open": chunk[0]["open"],
                    "high": max(c["high"] for c in chunk),
                    "low": min(c["low"] for c in chunk),
                    "close": chunk[-1]["close"],
                    "volume": round(sum(c["volume"] for c in chunk), 4),
                    "volume_usd": round(sum(c.get("volume_usd", 0.0) for c in chunk), 2)
                })
            return resampled

        tf_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", "1d": "1D"
        }
        bar = tf_map.get(tf_lower, "15m")
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/api/v5/market/candles", params={"instId": inst_id, "bar": bar, "limit": str(limit)})
        
        # OKX candle schema: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        candles = []
        for row in reversed(data):
            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "volume_usd": float(row[6]) if len(row) > 6 else 0.0
            })
        return candles

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookDepth:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/api/v5/market/books", params={"instId": inst_id, "sz": str(depth)})
        if not data:
            raise ExchangeAPIError("okx", "NO_DATA", f"Depth not found for {inst_id}")
        b = data[0]
        # bids/asks: [[px, sz, ...], ...]
        bids = [[float(x[0]), float(x[1])] for x in b.get("bids", [])]
        asks = [[float(x[0]), float(x[1])] for x in b.get("asks", [])]
        
        bid_vol = sum(x[1] for x in bids)
        ask_vol = sum(x[1] for x in asks)
        denom = bid_vol + ask_vol
        imbalance = ((bid_vol - ask_vol) / denom) if denom > 0 else 0.0

        return OrderBookDepth(
            venue="okx",
            symbol=normalize_symbol(symbol),
            inst_id=inst_id,
            bids=bids,
            asks=asks,
            imbalance_ratio=round(imbalance, 4),
            timestamp_ms=int(b.get("ts", time.time() * 1000))
        )

    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/api/v5/public/funding-rate", params={"instId": inst_id})
        if not data:
            return {"funding_rate": 0.0, "next_funding_time": 0}
        f = data[0]
        return {
            "funding_rate": float(f.get("fundingRate", 0.0)),
            "next_funding_time": int(f.get("nextFundingTime", 0))
        }

    async def get_rubik_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Fetch OKX Rubik big-data long/short account ratio."""
        ccy = normalize_symbol(symbol)
        try:
            data = await self._request("GET", "/api/v5/rubik/stat/contracts/long-short-account-ratio", params={"ccy": ccy})
            if data and len(data) > 0 and len(data[0]) >= 2:
                ratio = float(data[0][1] or 1.0)
                bull_pct = round((ratio / (ratio + 1.0)) * 100, 1)
                bear_pct = round((1.0 / (ratio + 1.0)) * 100, 1)
                return {
                    "ccy": ccy,
                    "long_short_ratio": ratio,
                    "bull_ratio_pct": bull_pct,
                    "bear_ratio_pct": bear_pct,
                    "label": "bullish" if ratio >= 1.2 else ("bearish" if ratio <= 0.83 else "neutral")
                }
        except Exception as e:
            logger.warning(f"OKX Rubik sentiment retrieval failed for {ccy}: {e}")
        return {"ccy": ccy, "long_short_ratio": 1.0, "bull_ratio_pct": 50.0, "bear_ratio_pct": 50.0, "label": "neutral"}

    async def get_account_balance(self) -> AccountBalance:
        data = await self._request("GET", "/api/v5/account/balance", params={"ccy": "USDT"}, auth_required=True)
        if not data:
            return AccountBalance(venue="okx", total_equity_usd=0.0, available_usd=0.0, margin_used_usd=0.0, unrealized_pnl_usd=0.0, timestamp_ms=int(time.time()*1000))
        acc = data[0]
        total_eq = float(acc.get("totalEq", 0.0))
        details = acc.get("details", [])
        avail = 0.0
        used_margin = 0.0
        upl = float(acc.get("upl", 0.0))
        for d in details:
            if d.get("ccy") == "USDT":
                avail = float(d.get("availEq") or d.get("availBal") or 0.0)
                used_margin = float(d.get("margin", 0.0)) or float(d.get("frozenBal", 0.0))
                break
        return AccountBalance(
            venue="okx",
            total_equity_usd=total_eq,
            available_usd=avail,
            margin_used_usd=used_margin,
            unrealized_pnl_usd=upl,
            timestamp_ms=int(acc.get("uTime", time.time() * 1000))
        )

    async def get_positions(self) -> List[PositionInfo]:
        data = await self._request("GET", "/api/v5/account/positions", params={"instType": "SWAP"}, auth_required=True)
        positions = []
        for p in data:
            sz = float(p.get("pos", 0.0))
            if abs(sz) <= 0.0:
                continue
            pos_side = p.get("posSide", "net")
            side = "long" if (pos_side == "long" or (pos_side == "net" and sz > 0)) else "short"
            notional = float(p.get("notionalUsd", 0.0))
            entry_px = float(p.get("avgPx", 0.0))
            mark_px = float(p.get("markPx", 0.0))
            upl = float(p.get("upl", 0.0))
            upl_ratio = float(p.get("uplRatio", 0.0))
            lever = float(p.get("lever", 1.0))
            margin = float(p.get("margin", 0.0))
            liq_px = float(p.get("liqPx", 0.0))
            
            positions.append(PositionInfo(
                venue="okx",
                symbol=normalize_symbol(p.get("instId", "")),
                inst_id=p.get("instId", ""),
                side=side,
                size=abs(sz),
                notional_usd=notional,
                entry_price=entry_px,
                mark_price=mark_px,
                unrealized_pnl_usd=upl,
                unrealized_pnl_ratio=upl_ratio,
                leverage=lever,
                margin_usd=margin,
                liquidation_price=liq_px
            ))
        return positions

    async def submit_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        leverage: float = 3.0,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        inst_id = self._to_inst_id(symbol)
        
        # Set leverage first
        try:
            await self._request("POST", "/api/v5/account/set-leverage", body={
                "instId": inst_id,
                "lever": str(int(leverage)),
                "mgnMode": "cross"
            }, auth_required=True)
        except Exception as e:
            logger.warning(f"OKX set leverage {leverage} for {inst_id} warning: {e}")

        # Construct order payload
        cl_ord_id = client_order_id or f"EL_{int(time.time()*1000)}_{symbol}"
        payload: Dict[str, Any] = {
            "instId": inst_id,
            "tdMode": "cross",
            "clOrdId": cl_ord_id,
            "side": side.lower(),
            "posSide": "long" if side.lower() == "buy" else "short",
            "ordType": order_type.lower(),
            "sz": str(quantity)
        }
        if order_type.lower() == "limit" and price:
            payload["px"] = str(price)

        # Attach Native TP/SL Algo Orders (attachAlgoOrds) - Zero naked exposure
        attached_algos = []
        if stop_loss_price and stop_loss_price > 0:
            attached_algos.append({
                "attachAlgoClOrdId": f"SL_{cl_ord_id}",
                "tpTriggerPx": "",
                "tpOrdPx": "",
                "slTriggerPx": str(stop_loss_price),
                "slOrdPx": "-1",  # -1 signifies market order upon trigger
                "slTriggerPxType": "last"
            })
        if take_profit_price and take_profit_price > 0:
            if attached_algos:
                attached_algos[0]["tpTriggerPx"] = str(take_profit_price)
                attached_algos[0]["tpOrdPx"] = "-1"
                attached_algos[0]["tpTriggerPxType"] = "last"
            else:
                attached_algos.append({
                    "attachAlgoClOrdId": f"TP_{cl_ord_id}",
                    "tpTriggerPx": str(take_profit_price),
                    "tpOrdPx": "-1",
                    "tpTriggerPxType": "last",
                    "slTriggerPx": "",
                    "slOrdPx": ""
                })

        if attached_algos:
            payload["attachAlgoOrds"] = attached_algos

        res = await self._request("POST", "/api/v5/trade/order", body=payload, auth_required=True)
        return {"order_id": res[0].get("ordId") if res else "", "cl_ord_id": cl_ord_id, "raw": res}

    async def close_position(self, symbol: str, side: str, size: Optional[float] = None) -> Dict[str, Any]:
        inst_id = self._to_inst_id(symbol)
        # Close via /api/v5/trade/close-position
        body = {
            "instId": inst_id,
            "mgnMode": "cross",
            "posSide": side.lower()  # "long" | "short"
        }
        res = await self._request("POST", "/api/v5/trade/close-position", body=body, auth_required=True)
        return {"success": True, "data": res}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        inst_id = self._to_inst_id(symbol)
        try:
            await self._request("POST", "/api/v5/trade/cancel-order", body={
                "instId": inst_id,
                "ordId": order_id
            }, auth_required=True)
            return True
        except Exception as e:
            logger.error(f"OKX cancel order {order_id} failed: {e}")
            return False

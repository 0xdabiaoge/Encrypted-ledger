"""
Encrypted Ledger - Binance Futures (USDT-M) Institutional Adapter
Supports Live (fapi.binance.com) & Demo (demo-fapi.binance.com),
HMAC-SHA256 signing, Algo Conditional orders, and high-frequency book depth.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
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


class BinanceAdapter(BaseExchangeAdapter):
    LIVE_URL = "https://fapi.binance.com"
    DEMO_URL = "https://demo-fapi.binance.com"

    def __init__(self, is_demo: Optional[bool] = None):
        if is_demo is None:
            is_demo = (settings.BINANCE_ENV.lower() == "demo")
        super().__init__(is_demo=is_demo)
        self.base_url = self.DEMO_URL if self.is_demo else self.LIVE_URL
        self._client: Optional[httpx.AsyncClient] = None
        self._capabilities = ExchangeCapabilities(
            venue="binance",
            display_name="Binance 币安 USDT-M 合约",
            symbol_template="{base}USDT",
            quantity_unit="base_asset",
            supports_attached_tp_sl=False,  # Binance handles TP/SL as separate Algo orders
            trigger_price_default="last",
            max_candle_limit=500,
            supports_algo_orders=True,
            supports_hedge_mode=True
        )

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return self._capabilities

    def _get_credentials(self) -> Dict[str, str]:
        if self.is_demo:
            api_key = settings.BINANCE_DEMO_API_KEY
            sec_key = settings.BINANCE_DEMO_SECRET_KEY
        else:
            api_key = settings.BINANCE_LIVE_API_KEY
            sec_key = settings.BINANCE_LIVE_SECRET_KEY

        if sec_key and sec_key.startswith("gAAAA"):
            sec_key = decrypt_secret(sec_key)

        return {
            "api_key": api_key,
            "secret_key": sec_key
        }

    def _sign_query(self, params: Dict[str, Any], secret_key: str) -> str:
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        sig = hmac.new(secret_key.encode("utf-8"), query.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()
        return f"{query}&signature={sig}"

    def _to_inst_id(self, symbol: str) -> str:
        base = normalize_symbol(symbol)
        return f"{base}USDT"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
            )
        return self._client

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, auth_required: bool = False) -> Any:
        params = params or {}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "EncryptedLedger-Desk/1.0"
        }
        creds = self._get_credentials()
        query_str = ""

        if auth_required:
            if not creds["api_key"] or not creds["secret_key"]:
                raise ExchangeAPIError("binance", "AUTH_NOT_CONFIGURED", f"Binance {'Demo' if self.is_demo else 'Live'} credentials incomplete.")
            headers["X-MBX-APIKEY"] = creds["api_key"]
            query_str = "?" + self._sign_query(params, creds["secret_key"])
        elif params:
            query_str = "?" + urllib.parse.urlencode(params)

        url = f"{self.base_url}{path}{query_str}"
        try:
            if method.upper() == "GET":
                resp = await self.client.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = await self.client.post(url, headers=headers)
            elif method.upper() == "DELETE":
                resp = await self.client.delete(url, headers=headers)
            else:
                resp = await self.client.request(method, url, headers=headers)

            if resp.status_code != 200:
                try:
                    err = resp.json()
                    raise ExchangeAPIError("binance", err.get("code", resp.status_code), err.get("msg", resp.text), resp.status_code)
                except Exception:
                    raise ExchangeAPIError("binance", resp.status_code, resp.text, resp.status_code)

            return resp.json()
        except Exception as e:
            if isinstance(e, ExchangeAPIError):
                raise
            raise ExchangeAPIError("binance", -1, f"Binance request failed: {e}")

    async def get_ticker(self, symbol: str) -> TickerData:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/fapi/v1/ticker/24hr", params={"symbol": inst_id})
        book = await self._request("GET", "/fapi/v1/ticker/bookTicker", params={"symbol": inst_id})
        
        return TickerData(
            venue="binance",
            symbol=normalize_symbol(symbol),
            inst_id=inst_id,
            last_price=float(data.get("lastPrice", 0.0)),
            bid_price=float(book.get("bidPrice", 0.0)),
            ask_price=float(book.get("askPrice", 0.0)),
            volume_24h_usd=float(data.get("quoteVolume", 0.0)),
            high_24h=float(data.get("highPrice", 0.0)),
            low_24h=float(data.get("lowPrice", 0.0)),
            timestamp_ms=int(data.get("closeTime", time.time() * 1000))
        )

    async def get_candles(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> List[Dict[str, Any]]:
        inst_id = self._to_inst_id(symbol)
        tf = timeframe.lower()
        data = await self._request("GET", "/fapi/v1/klines", params={"symbol": inst_id, "interval": tf, "limit": limit})
        
        candles = []
        for row in data:
            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "volume_usd": float(row[7])
            })
        return candles

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookDepth:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/fapi/v1/depth", params={"symbol": inst_id, "limit": depth})
        
        bids = [[float(x[0]), float(x[1])] for x in data.get("bids", [])]
        asks = [[float(x[0]), float(x[1])] for x in data.get("asks", [])]
        bid_vol = sum(x[1] for x in bids)
        ask_vol = sum(x[1] for x in asks)
        denom = bid_vol + ask_vol
        imbalance = ((bid_vol - ask_vol) / denom) if denom > 0 else 0.0

        return OrderBookDepth(
            venue="binance",
            symbol=normalize_symbol(symbol),
            inst_id=inst_id,
            bids=bids,
            asks=asks,
            imbalance_ratio=round(imbalance, 4),
            timestamp_ms=int(data.get("T", time.time() * 1000))
        )

    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        inst_id = self._to_inst_id(symbol)
        data = await self._request("GET", "/fapi/v1/premiumIndex", params={"symbol": inst_id})
        return {
            "funding_rate": float(data.get("lastFundingRate", 0.0)),
            "next_funding_time": int(data.get("nextFundingTime", 0))
        }

    async def get_account_balance(self) -> AccountBalance:
        data = await self._request("GET", "/fapi/v2/account", auth_required=True)
        total_margin = float(data.get("totalMarginBalance", 0.0))
        avail = float(data.get("availableBalance", 0.0))
        init_margin = float(data.get("totalInitialMargin", 0.0))
        unrealized_pnl = float(data.get("totalUnrealizedProfit", 0.0))

        return AccountBalance(
            venue="binance",
            total_equity_usd=total_margin,
            available_usd=avail,
            margin_used_usd=init_margin,
            unrealized_pnl_usd=unrealized_pnl,
            timestamp_ms=int(data.get("updateTime", time.time() * 1000))
        )

    async def get_positions(self) -> List[PositionInfo]:
        data = await self._request("GET", "/fapi/v2/positionRisk", auth_required=True)
        positions = []
        for p in data:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) <= 0.0:
                continue
            side = "long" if amt > 0 else "short"
            notional = abs(float(p.get("notional", 0.0)))
            entry_px = float(p.get("entryPrice", 0.0))
            mark_px = float(p.get("markPrice", 0.0))
            upl = float(p.get("unRealizedProfit", 0.0))
            lever = float(p.get("leverage", 1.0))
            liq_px = float(p.get("liquidationPrice", 0.0))
            margin = notional / lever if lever > 0 else 0.0
            upl_ratio = (upl / margin) if margin > 0 else 0.0

            positions.append(PositionInfo(
                venue="binance",
                symbol=normalize_symbol(p.get("symbol", "")),
                inst_id=p.get("symbol", ""),
                side=side,
                size=abs(amt),
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

        # Set Leverage
        try:
            await self._request("POST", "/fapi/v1/leverage", params={
                "symbol": inst_id,
                "leverage": int(leverage)
            }, auth_required=True)
        except Exception as e:
            logger.warning(f"Binance set leverage {leverage} for {inst_id}: {e}")

        cl_id = client_order_id or f"EL_{int(time.time()*1000)}_{symbol}"
        order_params = {
            "symbol": inst_id,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "newClientOrderId": cl_id
        }
        if order_type.upper() == "LIMIT" and price:
            order_params["price"] = price
            order_params["timeInForce"] = "GTC"

        res = await self._request("POST", "/fapi/v1/order", params=order_params, auth_required=True)
        order_id = str(res.get("orderId", ""))

        # Place TP/SL Protection Orders on Binance
        opposite_side = "SELL" if side.upper() == "BUY" else "BUY"
        if stop_loss_price and stop_loss_price > 0:
            try:
                await self._request("POST", "/fapi/v1/order", params={
                    "symbol": inst_id,
                    "side": opposite_side,
                    "type": "STOP_MARKET",
                    "stopPrice": stop_loss_price,
                    "closePosition": "true",
                    "workingType": "CONTRACT_PRICE"
                }, auth_required=True)
            except Exception as e:
                logger.error(f"Binance protective STOP_MARKET failed: {e}")

        if take_profit_price and take_profit_price > 0:
            try:
                await self._request("POST", "/fapi/v1/order", params={
                    "symbol": inst_id,
                    "side": opposite_side,
                    "type": "TAKE_PROFIT_MARKET",
                    "stopPrice": take_profit_price,
                    "closePosition": "true",
                    "workingType": "CONTRACT_PRICE"
                }, auth_required=True)
            except Exception as e:
                logger.error(f"Binance protective TAKE_PROFIT_MARKET failed: {e}")

        return {"order_id": order_id, "cl_ord_id": cl_id, "raw": res}

    async def close_position(self, symbol: str, side: str, size: Optional[float] = None) -> Dict[str, Any]:
        inst_id = self._to_inst_id(symbol)
        close_side = "SELL" if side.lower() == "long" else "BUY"
        params = {
            "symbol": inst_id,
            "side": close_side,
            "type": "MARKET",
            "reduceOnly": "true"
        }
        if size and size > 0:
            params["quantity"] = size
        else:
            # Fetch current position to close full
            positions = await self.get_positions()
            for p in positions:
                if p.inst_id == inst_id and p.side.lower() == side.lower():
                    params["quantity"] = p.size
                    break
        res = await self._request("POST", "/fapi/v1/order", params=params, auth_required=True)
        return {"success": True, "data": res}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        inst_id = self._to_inst_id(symbol)
        try:
            await self._request("DELETE", "/fapi/v1/order", params={
                "symbol": inst_id,
                "orderId": int(order_id)
            }, auth_required=True)
            return True
        except Exception as e:
            logger.error(f"Binance cancel order {order_id} failed: {e}")
            return False

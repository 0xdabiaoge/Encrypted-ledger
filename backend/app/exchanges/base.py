"""
Encrypted Ledger - Unified Exchange Adapter Base Specification
Defines the canonical interfaces, data structures, and capability matrix for OKX and Binance.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional


class ExchangeAPIError(RuntimeError):
    """Normalized exchange communication and business logic exception."""
    def __init__(self, venue: str, code: Any, message: str, status_code: int = 0):
        super().__init__(f"[{venue.upper()} Error {code}] {message}")
        self.venue = venue
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ExchangeCapabilities:
    venue: str                       # "okx" | "binance"
    display_name: str
    symbol_template: str             # e.g. "{base}-USDT-SWAP" vs "{base}USDT"
    quote: str = "USDT"
    quantity_unit: str = "contracts" # "contracts"(OKX张) | "base_asset"(Binance币数)
    supports_attached_tp_sl: bool = False
    trigger_price_default: str = "last"
    max_candle_limit: int = 300
    supports_algo_orders: bool = True
    supports_hedge_mode: bool = True


@dataclass(frozen=True)
class InstrumentSpec:
    venue: str
    inst_id: str
    base: str
    tick_size: float
    step_size: float
    ct_val: float             # OKX: contract multiplier (e.g. 0.01 for BTC), Binance: 1.0
    min_size: float
    max_leverage: float = 20.0
    status: str = "trading"


@dataclass
class TickerData:
    venue: str
    symbol: str
    inst_id: str
    last_price: float
    bid_price: float
    ask_price: float
    volume_24h_usd: float
    high_24h: float
    low_24h: float
    timestamp_ms: int


@dataclass
class OrderBookDepth:
    venue: str
    symbol: str
    inst_id: str
    bids: List[List[float]]  # [[price, size], ...] sorted descending
    asks: List[List[float]]  # [[price, size], ...] sorted ascending
    imbalance_ratio: float   # (bid_vol - ask_vol) / (bid_vol + ask_vol)
    timestamp_ms: int


@dataclass
class PositionInfo:
    venue: str
    symbol: str
    inst_id: str
    side: str                # "long" | "short"
    size: float              # Native size (contracts or coins)
    notional_usd: float      # Position nominal value
    entry_price: float
    mark_price: float
    unrealized_pnl_usd: float
    unrealized_pnl_ratio: float
    leverage: float
    margin_usd: float
    liquidation_price: float


@dataclass
class AccountBalance:
    venue: str
    total_equity_usd: float
    available_usd: float
    margin_used_usd: float
    unrealized_pnl_usd: float
    timestamp_ms: int


def normalize_symbol(raw_symbol: str) -> str:
    """Normalize any format (BTC, BTCUSDT, BTC-USDT-SWAP) to canonical base 'BTC'."""
    s = raw_symbol.upper().strip()
    for suffix in ["-USDT-SWAP", "-USD-SWAP", "USDT", "-USDT"]:
        if s.endswith(suffix):
            return s[:-len(suffix)]
    return s


class BaseExchangeAdapter(ABC):
    """Abstract base class for CEX connectors (OKX & Binance)."""

    def __init__(self, is_demo: bool = True):
        self.is_demo = is_demo

    @property
    @abstractmethod
    def capabilities(self) -> ExchangeCapabilities:
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerData:
        pass

    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookDepth:
        pass

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_account_balance(self) -> AccountBalance:
        pass

    @abstractmethod
    async def get_positions(self) -> List[PositionInfo]:
        pass

    @abstractmethod
    async def submit_order(
        self,
        symbol: str,
        side: str,           # "buy" | "sell"
        order_type: str,     # "limit" | "market"
        quantity: float,     # Base asset quantity or contracts
        price: Optional[float] = None,
        leverage: float = 3.0,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def close_position(self, symbol: str, side: str, size: Optional[float] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        pass

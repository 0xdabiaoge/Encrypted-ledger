"""
Encrypted Ledger - Market Data & Quantitative Factor API
Real-time quotes, orderbook depth, candles, calculus dynamics, and 5-pillar factor scores.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from app.exchanges.router import order_router
from app.quant.universe import universe_manager
from app.quant.factors import compute_factor_matrix

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/universe")
async def get_universe():
    """List all configured instruments in trading pool."""
    return universe_manager.load_instruments()


@router.get("/tickers")
async def get_all_tickers(venue: str = Query("okx", description="okx | binance")):
    """Fetch tickers for all universe instruments in parallel with high resilience."""
    instruments = universe_manager.load_instruments()
    symbols = [inst.get("name", "") if isinstance(inst, dict) else getattr(inst, "name", "") for inst in instruments]
    symbols = [s for s in symbols if s]
    adapter = order_router.get_adapter(venue)
    alt_venue = "binance" if venue.lower() == "okx" else "okx"
    alt_adapter = order_router.get_adapter(alt_venue)

    async def _fetch_one(sym: str):
        try:
            t = await adapter.get_ticker(sym)
            d = t.__dict__.copy()
            d["last"] = t.last_price
            d["price"] = t.last_price
            return sym, d
        except Exception:
            try:
                t = await alt_adapter.get_ticker(sym)
                d = t.__dict__.copy()
                d["last"] = t.last_price
                d["price"] = t.last_price
                return sym, d
            except Exception:
                return sym, None

    results = await asyncio.gather(*[_fetch_one(s) for s in symbols])
    return {sym: d for sym, d in results if d is not None}


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, venue: str = Query("okx", description="okx | binance")):
    adapter = order_router.get_adapter(venue)
    try:
        data = await adapter.get_ticker(symbol)
        d = data.__dict__.copy()
        d["last"] = data.last_price
        d["price"] = data.last_price
        return d
    except Exception as e:
        # Fallback to alternate venue
        try:
            alt_venue = "binance" if venue.lower() == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            data = await alt_adapter.get_ticker(symbol)
            d = data.__dict__.copy()
            d["last"] = data.last_price
            d["price"] = data.last_price
            return d
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "15m", limit: int = 100, venue: str = "okx"):
    adapter = order_router.get_adapter(venue)
    try:
        return await adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        try:
            alt_venue = "binance" if venue.lower() == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            return await alt_adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, depth: int = 20, venue: str = "okx"):
    adapter = order_router.get_adapter(venue)
    try:
        data = await adapter.get_orderbook(symbol, depth=depth)
        return data.__dict__
    except Exception as e:
        try:
            alt_venue = "binance" if venue.lower() == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            data = await alt_adapter.get_orderbook(symbol, depth=depth)
            return data.__dict__
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/factors/{symbol}")
async def get_factors(symbol: str):
    """Computes real-time 5-pillar factor matrix and composite alpha score with dual-venue redundancy."""
    okx = order_router.okx
    binance = order_router.binance

    candles = None
    book = None
    rubik = {"long_short_ratio": 1.0}
    funding = {"funding_rate": 0.0001}

    # 1. Fetch candles from OKX with Binance fallback
    try:
        candles = await okx.get_candles(symbol, timeframe="15m", limit=60)
    except Exception:
        try:
            candles = await binance.get_candles(symbol, timeframe="15m", limit=60)
        except Exception:
            pass

    # 2. Fetch orderbook from OKX with Binance fallback
    try:
        book = await okx.get_orderbook(symbol, depth=20)
    except Exception:
        try:
            book = await binance.get_orderbook(symbol, depth=20)
        except Exception:
            pass

    # 3. Sentiment & Funding (OKX primary, non-blocking)
    try:
        rubik = await okx.get_rubik_sentiment(symbol)
    except Exception:
        pass

    try:
        funding = await okx.get_funding_rate(symbol)
    except Exception:
        pass

    if not candles:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market candles for {symbol} on both OKX and Binance")

    imbalance = book.imbalance_ratio if book else 0.0
    matrix = compute_factor_matrix(
        candles_15m=candles,
        orderbook_imbalance=imbalance,
        long_short_ratio=rubik.get("long_short_ratio", 1.0),
        funding_rate=funding.get("funding_rate", 0.0)
    )
    matrix["calculus"] = matrix.get("pillar_1_trend", {})
    return {"symbol": symbol.upper(), "factors": matrix, **matrix}

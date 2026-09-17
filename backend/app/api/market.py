"""
Encrypted Ledger - Market Data & Quantitative Factor API
Real-time quotes, orderbook depth, candles, calculus dynamics, and 5-pillar factor scores.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from app.exchanges.router import order_router
from app.quant.universe import universe_manager
from app.quant.factors import compute_factor_matrix

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/universe")
async def get_universe():
    """List all configured instruments in trading pool."""
    return universe_manager.load_instruments()


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, venue: str = Query("okx", description="okx | binance")):
    adapter = order_router.get_adapter(venue)
    try:
        data = await adapter.get_ticker(symbol)
        return data.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "15m", limit: int = 100, venue: str = "okx"):
    adapter = order_router.get_adapter(venue)
    try:
        return await adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, depth: int = 20, venue: str = "okx"):
    adapter = order_router.get_adapter(venue)
    try:
        data = await adapter.get_orderbook(symbol, depth=depth)
        return data.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/factors/{symbol}")
async def get_factors(symbol: str):
    """Computes real-time 5-pillar factor matrix and composite alpha score."""
    okx = order_router.okx
    try:
        candles = await okx.get_candles(symbol, timeframe="15m", limit=60)
        book = await okx.get_orderbook(symbol, depth=20)
        rubik = await okx.get_rubik_sentiment(symbol)
        funding = await okx.get_funding_rate(symbol)
        
        matrix = compute_factor_matrix(
            candles_15m=candles,
            orderbook_imbalance=book.imbalance_ratio,
            long_short_ratio=rubik.get("long_short_ratio", 1.0),
            funding_rate=funding.get("funding_rate", 0.0)
        )
        return {"symbol": symbol.upper(), "factors": matrix}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

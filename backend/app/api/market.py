"""
Encrypted Ledger - Market Data & Quantitative Factor API
Real-time quotes, orderbook depth, candles, calculus dynamics, and 5-pillar factor scores.
Supports OKX, Binance, Gate.io (Meme/Altcoin priority), and Smart Hybrid Aggregation.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from app.exchanges.router import order_router
from app.exchanges.categories import is_meme_or_altcoin, extract_base_asset
from app.quant.universe import universe_manager
from app.quant.factors import compute_factor_matrix

router = APIRouter(prefix="/market", tags=["Market Data"])


def _calculate_ma_series(candles: List[Dict[str, Any]], period: int) -> List[Dict[str, Any]]:
    mas = []
    closes = [c["close"] for c in candles]
    for i in range(len(candles)):
        if i + 1 < period:
            continue
        avg = sum(closes[i + 1 - period : i + 1]) / period
        mas.append({
            "time": candles[i]["timestamp"] // 1000,
            "value": round(avg, 4)
        })
    return mas


def _calculate_boll_series(candles: List[Dict[str, Any]], period: int = 20, mult: float = 2.0) -> Dict[str, List[Dict[str, Any]]]:
    upper = []
    middle = []
    lower = []
    closes = [c["close"] for c in candles]
    for i in range(len(candles)):
        if i + 1 < period:
            continue
        window = closes[i + 1 - period : i + 1]
        mean = sum(window) / period
        std = (sum((x - mean) ** 2 for x in window) / period) ** 0.5
        t_sec = candles[i]["timestamp"] // 1000
        upper.append({"time": t_sec, "value": round(mean + mult * std, 4)})
        middle.append({"time": t_sec, "value": round(mean, 4)})
        lower.append({"time": t_sec, "value": round(mean - mult * std, 4)})
    return {"upper": upper, "middle": middle, "lower": lower}


@router.get("/universe")
async def get_universe():
    """List all configured instruments in trading pool."""
    return universe_manager.load_instruments()


@router.get("/tickers")
async def get_all_tickers(venue: str = Query("okx", description="okx | binance | gate | agg | smart_agg")):
    """Fetch tickers for all universe instruments in parallel with high resilience and smart category routing."""
    instruments = universe_manager.load_instruments()
    symbols = [inst.get("name", "") if isinstance(inst, dict) else getattr(inst, "name", "") for inst in instruments]
    symbols = [s for s in symbols if s]
    v_clean = venue.lower().strip()

    inst_map = {inst.get("name", "").upper(): inst for inst in instruments if isinstance(inst, dict)}

    if v_clean in ("agg", "smart_agg"):
        async def _fetch_smart_agg(sym: str):
            inst = inst_map.get(sym.upper())
            inst_venue = str(inst.get("venue") or "auto").lower().strip() if inst else "auto"

            # 1. Designated venue specified by user in universe
            if inst_venue == "gate":
                try:
                    t_gate = await order_router.gate.get_ticker(sym)
                    d = t_gate.__dict__.copy()
                    d["venue"] = "gate"
                    d["designated_venue"] = "gate"
                    d["last"] = t_gate.last_price
                    d["price"] = t_gate.last_price
                    return sym, d
                except Exception:
                    pass
            elif inst_venue == "okx":
                try:
                    t_okx = await order_router.okx.get_ticker(sym)
                    d = t_okx.__dict__.copy()
                    d["venue"] = "okx"
                    d["designated_venue"] = "okx"
                    d["last"] = t_okx.last_price
                    d["price"] = t_okx.last_price
                    return sym, d
                except Exception:
                    pass
            elif inst_venue == "binance":
                try:
                    t_bin = await order_router.binance.get_ticker(sym)
                    d = t_bin.__dict__.copy()
                    d["venue"] = "binance"
                    d["designated_venue"] = "binance"
                    d["last"] = t_bin.last_price
                    d["price"] = t_bin.last_price
                    return sym, d
                except Exception:
                    pass

            # 2. Auto / Default routing: Meme coins prioritize Gate.io
            is_meme = is_meme_or_altcoin(sym)
            if is_meme:
                try:
                    t_gate = await order_router.gate.get_ticker(sym)
                    d = t_gate.__dict__.copy()
                    d["venue"] = "gate"
                    d["category"] = "MEME_ALTCOIN"
                    d["last"] = t_gate.last_price
                    d["price"] = t_gate.last_price
                    return sym, d
                except Exception:
                    pass

            # 3. Mainstream / Auto: OKX and Binance
            t_okx = None
            t_bin = None
            try:
                t_okx = await order_router.okx.get_ticker(sym)
            except Exception:
                pass
            try:
                t_bin = await order_router.binance.get_ticker(sym)
            except Exception:
                pass

            if t_okx and t_bin:
                avg_price = (t_okx.last_price + t_bin.last_price) / 2.0
                d = {
                    "venue": "agg",
                    "category": "MAINSTREAM",
                    "symbol": sym,
                    "inst_id": f"{sym}-AGG",
                    "last_price": avg_price,
                    "last": avg_price,
                    "price": avg_price,
                    "bid_price": max(t_okx.bid_price, t_bin.bid_price),
                    "ask_price": min(t_okx.ask_price, t_bin.ask_price),
                    "volume_24h_usd": t_okx.volume_24h_usd + t_bin.volume_24h_usd,
                    "high_24h": max(t_okx.high_24h, t_bin.high_24h),
                    "low_24h": min(t_okx.low_24h, t_bin.low_24h),
                    "timestamp_ms": max(t_okx.timestamp_ms, t_bin.timestamp_ms)
                }
                return sym, d
            elif t_okx:
                d = t_okx.__dict__.copy()
                d["venue"] = "agg"
                d["last"] = t_okx.last_price
                d["price"] = t_okx.last_price
                return sym, d
            elif t_bin:
                d = t_bin.__dict__.copy()
                d["venue"] = "agg"
                d["last"] = t_bin.last_price
                d["price"] = t_bin.last_price
                return sym, d
            return sym, None

        results = await asyncio.gather(*[_fetch_smart_agg(s) for s in symbols])
        return {sym: d for sym, d in results if d is not None}

    # Direct venue requests (okx, binance, gate)
    adapter = order_router.get_adapter(v_clean)
    alt_venue = "binance" if v_clean == "okx" else ("okx" if v_clean == "binance" else "okx")
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
async def get_ticker(symbol: str, venue: str = Query("okx", description="okx | binance | gate | agg")):
    v_clean = venue.lower().strip()
    if v_clean in ("agg", "smart_agg"):
        if is_meme_or_altcoin(symbol):
            adapter = order_router.gate
        else:
            adapter = order_router.okx
    else:
        adapter = order_router.get_adapter(v_clean)

    try:
        data = await adapter.get_ticker(symbol)
        d = data.__dict__.copy()
        d["last"] = data.last_price
        d["price"] = data.last_price
        return d
    except Exception as e:
        # Fallback to alternate venue
        try:
            alt_venue = "binance" if v_clean == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            data = await alt_adapter.get_ticker(symbol)
            d = data.__dict__.copy()
            d["last"] = data.last_price
            d["price"] = data.last_price
            return d
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/klines")
async def get_klines(
    symbol: str = Query("BTC", description="Symbol name (e.g. BTC, ETH, SOL, PEPE)"),
    interval: str = Query("5m", description="5m | 15m | 1h | 4h | 1d | 15d"),
    venue: str = Query("okx", description="okx | binance | gate | agg | smart_agg"),
    limit: int = Query(150, ge=20, le=500)
):
    """
    Exchange-grade candlestick data endpoint supporting 5m to 15d intervals,
    volume histograms, and pre-computed technical indicators (MA7, MA25, MA99, BOLL).
    Supports smart category routing (Gate for Meme/Altcoin, OKX/Binance for Mainstream).
    """
    v_clean = venue.lower().strip()
    inst = universe_manager.get_instrument(symbol)
    inst_venue = str(inst.get("venue") or "auto").lower().strip() if inst else "auto"

    if v_clean in ("agg", "smart_agg"):
        if inst_venue in ("okx", "binance", "gate"):
            target_venue = inst_venue
        elif is_meme_or_altcoin(symbol):
            target_venue = "gate"
        else:
            target_venue = "okx"
    elif v_clean in ("okx", "binance", "gate"):
        target_venue = v_clean
    else:
        target_venue = "okx"

    adapter = order_router.get_adapter(target_venue)
    alt_venue = "binance" if target_venue == "okx" else "okx"
    alt_adapter = order_router.get_adapter(alt_venue)

    candles = None
    used_venue = target_venue
    try:
        candles = await adapter.get_candles(symbol, timeframe=interval, limit=limit)
    except Exception:
        try:
            candles = await alt_adapter.get_candles(symbol, timeframe=interval, limit=limit)
            used_venue = alt_venue
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch {interval} klines for {symbol}: {e}")

    if not candles:
        raise HTTPException(status_code=404, detail=f"No candlestick data returned for {symbol}")

    formatted_candles = []
    volume_data = []
    for c in candles:
        t_sec = c["timestamp"] // 1000
        formatted_candles.append({
            "time": t_sec,
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"]
        })
        is_up = c["close"] >= c["open"]
        volume_data.append({
            "time": t_sec,
            "value": c["volume"],
            "color": "rgba(34, 197, 94, 0.55)" if is_up else "rgba(239, 68, 68, 0.55)"
        })

    ma7 = _calculate_ma_series(candles, 7)
    ma25 = _calculate_ma_series(candles, 25)
    ma99 = _calculate_ma_series(candles, 99)
    boll = _calculate_boll_series(candles, 20, 2.0)

    first_close = candles[0]["close"]
    last_close = candles[-1]["close"]
    change_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0.0

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "venue": used_venue,
        "count": len(formatted_candles),
        "candles": formatted_candles,
        "volumes": volume_data,
        "indicators": {
            "ma7": ma7,
            "ma25": ma25,
            "ma99": ma99,
            "boll": boll
        },
        "stats": {
            "last": last_close,
            "open": candles[-1]["open"],
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "change_pct": round(change_pct, 2),
            "total_volume": round(sum(c["volume"] for c in candles), 2)
        }
    }


@router.get("/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "15m", limit: int = 100, venue: str = "okx"):
    v_clean = venue.lower().strip()
    inst = universe_manager.get_instrument(symbol)
    inst_venue = str(inst.get("venue") or "auto").lower().strip() if inst else "auto"

    if v_clean in ("agg", "smart_agg"):
        if inst_venue in ("okx", "binance", "gate"):
            v_clean = inst_venue
        elif is_meme_or_altcoin(symbol):
            v_clean = "gate"
        else:
            v_clean = "okx"

    adapter = order_router.gate if v_clean == "gate" else order_router.get_adapter(v_clean if v_clean in ("okx", "binance") else "okx")
    try:
        return await adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        try:
            alt_venue = "binance" if v_clean == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            return await alt_adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, depth: int = 20, venue: str = "okx"):
    v_clean = venue.lower().strip()
    adapter = order_router.gate if v_clean == "gate" or (v_clean in ("agg", "smart_agg") and is_meme_or_altcoin(symbol)) else order_router.get_adapter(v_clean if v_clean in ("okx", "binance") else "okx")
    try:
        data = await adapter.get_orderbook(symbol, depth=depth)
        return data.__dict__
    except Exception as e:
        try:
            alt_venue = "binance" if v_clean == "okx" else "okx"
            alt_adapter = order_router.get_adapter(alt_venue)
            data = await alt_adapter.get_orderbook(symbol, depth=depth)
            return data.__dict__
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/factors/{symbol}")
async def get_factors(symbol: str):
    """Computes real-time 5-pillar factor matrix with Gate/OKX/Binance redundancy."""
    is_meme = is_meme_or_altcoin(symbol)
    primary = order_router.gate if is_meme else order_router.okx
    fallback = order_router.okx if is_meme else order_router.binance

    candles = None
    book = None
    rubik = {"long_short_ratio": 1.0}
    funding = {"funding_rate": 0.0001}

    try:
        candles = await primary.get_candles(symbol, timeframe="15m", limit=60)
    except Exception:
        try:
            candles = await fallback.get_candles(symbol, timeframe="15m", limit=60)
        except Exception:
            pass

    try:
        book = await primary.get_orderbook(symbol, depth=20)
    except Exception:
        try:
            book = await fallback.get_orderbook(symbol, depth=20)
        except Exception:
            pass

    try:
        rubik = await order_router.okx.get_rubik_sentiment(symbol)
    except Exception:
        pass

    try:
        funding = await order_router.okx.get_funding_rate(symbol)
    except Exception:
        pass

    if not candles:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market candles for {symbol}")

    imbalance = book.imbalance_ratio if book else 0.0
    matrix = compute_factor_matrix(
        candles_15m=candles,
        orderbook_imbalance=imbalance,
        long_short_ratio=rubik.get("long_short_ratio", 1.0),
        funding_rate=funding.get("funding_rate", 0.0)
    )
    matrix["calculus"] = matrix.get("pillar_1_trend", {})
    return {"symbol": symbol.upper(), "factors": matrix, **matrix}

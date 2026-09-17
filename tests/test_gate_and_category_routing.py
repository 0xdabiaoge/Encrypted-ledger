"""
Test Suite: Gate.io Integration & Category-Based Smart Order Routing
Verifies:
1. Category classification: Mainstream (BTC, ETH, SOL) vs Meme/Altcoins (PEPE, DOGE, BONK, etc.)
2. GateAdapter V4 methods (Ticker, Depth, Candles, Simulated Orders)
3. SmartOrderRouter routing policies: Meme coins routed to Gate.io, Mainstream routed to OKX/Binance
"""
import asyncio
import sys
from pathlib import Path

# Ensure backend directory in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.exchanges.categories import (
    categorize_symbol,
    is_meme_or_altcoin,
    extract_base_asset,
    MAINSTREAM_SYMBOLS,
    KNOWN_MEME_AND_ALTCOINS
)
from app.exchanges.gate import GateAdapter
from app.exchanges.router import SmartOrderRouter


def test_symbol_categorization():
    """Test classification of mainstream vs meme/altcoins."""
    # Mainstream symbols
    assert categorize_symbol("BTC") == "MAINSTREAM"
    assert categorize_symbol("BTC-USDT-SWAP") == "MAINSTREAM"
    assert categorize_symbol("ETHUSDT") == "MAINSTREAM"
    assert categorize_symbol("SOL-USDT") == "MAINSTREAM"
    assert categorize_symbol("BNB") == "MAINSTREAM"
    assert not is_meme_or_altcoin("BTC")
    assert not is_meme_or_altcoin("ETH")

    # Meme & Altcoin symbols
    assert categorize_symbol("PEPE") == "MEME_ALTCOIN"
    assert categorize_symbol("PEPE_USDT") == "MEME_ALTCOIN"
    assert categorize_symbol("DOGE-USDT-SWAP") == "MEME_ALTCOIN"
    assert categorize_symbol("SHIB") == "MEME_ALTCOIN"
    assert categorize_symbol("FLOKI") == "MEME_ALTCOIN"
    assert categorize_symbol("BONK") == "MEME_ALTCOIN"
    assert categorize_symbol("WIF") == "MEME_ALTCOIN"
    assert is_meme_or_altcoin("PEPE")
    assert is_meme_or_altcoin("BONK")
    assert is_meme_or_altcoin("UNKNOWN_MEME_COIN")  # default fallback


async def test_gate_adapter_functionality():
    """Test GateAdapter ticker, orderbook, candles, and simulated execution."""
    gate = GateAdapter(is_demo=True)
    assert gate.capabilities.venue == "gate"
    assert "Gate.io" in gate.capabilities.display_name

    # 1. Ticker fetch
    ticker = await gate.get_ticker("PEPE")
    assert ticker.symbol == "PEPE"
    assert ticker.venue == "gate"
    assert ticker.last_price > 0
    assert ticker.bid_price > 0
    assert ticker.ask_price >= ticker.bid_price

    # 2. Orderbook depth
    depth = await gate.get_orderbook("PEPE", depth=10)
    assert depth.symbol == "PEPE"
    assert depth.venue == "gate"
    assert len(depth.bids) > 0
    assert len(depth.asks) > 0

    # 3. Candlesticks
    candles = await gate.get_candles("PEPE", timeframe="15m", limit=30)
    assert len(candles) > 0
    assert "open" in candles[0]
    assert "close" in candles[0]

    # 4. Simulated Order
    order_res = await gate.place_order(
        symbol="PEPE",
        side="buy",
        order_type="market",
        size=100000.0,
        price=0.000012
    )
    assert order_res["status"] == "filled"
    assert order_res["venue"] == "gate"


async def test_smart_order_router_category_routing():
    """Test SmartOrderRouter sends Meme coins to Gate.io and Mainstream to OKX/Binance."""
    router = SmartOrderRouter()

    # 1. PEPE should route to Gate.io
    chosen_venue, metrics = await router.evaluate_best_execution_venue(
        symbol="PEPE",
        side="buy",
        notional_usd=200.0
    )
    assert chosen_venue == "gate"
    assert metrics.get("category") == "MEME_ALTCOIN"
    assert "Gate.io" in metrics.get("reason", "")

    # 2. DOGE should route to Gate.io
    chosen_venue_doge, metrics_doge = await router.evaluate_best_execution_venue(
        symbol="DOGE",
        side="sell",
        notional_usd=150.0
    )
    assert chosen_venue_doge == "gate"
    assert metrics_doge.get("category") == "MEME_ALTCOIN"

    # 3. BTC should route to OKX or Binance (Mainstream)
    chosen_venue_btc, metrics_btc = await router.evaluate_best_execution_venue(
        symbol="BTC",
        side="buy",
        notional_usd=500.0
    )
    assert chosen_venue_btc in ("okx", "binance")
    assert metrics_btc.get("category") == "MAINSTREAM"

    # 4. Aggregated balances
    agg_bal = await router.get_aggregated_balances()
    assert "total_equity_usd" in agg_bal
    assert "gate" in agg_bal
    assert "okx" in agg_bal
    assert "binance" in agg_bal


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=== [TEST SUITE 1] Gate.io Integration & Category-Based SOR Routing ===")
    test_symbol_categorization()
    print("  ✓ test_symbol_categorization passed successfully")
    asyncio.run(test_gate_adapter_functionality())
    print("  ✓ test_gate_adapter_functionality passed successfully")
    asyncio.run(test_smart_order_router_category_routing())
    print("  ✓ test_smart_order_router_category_routing passed successfully")
    print(">>> All Gate.io & Category Routing tests PASSED! <<<\n")

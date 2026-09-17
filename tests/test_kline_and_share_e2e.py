"""
Encrypted Ledger - E2E Verification for K-Lines (5m-15d), Venues, and Position Sharing
Tests:
1. Market Tickers with venue parameter (okx, binance, agg)
2. Candlestick Klines across 5m, 15m, 1h, 4h, 1d, and 15d (with resampling)
3. Technical Indicators (MA7, MA25, MA99, Bollinger Bands)
4. Position Sharing creation and public showcase retrieval with strict data masking
"""
import sys
import io
import asyncio
from pathlib import Path

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_market_tickers_and_venues():
    print("\n[STEP 1] Testing Market Tickers with OKX, Binance, and Dual Agg...")
    # OKX
    r_okx = client.get("/api/v1/market/tickers?venue=okx")
    assert r_okx.status_code == 200, f"OKX tickers failed: {r_okx.text}"
    okx_data = r_okx.json()
    assert "BTC" in okx_data
    print(f"  ✓ OKX Tickers: BTC last={okx_data['BTC']['last_price']}")

    # Binance
    r_bin = client.get("/api/v1/market/tickers?venue=binance")
    assert r_bin.status_code == 200, f"Binance tickers failed: {r_bin.text}"
    bin_data = r_bin.json()
    assert "BTC" in bin_data
    print(f"  ✓ Binance Tickers: BTC last={bin_data['BTC']['last_price']}")

    # Smart Dual Aggregation
    r_agg = client.get("/api/v1/market/tickers?venue=agg")
    assert r_agg.status_code == 200, f"Agg tickers failed: {r_agg.text}"
    agg_data = r_agg.json()
    assert "BTC" in agg_data
    assert agg_data["BTC"]["venue"] == "agg"
    print(f"  ✓ Smart Dual Aggregator: BTC agg_price={agg_data['BTC']['last_price']}")


def test_klines_intervals_and_indicators():
    print("\n[STEP 2] Testing Exchange Candlestick Klines (5m to 15d) & Indicators...")
    intervals = ["5m", "15m", "1h", "4h", "1d", "15d"]
    
    for interval in intervals:
        resp = client.get(f"/api/v1/market/klines?symbol=BTC&interval={interval}&limit=50")
        assert resp.status_code == 200, f"Kline interval {interval} failed: {resp.text}"
        data = resp.json()
        assert data["symbol"] == "BTC"
        assert data["interval"] == interval
        assert len(data["candles"]) > 0, f"No candles for {interval}"
        
        # Check candle schema: time, open, high, low, close
        c0 = data["candles"][0]
        assert "time" in c0 and "open" in c0 and "high" in c0 and "low" in c0 and "close" in c0
        assert "volumes" in data and len(data["volumes"]) > 0
        
        # Check pre-computed indicators
        indicators = data["indicators"]
        assert "ma7" in indicators
        assert "ma25" in indicators
        assert "ma99" in indicators
        assert "boll" in indicators
        
        stats = data["stats"]
        print(f"  ✓ Interval [{interval:4s}]: {len(data['candles'])} bars | Last: ${stats['last']} | Chg: {stats['change_pct']}% | MA7 points: {len(indicators['ma7'])}")


def test_position_sharing_lifecycle():
    print("\n[STEP 3] Testing User Position Share Creation & Public Masked Retrieval...")
    
    # 1. Create a position share
    payload = {
        "symbol": "BTC-USDT-SWAP",
        "side": "LONG",
        "leverage": "5.0x",
        "entry_price": 64200.5,
        "mark_price": 76550.0,
        "unrealized_pnl_ratio": 0.2845,
        "venue": "okx",
        "council_insight": "顺应 4H 宏观大势通道，微积分加速度 (v>0, a>0) 爆发，CIO 全票核准。"
    }
    
    create_resp = client.post("/api/v1/trading/share/create", json=payload)
    assert create_resp.status_code == 200, f"Share create failed: {create_resp.text}"
    create_data = create_resp.json()
    assert create_data["status"] == "success"
    share = create_data["share"]
    share_id = share["share_id"]
    assert share_id.startswith("EL-SH")
    assert share["roi_pct"] == "+28.45%"
    assert share["is_masked"] is True
    print(f"  ✓ Share created: ID={share_id}, Trader={share['trader_alias']}, ROI={share['roi_pct']}")

    # 2. Retrieve the shared position publicly without auth
    get_resp = client.get(f"/api/v1/trading/share/{share_id}")
    assert get_resp.status_code == 200, f"Share get failed: {get_resp.text}"
    fetched = get_resp.json()["share"]
    assert fetched["share_id"] == share_id
    assert fetched["symbol"] == "BTC-USDT-SWAP"
    assert fetched["entry_price"] == 64200.5
    assert fetched["mark_price"] == 76550.0
    assert "total_equity" not in fetched
    assert "api_key" not in fetched
    print(f"  ✓ Public showcase retrieval verified without leaking account balance or keys.")

    # 3. List recent shares
    list_resp = client.get("/api/v1/trading/shares")
    assert list_resp.status_code == 200
    shares = list_resp.json()["shares"]
    assert any(s["share_id"] == share_id for s in shares)
    print(f"  ✓ Listed {len(shares)} total shared positions in store.")


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 RUNNING KLINES (5m-15d), DATA VENUES & POSITION SHARING E2E TEST")
    print("=" * 70)
    test_market_tickers_and_venues()
    test_klines_intervals_and_indicators()
    test_position_sharing_lifecycle()
    print("\n" + "=" * 70)
    print("🎉 ALL KLINE, VENUE & POSITION SHARING TESTS PASSED 100%!")
    print("=" * 70)

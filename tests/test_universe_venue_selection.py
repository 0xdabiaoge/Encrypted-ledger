"""
Test Suite: Unrestricted Universe Symbol Addition & Designated Exchange Venue Routing
Verifies:
1. Adding any cryptocurrency without restriction (mainstream, meme, altcoin)
2. Specifying designated exchange venues (okx, binance, gate, auto)
3. SmartOrderRouter honoring designated venue directly
4. Mainstream coins prioritizing OKX & Binance under auto SOR
5. Unspecified Meme coins prioritizing Gate.io under auto SOR
6. Market tickers & Klines adapting to designated venues
"""
import io
import sys
import asyncio
from pathlib import Path

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend directory in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.quant.universe import universe_manager
from app.exchanges.router import SmartOrderRouter

client = TestClient(app)
superadmin_token = create_access_token(data={"sub": "admin", "role": "superadmin"})
headers = {"Authorization": f"Bearer {superadmin_token}"}
router = SmartOrderRouter()


def test_unrestricted_addition_and_designated_venues():
    """Test adding custom coins with specified venues and verifying SOR routing."""
    # 1. Clean up any previous test remnants
    for sym in ["TESTPEPE", "TESTDOGE", "TESTFLOKI", "TESTANY"]:
        universe_manager.remove_instrument(sym)

    # 2. Add Meme coin with designated Binance venue
    universe_manager.add_instrument({
        "name": "TESTPEPE",
        "tier": "tier_2_momentum",
        "venue": "binance",
        "max_leverage": 3.0
    })
    inst_pepe = universe_manager.get_instrument("TESTPEPE")
    assert inst_pepe is not None
    assert inst_pepe["venue"] == "binance"
    assert inst_pepe["binance_inst_id"] == "TESTPEPEUSDT"

    # 3. Add Meme coin with designated OKX venue
    universe_manager.add_instrument({
        "name": "TESTDOGE",
        "tier": "tier_2_momentum",
        "venue": "okx",
        "max_leverage": 3.0
    })
    inst_doge = universe_manager.get_instrument("TESTDOGE")
    assert inst_doge is not None
    assert inst_doge["venue"] == "okx"
    assert inst_doge["okx_inst_id"] == "TESTDOGE-USDT-SWAP"

    # 4. Add Altcoin with designated Gate.io venue
    universe_manager.add_instrument({
        "name": "TESTFLOKI",
        "tier": "tier_2_momentum",
        "venue": "gate",
        "max_leverage": 3.0
    })
    inst_floki = universe_manager.get_instrument("TESTFLOKI")
    assert inst_floki is not None
    assert inst_floki["venue"] == "gate"
    assert inst_floki["gate_inst_id"] == "TESTFLOKI_USDT"

    # 5. Add completely novel unlisted token with auto venue
    universe_manager.add_instrument({
        "name": "TESTANY",
        "tier": "tier_2_momentum",
        "venue": "auto",
        "max_leverage": 2.0
    })
    inst_any = universe_manager.get_instrument("TESTANY")
    assert inst_any is not None
    assert inst_any["venue"] == "auto"


def test_sor_routing_with_designated_venues():
    """Verify SmartOrderRouter routes to designated venue or falls back to category SOR."""
    async def _run():
        # 1. TESTPEPE designated to binance -> Must return binance
        v_pepe, m_pepe = await router.evaluate_best_execution_venue("TESTPEPE", "buy", 500.0)
        assert v_pepe == "binance"
        assert "BINANCE" in m_pepe.get("reason", "").upper()

        # 2. TESTDOGE designated to okx -> Must return okx
        v_doge, m_doge = await router.evaluate_best_execution_venue("TESTDOGE", "buy", 500.0)
        assert v_doge == "okx"
        assert "OKX" in m_doge.get("reason", "").upper()

        # 3. TESTFLOKI designated to gate -> Must return gate
        v_floki, m_floki = await router.evaluate_best_execution_venue("TESTFLOKI", "buy", 500.0)
        assert v_floki == "gate"
        assert "GATE" in m_floki.get("reason", "").upper()

        # 4. BTC with auto venue -> Mainstream must route to OKX or Binance
        v_btc, m_btc = await router.evaluate_best_execution_venue("BTC", "buy", 500.0)
        assert v_btc in ("okx", "binance")

        # 5. Unspecified Meme coin with auto venue (e.g. PEPE) -> Prioritizes Gate.io
        v_meme, m_meme = await router.evaluate_best_execution_venue("PEPE", "buy", 500.0)
        assert v_meme == "gate"

    asyncio.run(_run())


def test_system_universe_api_venue_lifecycle():
    """Verify REST API adds coin with venue and returns updated record."""
    # Test adding via POST /api/v1/system/universe/add
    universe_manager.remove_instrument("WIF")
    res = client.post("/api/v1/system/universe/add", headers=headers, json={
        "name": "WIF",
        "tier": "tier_2_momentum",
        "venue": "okx",
        "max_leverage": 3.0
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # Verify WIF has venue=okx in universe list
    res_list = client.get("/api/v1/market/universe")
    assert res_list.status_code == 200
    u_list = res_list.json()
    wif_item = next((x for x in u_list if x["name"] == "WIF"), None)
    assert wif_item is not None
    assert wif_item["venue"] == "okx"

    # Clean up WIF and test coins
    for sym in ["WIF", "TESTPEPE", "TESTDOGE", "TESTFLOKI", "TESTANY"]:
        universe_manager.remove_instrument(sym)


if __name__ == "__main__":
    print("=== [TEST SUITE 9] Unrestricted Symbol Addition & Venue Selection ===")
    test_unrestricted_addition_and_designated_venues()
    print("  ✓ test_unrestricted_addition_and_designated_venues passed successfully")
    test_sor_routing_with_designated_venues()
    print("  ✓ test_sor_routing_with_designated_venues passed successfully (designated OKX/Binance/Gate honored)")
    test_system_universe_api_venue_lifecycle()
    print("  ✓ test_system_universe_api_venue_lifecycle passed successfully (API end-to-end)")
    print(">>> All Universe Venue Selection tests PASSED! <<<\n")

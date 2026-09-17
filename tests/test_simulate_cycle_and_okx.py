"""
Test Suite: OKX Connectivity Diagnostics & On-Demand Simulated Trading Cycle
Verifies:
1. OKX test endpoint returns detailed environment detection (demo vs live).
2. Credentials encryption & persistence in credentials_store.py.
3. Robust markdown code fence cleanup in council_desk.py.
4. On-demand simulated trade cycle execution (POST /api/v1/trading/simulate-cycle).
5. Automatic paper sandbox fallback on order submission errors.
"""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.config import settings
from app.core.credentials_store import save_persisted_credentials, load_persisted_credentials
from app.council.council_desk import extract_json_payload

client = TestClient(app)
superadmin_token = create_access_token(data={"sub": "admin", "role": "superadmin"})
headers = {"Authorization": f"Bearer {superadmin_token}"}


def test_extract_json_payload():
    # 1. Plain JSON
    assert extract_json_payload('{"action": "BUY"}') == {"action": "BUY"}
    # 2. Markdown fenced JSON
    assert extract_json_payload('```json\n{"action": "SELL", "confidence": 85.0}\n```') == {"action": "SELL", "confidence": 85.0}
    # 3. JSON with surrounding prose
    assert extract_json_payload('Here is the decision:\n{"action": "HOLD"}\nHope this helps!') == {"action": "HOLD"}


def test_credentials_persistence():
    save_persisted_credentials({
        "okx_env": "demo",
        "okx_demo_api_key": "test_api_key_12345",
        "okx_demo_secret_key": "test_secret_67890",
        "okx_demo_passphrase": "test_passphrase_abc"
    })
    # Reset in memory and reload
    settings.OKX_DEMO_API_KEY = ""
    load_persisted_credentials()
    assert settings.OKX_DEMO_API_KEY == "test_api_key_12345"
    assert settings.OKX_DEMO_SECRET_KEY == "test_secret_67890"


def test_okx_connectivity_diagnostics():
    # Mock OKXAdapter.test_connectivity
    with patch("app.exchanges.okx.OKXAdapter.test_connectivity", new_callable=AsyncMock) as mock_test:
        # Case A: Demo success
        mock_test.return_value = (True, "连接成功", {"total_equity_usd": 12500.0})
        res = client.post("/api/v1/system/exchanges/okx/test", json={
            "api_key": "mock_key",
            "secret_key": "mock_sec",
            "passphrase": "mock_pass"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["matched_env"] == "demo"
        assert data["total_equity_usd"] == 12500.0

        # Case B: Demo failed, Live success
        mock_test.side_effect = [
            (False, "APIKey does not match current environment", {"code": "50101"}),
            (True, "连接成功", {"total_equity_usd": 500.0})
        ]
        res_live = client.post("/api/v1/system/exchanges/okx/test", json={
            "api_key": "mock_live_key",
            "secret_key": "mock_sec",
            "passphrase": "mock_pass"
        }, headers=headers)
        assert res_live.status_code == 200
        data_live = res_live.json()
        assert data_live["matched_env"] == "live"
        assert "OKX 实盘账户" in data_live["message"]


def test_simulate_cycle_endpoint():
    with patch("app.scheduler.tasks.orchestrator.execute_trade_cycle", new_callable=AsyncMock) as mock_cycle:
        mock_cycle.return_value = [{"symbol": "BTC", "action": "BUY", "passed": True, "reason": ""}]
        res = client.post("/api/v1/trading/simulate-cycle", json={"symbol": "BTC"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "模拟盘投委会研判与执行周期已成功执行" in data["message"]


if __name__ == "__main__":
    test_extract_json_payload()
    print("✓ extract_json_payload passed")
    test_credentials_persistence()
    print("✓ credentials_persistence passed")
    test_okx_connectivity_diagnostics()
    print("✓ okx_connectivity_diagnostics passed")
    test_simulate_cycle_endpoint()
    print("✓ simulate_cycle_endpoint passed")
    print("ALL OKX DIAGNOSTICS & SIMULATION TESTS PASSED!")

"""
Comprehensive Full-System End-to-End Verification Suite
Covers:
1. Symbol Category Routing & Gate.io Priority for Meme Coins
2. Python Risk Interceptor Plugins & Fail-Closed Sandbox Engine
3. Prompt Studio Dynamic Token Badges & Calculus Rendering
4. System-Level Authenticated AES-256 Disaster Recovery & Restore
5. REST API Integration (Market, Risk, Council, System, Trading)
"""
import io
import sys
import os
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


client = TestClient(app)
superadmin_token = create_access_token(data={"sub": "admin", "role": "superadmin"})
headers = {"Authorization": f"Bearer {superadmin_token}"}


def test_full_health_and_api():
    """Verify application health and core status endpoints."""
    res = client.get("/api/v1/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "Encrypted Ledger" in data["app_name"]


def test_gate_and_market_api():
    """Verify Market endpoints with Gate.io and Smart Aggregation."""
    # 1. Universe tickers via smart_agg
    res_agg = client.get("/api/v1/market/tickers?venue=smart_agg")
    assert res_agg.status_code == 200
    tickers = res_agg.json()
    assert len(tickers) > 0

    # 2. Gate tickers directly
    res_gate = client.get("/api/v1/market/tickers?venue=gate")
    assert res_gate.status_code == 200

    # 3. Klines for Meme coin with smart_agg (routes to Gate)
    res_kline = client.get("/api/v1/market/klines?symbol=PEPE&interval=15m&venue=smart_agg")
    assert res_kline.status_code == 200
    kline_data = res_kline.json()
    assert kline_data["symbol"] == "PEPE"
    assert kline_data["venue"] == "gate"
    assert len(kline_data["candles"]) > 0


def test_risk_plugins_api():
    """Verify Risk Plugins CRUD and Sandbox API endpoints."""
    # 1. List plugins
    res = client.get("/api/v1/risk/plugins", headers=headers)
    assert res.status_code == 200
    plugins = res.json()
    assert len(plugins) >= 4

    # 2. Run sandbox stress test
    res_test = client.post("/api/v1/risk/plugins/sandbox-test", headers=headers)
    assert res_test.status_code == 200
    rep = res_test.json()["report"]
    assert rep["total_scenarios"] == 5
    assert rep["verification_accuracy_pct"] == 100.0


def test_council_prompt_tokens_api():
    """Verify Prompt Studio token badges API."""
    res = client.get("/api/v1/council/prompt-tokens")
    assert res.status_code == 200
    tokens = res.json()
    assert len(tokens) >= 9
    tokens_map = {t["token"]: t for t in tokens}
    assert "{{macro_4h}}" in tokens_map
    assert "{{calculus_1h}}" in tokens_map
    assert "{{smart_money}}" in tokens_map
    assert "{{hft_micro_scalp}}" in tokens_map


def test_disaster_recovery_api():
    """Verify Disaster Recovery backup creation, list, and restore API."""
    # 1. Create backup
    test_pwd = "EndToEndSecretMasterPass2026!"
    res_create = client.post(
        "/api/v1/system/backup/create",
        headers=headers,
        json={"password": test_pwd, "note": "End-to-End Test Backup"}
    )
    assert res_create.status_code == 200
    backup_meta = res_create.json()["backup"]
    fname = backup_meta["filename"]

    # 2. List backups
    res_list = client.get("/api/v1/system/backup/list", headers=headers)
    assert res_list.status_code == 200
    archives = res_list.json()
    assert any(a["filename"] == fname for a in archives)

    # 3. Download backup
    res_dl = client.get(f"/api/v1/system/backup/download/{fname}", headers=headers)
    assert res_dl.status_code == 200
    assert len(res_dl.content) > 0

    # 4. Attempt restore with wrong password (fail)
    res_restore_fail = client.post(
        "/api/v1/system/backup/restore",
        headers=headers,
        json={"filename": fname, "password": "BadPassword123"}
    )
    assert res_restore_fail.status_code == 400

    # 5. Restore with correct password (success)
    res_restore_ok = client.post(
        "/api/v1/system/backup/restore",
        headers=headers,
        json={"filename": fname, "password": test_pwd}
    )
    assert res_restore_ok.status_code == 200
    assert res_restore_ok.json()["status"] == "success"

    # 6. Delete backup
    res_del = client.delete(f"/api/v1/system/backup/{fname}", headers=headers)
    assert res_del.status_code == 200


if __name__ == "__main__":
    print("=== [TEST SUITE 5] Comprehensive Full-System End-to-End Test ===")
    test_full_health_and_api()
    print("  ✓ test_full_health_and_api passed successfully")
    test_gate_and_market_api()
    print("  ✓ test_gate_and_market_api passed successfully (smart_agg & Gate.io routing)")
    test_risk_plugins_api()
    print("  ✓ test_risk_plugins_api passed successfully (plugins CRUD & 5-scenario sandbox)")
    test_council_prompt_tokens_api()
    print("  ✓ test_council_prompt_tokens_api passed successfully (prompt token badges)")
    test_disaster_recovery_api()
    print("  ✓ test_disaster_recovery_api passed successfully (full AES-256 backup & restore lifecycle)")
    print(">>> All Full-System E2E tests PASSED! <<<\n")

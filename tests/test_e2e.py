import asyncio
import os
import sys
from pathlib import Path

# Force UTF-8 on Windows stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from app.main import app


async def main():
    print("[TEST] Starting End-to-End System Integration Test with Lifespan...")
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Root SPA
            r_root = await client.get("/")
            print(f"1. GET / -> Status: {r_root.status_code} | HTML Size: {len(r_root.text)} bytes")
            assert r_root.status_code == 200
            assert "ENCRYPTED LEDGER" in r_root.text

            # 2. System Health
            r_health = await client.get("/api/v1/system/health")
            print(f"2. GET /api/v1/system/health -> Status: {r_health.status_code} | Payload: {r_health.json()}")
            assert r_health.status_code == 200
            assert r_health.json()["status"] == "healthy"

            # 3. Market Universe
            r_univ = await client.get("/api/v1/market/universe")
            univ = r_univ.json()
            print(f"3. GET /api/v1/market/universe -> Status: {r_univ.status_code} | Count: {len(univ)} coins")
            assert r_univ.status_code == 200
            assert len(univ) == 10

            # 4. Admin Login to get Bearer Token
            r_login = await client.post("/api/v1/auth/login", json={
                "username": "admin",
                "password": "Admin123!@#"
            })
            print(f"4. POST /api/v1/auth/login -> Status: {r_login.status_code}")
            assert r_login.status_code == 200
            token = r_login.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            # 5. Circuit Breaker
            r_cb = await client.get("/api/v1/risk/circuit-breaker")
            cb = r_cb.json()
            print(f"5. GET /api/v1/risk/circuit-breaker -> Status: {r_cb.status_code} | Active: {cb.get('active')}")
            assert r_cb.status_code == 200

            # 6. Macro Intelligence News
            r_news = await client.get("/api/v1/intelligence/news")
            news = r_news.json()
            print(f"6. GET /api/v1/intelligence/news -> Status: {r_news.status_code} | Count: {len(news.get('news', []))}")
            assert r_news.status_code == 200

            # 7. Active Policy
            r_policy = await client.get("/api/v1/council/policy/active")
            pol = r_policy.json()
            print(f"7. GET /api/v1/council/policy/active -> Status: {r_policy.status_code} | Tag: {pol.get('version_tag')} | Hash: {pol.get('sha256_hash')[:16]}")
            assert r_policy.status_code == 200

            # 8. Physical Interceptor Simulation (With Admin Auth)
            r_sandbox = await client.post("/api/v1/risk/sandbox/simulate", headers=auth_headers, json={
                "symbol": "BTC",
                "side": "buy",
                "entry_price": 65000.0,
                "stop_loss_price": 64000.0,
                "take_profit_price": 67500.0,
                "confidence": 85.0,
                "notional_usd": 300.0,
                "leverage": 3.0,
                "account_balance_usd": 1000.0
            })
            print(f"8. POST /api/v1/risk/sandbox/simulate -> Status: {r_sandbox.status_code} | Passed: {r_sandbox.json().get('passed')}")
            assert r_sandbox.status_code == 200
            assert r_sandbox.json().get("passed") is True

            # 9. Dynamic Instrument Addition
            r_add = await client.post("/api/v1/system/universe/add", headers=auth_headers, json={
                "name": "AVAX",
                "tier": "tier_2_momentum",
                "max_leverage": 3.0
            })
            print(f"9. POST /api/v1/system/universe/add -> Status: {r_add.status_code} | Res: {r_add.json()}")
            assert r_add.status_code == 200

            # Verify universe expanded to 11 coins
            r_univ2 = await client.get("/api/v1/market/universe")
            assert len(r_univ2.json()) == 11
            print(f"10. Dynamic Universe verified: Pool size now = {len(r_univ2.json())}")

            # Clean up test coin
            await client.delete("/api/v1/system/universe/AVAX", headers=auth_headers)

            print("\n[SUCCESS] ALL 10 END-TO-END INTEGRATION TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
from pathlib import Path

# Force UTF-8 on Windows stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from app.main import app
from app.core.config import settings
from app.council.council_desk import council_desk
from app.notifications.telegram_bot import telegram_bot
from app.intelligence.circuit_breaker import circuit_breaker


async def test_commercial_e2e():
    print("======================================================================")
    print("🚀 STARTING COMMERCIAL MEMBERSHIP, MASKING, COUNCIL & TELEGRAM E2E TEST")
    print("======================================================================")

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # ------------------------------------------------------------------
            # 1. Public Showcase & Security Data Masking
            # ------------------------------------------------------------------
            print("\n[STEP 1] Testing Unauthenticated Data Masking (Public Showcase)...")
            
            # 1.1 Unauthenticated positions query
            r_pos = await client.get("/api/v1/trading/positions")
            assert r_pos.status_code == 200, f"Positions status: {r_pos.status_code}"
            pos_data = r_pos.json()
            assert pos_data.get("is_masked") is True, "is_masked flag must be True for unauthenticated requests"
            print(f"  ✓ GET /api/v1/trading/positions (Public): count={len(pos_data.get('positions', []))}, is_masked={pos_data.get('is_masked')}")
            for p in pos_data.get("positions", []):
                assert p.get("size") == "***", "Position size must be masked"
                assert p.get("notional_usd") is None, "Position notional must be None"
                assert p.get("unrealized_pnl_usd") is None, "Position PnL must be masked"

            # 1.2 Unauthenticated balance query
            r_bal = await client.get("/api/v1/trading/balance")
            assert r_bal.status_code == 200
            bal_data = r_bal.json()
            assert bal_data.get("is_masked") is True, "Balance must be masked"
            assert "display_scale" in bal_data, "Display scale must be provided"
            assert bal_data.get("total_equity_usd") == 0.0, "Total equity must not leak in public view"
            print(f"  ✓ GET /api/v1/trading/balance (Public): display_scale={bal_data.get('display_scale')}, is_masked={bal_data.get('is_masked')}")

            # 1.3 Unauthenticated ledger entries query
            r_led = await client.get("/api/v1/ledger/entries")
            assert r_led.status_code == 200
            entries = r_led.json()
            assert isinstance(entries, list)
            print(f"  ✓ GET /api/v1/ledger/entries (Public): entries_count={len(entries)}")
            for entry in entries:
                assert entry.get("fill_qty") == "***" or entry.get("notional_usd") is None

            # 1.4 Unauthenticated access to credentials must be blocked
            r_cred_anon = await client.get("/api/v1/system/credentials")
            assert r_cred_anon.status_code in (401, 403), "Unauthenticated credentials request must be blocked"
            print(f"  ✓ GET /api/v1/system/credentials without auth -> Blocked ({r_cred_anon.status_code})")

            # ------------------------------------------------------------------
            # 2. Admin Authentication & Transparent Verification
            # ------------------------------------------------------------------
            print("\n[STEP 2] Testing Superadmin Login & Transparent Access...")
            r_login = await client.post("/api/v1/auth/login", json={
                "username": "admin",
                "password": "Admin123!@#"
            })
            assert r_login.status_code == 200
            admin_token = r_login.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            print(f"  ✓ POST /api/v1/auth/login -> Superadmin token acquired")

            # Admin positions query (unmasked)
            r_pos_admin = await client.get("/api/v1/trading/positions", headers=admin_headers)
            assert r_pos_admin.status_code == 200
            pos_admin_data = r_pos_admin.json()
            assert pos_admin_data.get("is_masked") is False, "Admin must see unmasked positions"
            print(f"  ✓ GET /api/v1/trading/positions (Admin): is_masked={pos_admin_data.get('is_masked')}")

            # Admin credentials query (safe-masked values returned)
            r_cred_admin = await client.get("/api/v1/system/credentials", headers=admin_headers)
            assert r_cred_admin.status_code == 200
            cred_data = r_cred_admin.json()
            print(f"  ✓ GET /api/v1/system/credentials (Admin): OKX masked key={cred_data.get('okx_api_key')}")

            # ------------------------------------------------------------------
            # 3. Commercial Member System & Invite Code Lifecycle
            # ------------------------------------------------------------------
            print("\n[STEP 3] Testing Commercial Registration & Invite Codes...")
            
            # 3.1 Check registration mode
            r_mode = await client.get("/api/v1/auth/registration-mode")
            assert r_mode.status_code == 200
            print(f"  ✓ Current registration mode: {r_mode.json().get('registration_mode')}")

            # Set mode to open first
            r_set_open = await client.post("/api/v1/auth/registration-mode", headers=admin_headers, json={"mode": "open"})
            assert r_set_open.status_code == 200
            assert r_set_open.json()["registration_mode"] == "open"
            print("  ✓ Switched registration mode to 'open'")

            # Register a standard member in open mode
            test_username = f"vip_trader_{int(asyncio.get_event_loop().time())}"
            r_reg_open = await client.post("/api/v1/auth/register", json={
                "username": test_username,
                "password": "Password123!@#",
                "telegram_chat_id": "987654321"
            })
            assert r_reg_open.status_code == 200
            print(f"  ✓ Registered new member '{test_username}' in open mode")

            # Log in as the new member
            r_user_login = await client.post("/api/v1/auth/login", json={
                "username": test_username,
                "password": "Password123!@#"
            })
            assert r_user_login.status_code == 200
            user_token = r_user_login.json()["access_token"]
            user_headers = {"Authorization": f"Bearer {user_token}"}
            print(f"  ✓ Logged in as member '{test_username}', role={r_user_login.json().get('role')}")

            # Verify that regular members still get masked data on positions
            r_pos_user = await client.get("/api/v1/trading/positions", headers=user_headers)
            assert r_pos_user.json().get("is_masked") is True, "Regular member must see masked positions"
            print("  ✓ Verified member sees masked positions (is_masked=True)")

            # Verify regular member CANNOT manage invite codes
            r_user_codes = await client.get("/api/v1/auth/invite-codes", headers=user_headers)
            assert r_user_codes.status_code == 403, "Regular member must not access invite codes"
            print("  ✓ Verified member is forbidden from invite code management (403)")

            # 3.2 Switch mode to invite_only
            r_set_invite = await client.post("/api/v1/auth/registration-mode", headers=admin_headers, json={"mode": "invite_only"})
            assert r_set_invite.status_code == 200
            assert r_set_invite.json()["registration_mode"] == "invite_only"
            print("  ✓ Switched registration mode to 'invite_only'")

            # Attempt to register without invite code in invite_only mode -> Should fail
            r_reg_no_code = await client.post("/api/v1/auth/register", json={
                "username": f"fail_user_{int(asyncio.get_event_loop().time())}",
                "password": "Password123!@#"
            })
            assert r_reg_no_code.status_code == 400
            print(f"  ✓ Registration without invite code rejected: {r_reg_no_code.json()['detail']}")

            # Admin creates a single-use invite code
            r_create_code = await client.post("/api/v1/auth/invite-codes", headers=admin_headers, json={
                "max_uses": 1,
                "note": "VIP One-Time Test Code"
            })
            assert r_create_code.status_code == 200
            invite_code_str = r_create_code.json()["code"]
            print(f"  ✓ Admin generated invite code: {invite_code_str} (max_uses: 1)")

            # Register with the new invite code
            test_vip_user = f"vip_invited_{int(asyncio.get_event_loop().time())}"
            r_reg_with_code = await client.post("/api/v1/auth/register", json={
                "username": test_vip_user,
                "password": "Password123!@#",
                "invite_code": invite_code_str
            })
            assert r_reg_with_code.status_code == 200
            print(f"  ✓ Successfully registered member '{test_vip_user}' with invite code")

            # Try to register a second user with the same single-use code -> Should fail
            r_reg_reuse = await client.post("/api/v1/auth/register", json={
                "username": f"vip_reuse_{int(asyncio.get_event_loop().time())}",
                "password": "Password123!@#",
                "invite_code": invite_code_str
            })
            assert r_reg_reuse.status_code == 400
            print(f"  ✓ Re-use of exhausted invite code correctly rejected: {r_reg_reuse.json()['detail']}")

            # Clean up: Admin revokes the test code
            r_del_code = await client.delete(f"/api/v1/auth/invite-codes/{invite_code_str}", headers=admin_headers)
            assert r_del_code.status_code == 200
            print(f"  ✓ Admin revoked invite code {invite_code_str}")

            # ------------------------------------------------------------------
            # 4. Multi-Agent Investment Council Architecture
            # ------------------------------------------------------------------
            print("\n[STEP 4] Testing Multi-Agent Hedge Fund Council Desk...")
            
            # 4.1 Get Seats Configuration
            r_seats = await client.get("/api/v1/system/council/seats", headers=admin_headers)
            assert r_seats.status_code == 200
            seats_list = r_seats.json()
            assert len(seats_list) == 5, f"Expected 5 council seats, found {len(seats_list)}"
            seat_names = [s["name"] for s in seats_list]
            print(f"  ✓ Council seats verified (Count=5): {', '.join(seat_names)}")

            # 4.2 Run deliberate simulation on Council Desk
            mock_factors = {
                "pillar_1_trend": {"adx": 28.5, "direction": "BULLISH", "macro_4h_channel": "BULLISH"},
                "pillar_2_momentum": {"velocity": 1.45, "acceleration": 0.32, "rsi": 62.0},
                "pillar_3_microstructure": {"imbalance_ratio": 1.58, "funding_rate": 0.0001},
                "pillar_4_sentiment": {"macro_regime": "RISK_ON", "headline_risk": "LOW"}
            }
            mock_news = [{"headline": "Global liquidity expands as institutional ETF inflows hit record highs", "sentiment": "bullish"}]
            
            deliberation = await council_desk.deliberate_on_instrument(
                symbol="ETH",
                current_price=3500.0,
                factors=mock_factors,
                macro_news=mock_news,
                account_equity=10000.0
            )
            assert "debate_transcript" in deliberation, "Deliberation must include debate_transcript"
            assert len(deliberation["debate_transcript"]) == 4, "Must contain 4 analyst seat opinions"
            assert "action" in deliberation
            assert "confidence" in deliberation
            
            print(f"  ✓ Multi-agent debate executed:")
            for op in deliberation["debate_transcript"]:
                print(f"    - [{op.get('name')}] Proposal: {op['action']} | Confidence: {op['confidence']}%")
            print(f"    ⚖️ [CIO 终审裁决] Action: {deliberation['action']} | Final Confidence: {deliberation['confidence']}% | R:R: {deliberation.get('risk_reward_ratio')}")
            print(f"    📝 Consensus Summary: {deliberation.get('consensus_summary')}")

            # 4.3 Verify debate logged in history API
            r_debates = await client.get("/api/v1/system/council/debates")
            assert r_debates.status_code == 200
            history = r_debates.json()
            assert len(history) >= 1
            print(f"  ✓ Verified debate history API: {len(history)} records in cache")

            # 4.4 Multi-Model Pool Management & Seat Assignment
            print("  ✓ Testing Multi-Model Pool CRUD & Seat Model Assignment...")
            r_models = await client.get("/api/v1/system/llm/models")
            assert r_models.status_code == 200
            models_list = r_models.json()
            assert isinstance(models_list, list)
            print(f"    - Current model pool count: {len(models_list)}")

            # Admin adds a new model (e.g. DeepSeek V3)
            r_add_model = await client.post("/api/v1/system/llm/models", headers=admin_headers, json={
                "name": "DeepSeek V3 Reasoning",
                "provider": "DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "api_key": "sk-deepseek-test-key-123456"
            })
            assert r_add_model.status_code == 200
            created_model = r_add_model.json()["model"]
            created_model_id = created_model["id"]
            assert created_model["api_key_masked"].startswith("sk-")
            print(f"    - Added model '{created_model['name']}' (ID: {created_model_id})")

            # Admin assigns this model to Seat 1 (seat_trend)
            r_assign_seat = await client.post("/api/v1/system/council/seats/seat_trend", headers=admin_headers, json={
                "model_id": created_model_id
            })
            assert r_assign_seat.status_code == 200
            print(f"    - Assigned model '{created_model_id}' to seat_trend")

            # Verify seat configuration has model_id
            r_seats_updated = await client.get("/api/v1/system/council/seats")
            trend_seat = next((s for s in r_seats_updated.json() if s["id"] == "seat_trend"), None)
            assert trend_seat is not None
            assert trend_seat.get("model_id") == created_model_id, "Seat model_id must match assigned model"
            print(f"    - Verified seat_trend model_id is persistently updated to: {trend_seat.get('model_id')}")

            # Clean up: Delete test model and reset seat
            await client.post("/api/v1/system/council/seats/seat_trend", headers=admin_headers, json={"model_id": ""})
            r_del_model = await client.delete(f"/api/v1/system/llm/models/{created_model_id}", headers=admin_headers)
            assert r_del_model.status_code == 200
            print(f"    - Cleaned up test model {created_model_id}")

            # 4.5 Strategy Presets & English System Prompt Verification
            print("  ✓ Testing Institutional Strategy Presets (Conservative, Aggressive, High-Alpha, Balanced)...")
            r_presets = await client.get("/api/v1/system/council/presets")
            assert r_presets.status_code == 200
            presets_data = r_presets.json()
            assert len(presets_data["presets"]) == 4, f"Expected 4 presets, got {len(presets_data['presets'])}"
            print(f"    - Verified 4 strategy presets: {[p['name'] for p in presets_data['presets']]}")

            # Apply 'conservative' preset
            r_apply_cons = await client.post("/api/v1/system/council/presets/conservative/apply", headers=admin_headers)
            assert r_apply_cons.status_code == 200
            cons_seats = r_apply_cons.json()["seats"]
            cons_trend = next(s for s in cons_seats if s["id"] == "seat_trend")
            assert "[ROLE]: Conservative Trend" in cons_trend["prompt"]
            assert "# [角色定位]" in cons_trend["prompt"]
            print(f"    - Applied 'conservative' preset: seat_trend prompt verified with English instructions + Chinese comments")

            # Apply 'high_alpha' preset
            r_apply_alpha = await client.post("/api/v1/system/council/presets/high_alpha/apply", headers=admin_headers)
            assert r_apply_alpha.status_code == 200
            alpha_seats = r_apply_alpha.json()["seats"]
            alpha_cio = next(s for s in alpha_seats if s["id"] == "seat_cio")
            assert ">= 3.5" in alpha_cio["prompt"]
            print(f"    - Applied 'high_alpha' preset: seat_cio R:R >= 3.5 constraint verified")

            # Restore 'balanced' default preset
            r_restore = await client.post("/api/v1/system/council/presets/balanced/apply", headers=admin_headers)
            assert r_restore.status_code == 200
            print(f"    - Restored 'balanced' strategy preset")

            # ------------------------------------------------------------------
            # 5. Dual-Tier Telegram Bot Engine & Interactive Command Routing
            # ------------------------------------------------------------------
            print("\n[STEP 5] Testing Dual-Tier Telegram Bot Engine...")
            admin_cid = "12345678"
            user_cid = "999888777"
            settings.TELEGRAM_ADMIN_CHAT_ID = admin_cid

            # 5.1 Admin Command: /status
            res_admin_status = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(admin_cid)}, "text": "/status"}
            })
            assert res_admin_status is not None
            assert "生产系统运行报告" in res_admin_status
            print(f"  ✓ Admin /status received valid production status report")

            # 5.2 Admin Command: /risk balanced
            res_admin_risk = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(admin_cid)}, "text": "/risk balanced"}
            })
            assert res_admin_risk is not None
            assert "BALANCED" in res_admin_risk
            print(f"  ✓ Admin /risk balanced correctly applied preset")

            # 5.3 Regular User Command: /status (Masked Sandboxed)
            res_user_status = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(user_cid)}, "text": "/status"}
            })
            assert res_user_status is not None
            assert "★ 100,000+ USDT" in res_user_status
            assert "公开量化监测看板" in res_user_status
            print(f"  ✓ User /status returned masked sandboxed public overview")

            # 5.4 Regular User Command: /panic (Privilege Gated)
            res_user_panic = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(user_cid)}, "text": "/panic"}
            })
            assert res_user_panic is not None
            assert "权限不足" in res_user_panic
            print(f"  ✓ User /panic blocked with insufficient privilege warning")

            # 5.5 Regular User Command: /signals
            res_user_signals = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(user_cid)}, "text": "/signals"}
            })
            assert res_user_signals is not None
            assert "投委会最新多智能体共识信号" in res_user_signals
            print(f"  ✓ User /signals returned multi-agent consensus broadcast")

            # 5.6 Admin Command: /reset_cb (Circuit Breaker Reset)
            circuit_breaker.trigger_circuit_breaker("Test Trigger", "Manual E2E check")
            assert circuit_breaker.get_state()["active"] is True
            res_admin_reset = await telegram_bot.process_telegram_update({
                "message": {"chat": {"id": int(admin_cid)}, "text": "/reset_cb"}
            })
            assert res_admin_reset is not None
            assert circuit_breaker.get_state()["active"] is False
            print(f"  ✓ Admin /reset_cb successfully disengaged circuit breaker")

            # 5.7 Telegram Webhook Endpoint
            r_webhook = await client.post("/api/v1/system/telegram/webhook", json={
                "message": {"chat": {"id": int(user_cid)}, "text": "/help"}
            })
            assert r_webhook.status_code == 200
            print(f"  ✓ POST /api/v1/system/telegram/webhook returned 200 OK")

    print("\n======================================================================")
    print("🎉 ALL COMMERCIAL, MASKING, COUNCIL & TELEGRAM TESTS PASSED PERFECTLY!")
    print("======================================================================")


if __name__ == "__main__":
    asyncio.run(test_commercial_e2e())

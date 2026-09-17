"""
Test Suite: Multi-Model LLM Pool Connectivity and Secure Secret Handling
Verifies:
1. Storing model with secret key and ensuring masked key on GET /system/llm/models
2. Testing connectivity via POST /system/llm/models/{model_id}/test using server-side secret
3. Testing connectivity via POST /system/llm/models/test with model_id
4. Handling invalid credentials gracefully with HTTP 400
5. Fallback to pool default model in LLMGateway
"""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.council.llm_models import llm_model_manager
from app.council.llm_gateway import llm_gateway

client = TestClient(app)
superadmin_token = create_access_token(data={"sub": "admin", "role": "superadmin"})
headers = {"Authorization": f"Bearer {superadmin_token}"}


def test_llm_model_pool_secure_test():
    # 1. Register a test model with a secret key
    saved = llm_model_manager.save_model({
        "id": "test_unit_model_1",
        "name": "Unit Test Model",
        "provider": "OpenAI-Compatible",
        "base_url": "https://test.api.ai/v1",
        "model_name": "test-gpt-4o",
        "api_key": "sk-REAL_SECRET_KEY_12345678",
        "is_default": True
    })

    assert saved["id"] == "test_unit_model_1"
    assert saved["api_key_masked"] == "sk-R••••••••5678"
    assert "api_key" not in saved

    # 2. Verify GET /api/v1/system/llm/models returns masked key
    res = client.get("/api/v1/system/llm/models", headers=headers)
    assert res.status_code == 200
    models = res.json()
    matched = next((m for m in models if m["id"] == "test_unit_model_1"), None)
    assert matched is not None
    assert matched["api_key_masked"] == "sk-R••••••••5678"
    assert "api_key" not in matched

    # 3. Test POST /api/v1/system/llm/models/{model_id}/test
    # Mock httpx.AsyncClient.post to verify real secret key was sent
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"choices":[{"message":{"content":"{\\"ping\\": \\"pong\\"}"}}]}'
        mock_post.return_value = mock_resp

        res_test = client.post("/api/v1/system/llm/models/test_unit_model_1/test", headers=headers)
        assert res_test.status_code == 200
        assert "连通成功" in res_test.json()["message"]

        # Assert that real secret key was sent in headers
        args, kwargs = mock_post.call_args
        sent_headers = kwargs.get("headers", {})
        assert sent_headers.get("Authorization") == "Bearer sk-REAL_SECRET_KEY_12345678"

    # 4. Test POST /api/v1/system/llm/models/test with model_id
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"choices":[{"message":{"content":"ok"}}]}'
        mock_post.return_value = mock_resp

        res_test2 = client.post("/api/v1/system/llm/models/test", json={
            "model_id": "test_unit_model_1"
        }, headers=headers)
        assert res_test2.status_code == 200
        args, kwargs = mock_post.call_args
        assert kwargs.get("headers", {}).get("Authorization") == "Bearer sk-REAL_SECRET_KEY_12345678"

    # 5. Test POST /api/v1/system/llm/models/test with non-existent model and no key
    res_fail = client.post("/api/v1/system/llm/models/test", json={
        "base_url": "https://dummy.ai",
        "model_name": "dummy",
        "api_key": "***"
    }, headers=headers)
    assert res_fail.status_code == 400

    # 6. Verify llm_model_manager.get_default_model()
    default_m = llm_model_manager.get_default_model()
    assert default_m is not None
    assert default_m["id"] == "test_unit_model_1"
    assert default_m["api_key"] == "sk-REAL_SECRET_KEY_12345678"

    # Clean up test model
    llm_model_manager.delete_model("test_unit_model_1")
    print("ALL LLM MODEL POOL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_llm_model_pool_secure_test()

"""
Encrypted Ledger - System Status, Dynamic Universe & Multi-Agent Council API
Health checks, exchange credentials, 4+1 multi-agent council seats management,
and dual-tier Telegram Bot settings.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.api.auth import verify_admin_session
from app.core.config import settings
from app.council.council_policy import council_policy_manager
from app.council.council_desk import council_desk
from app.notifications.telegram_bot import telegram_bot
from app.quant.universe import universe_manager

router = APIRouter(prefix="/system", tags=["System Management"])


class AddInstrumentRequest(BaseModel):
    name: str
    ccy: Optional[str] = None
    tier: Optional[str] = "tier_2_momentum"
    max_leverage: Optional[float] = 3.0
    sl_atr_mult: Optional[float] = 2.2
    precision: Optional[int] = 2
    risk_per_trade_usd: Optional[float] = 15.0


@router.get("/health")
async def health_check():
    """System liveness and core subsystem integrity indicator."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "2.0.0-PRO",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }


class UpdateCredentialsRequest(BaseModel):
    okx_env: Optional[str] = None
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None
    binance_env: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    gate_env: Optional[str] = None
    gate_api_key: Optional[str] = None
    gate_secret_key: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_admin_chat_id: Optional[str] = None


@router.post("/credentials", dependencies=[Depends(verify_admin_session)])
async def update_credentials(req: UpdateCredentialsRequest):
    """Update OKX, Binance, LLM, and Telegram Bot credentials dynamically."""
    if req.okx_env:
        settings.OKX_ENV = req.okx_env.lower()
    if req.okx_api_key is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_API_KEY = req.okx_api_key
        else:
            settings.OKX_LIVE_API_KEY = req.okx_api_key
    if req.okx_secret_key is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_SECRET_KEY = req.okx_secret_key
        else:
            settings.OKX_LIVE_SECRET_KEY = req.okx_secret_key
    if req.okx_passphrase is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_PASSPHRASE = req.okx_passphrase
        else:
            settings.OKX_LIVE_PASSPHRASE = req.okx_passphrase

    if req.binance_env:
        settings.BINANCE_ENV = req.binance_env.lower()
    if req.binance_api_key is not None:
        if settings.BINANCE_ENV == "demo":
            settings.BINANCE_DEMO_API_KEY = req.binance_api_key
        else:
            settings.BINANCE_LIVE_API_KEY = req.binance_api_key
    if req.binance_secret_key is not None:
        if settings.BINANCE_ENV == "demo":
            settings.BINANCE_DEMO_SECRET_KEY = req.binance_secret_key
        else:
            settings.BINANCE_LIVE_SECRET_KEY = req.binance_secret_key

    if req.gate_env:
        settings.GATE_ENV = req.gate_env.lower()
    if req.gate_api_key is not None:
        settings.GATE_API_KEY = req.gate_api_key.strip()
    if req.gate_secret_key is not None:
        settings.GATE_SECRET_KEY = req.gate_secret_key.strip()

    if req.llm_api_key is not None:
        settings.LLM_API_KEY = req.llm_api_key
    if req.llm_base_url is not None:
        settings.LLM_BASE_URL = req.llm_base_url
    if req.llm_model is not None:
        settings.LLM_MODEL = req.llm_model

    if req.telegram_bot_token is not None:
        settings.TELEGRAM_BOT_TOKEN = req.telegram_bot_token.strip()
    if req.telegram_admin_chat_id is not None:
        settings.TELEGRAM_ADMIN_CHAT_ID = req.telegram_admin_chat_id.strip()

    return {"status": "success", "message": "系统与外部服务凭证已动态更新生效"}


def mask_secret(s: str) -> str:
    if not s:
        return ""
    if len(s) < 8:
        return "******"
    return s[:3] + "..." + s[-3:]


@router.get("/credentials", dependencies=[Depends(verify_admin_session)])
async def get_credentials():
    """Retrieve masked credentials overview for admin console."""
    return {
        "okx_env": settings.OKX_ENV,
        "okx_api_key_masked": mask_secret(settings.OKX_LIVE_API_KEY if settings.OKX_ENV == "live" else settings.OKX_DEMO_API_KEY),
        "binance_env": settings.BINANCE_ENV,
        "binance_api_key_masked": mask_secret(settings.BINANCE_LIVE_API_KEY if settings.BINANCE_ENV == "live" else settings.BINANCE_DEMO_API_KEY),
        "llm_base_url": settings.LLM_BASE_URL,
        "llm_model": settings.LLM_MODEL,
        "llm_key_masked": mask_secret(settings.LLM_API_KEY),
        "telegram_bot_token_masked": mask_secret(settings.TELEGRAM_BOT_TOKEN),
        "telegram_admin_chat_id": settings.TELEGRAM_ADMIN_CHAT_ID or settings.TELEGRAM_CHAT_ID or ""
    }


# ------------------------------------------------------------------------------
# Multi-Agent Council Seats Management
# ------------------------------------------------------------------------------

class UpdateSeatRequest(BaseModel):
    name: Optional[str] = None
    role_title: Optional[str] = None
    prompt: Optional[str] = None
    weight: Optional[float] = None
    temperature: Optional[float] = None
    enabled: Optional[bool] = None
    model_id: Optional[str] = None


@router.get("/council/seats")
async def get_council_seats():
    """List configured 4+1 institutional multi-agent seats."""
    return council_policy_manager.get_seats()


@router.post("/council/seats/{seat_id}", dependencies=[Depends(verify_admin_session)])
async def update_council_seat(seat_id: str, req: UpdateSeatRequest):
    """Update system prompt, weight, model, or enabled status for a council seat."""
    success = council_policy_manager.update_seat(seat_id, req.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到席位 {seat_id}")
    return {"status": "success", "message": f"席位 {seat_id} 配置已更新生效"}


@router.get("/council/presets")
async def get_council_presets():
    """List available institutional hedge fund strategy presets with active status."""
    return {
        "presets": council_policy_manager.get_presets(),
        "active_preset": council_policy_manager.get_active_preset()
    }


@router.post("/council/presets/{preset_id}/apply", dependencies=[Depends(verify_admin_session)])
async def apply_council_preset(preset_id: str):
    """Apply a hedge fund strategy preset to all 5 council seats while keeping model assignments."""
    try:
        seats = council_policy_manager.apply_preset(preset_id)
        return {
            "status": "success",
            "message": f"策略模板 [{preset_id}] 已一键套用至投委会 5 大席位！",
            "active_preset": preset_id,
            "seats": seats
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/council/reset", dependencies=[Depends(verify_admin_session)])
async def reset_council_seats():
    """Reset all council seats to default institutional hedge fund settings."""
    seats = council_policy_manager.reset_to_defaults()
    return {"status": "success", "message": "投委会 4+1 席位已全部重置为平衡机构官方默认模板", "seats": seats}


@router.get("/council/debates")
async def get_recent_council_debates():
    """Retrieve recent multi-agent deliberation records with full debate transcripts."""
    return council_desk.get_latest_debate_history(15)


# ------------------------------------------------------------------------------
# Multi-Model Pool Management Endpoints
# ------------------------------------------------------------------------------

class SaveLLMModelRequest(BaseModel):
    id: Optional[str] = None
    name: str
    provider: Optional[str] = "OpenAI-Compatible"
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    is_default: Optional[bool] = False


class TestLLMModelRequest(BaseModel):
    base_url: str
    model_name: str
    api_key: str


@router.get("/llm/models")
async def list_llm_models():
    """Retrieve all configured LLM models with masked API keys."""
    from app.council.llm_models import llm_model_manager
    return llm_model_manager.get_all_models(mask_keys=True)


@router.post("/llm/models", dependencies=[Depends(verify_admin_session)])
async def save_llm_model(req: SaveLLMModelRequest):
    """Add or update an LLM model entry in the pool."""
    from app.council.llm_models import llm_model_manager
    saved = llm_model_manager.save_model(req.model_dump())
    return {"status": "success", "message": f"模型「{saved.get('name')}」配置已保存", "model": saved}


@router.delete("/llm/models/{model_id}", dependencies=[Depends(verify_admin_session)])
async def delete_llm_model(model_id: str):
    """Delete a model entry from the pool."""
    from app.council.llm_models import llm_model_manager
    ok = llm_model_manager.delete_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该模型")
    return {"status": "success", "message": "模型已成功删除"}


@router.post("/llm/models/test", dependencies=[Depends(verify_admin_session)])
async def test_llm_model(req: TestLLMModelRequest):
    """Test connectivity to an OpenAI-compatible endpoint."""
    from app.council.llm_models import llm_model_manager
    ok, msg = await llm_model_manager.test_connection(req.base_url, req.model_name, req.api_key)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}


# ------------------------------------------------------------------------------
# Telegram Bot Testing & Webhook Dispatcher
# ------------------------------------------------------------------------------

@router.post("/telegram/test", dependencies=[Depends(verify_admin_session)])
async def test_telegram_alert():
    """Send a test notification to configured Superadmin Telegram Chat ID."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="未配置 TELEGRAM_BOT_TOKEN，无法发送测试消息")
    admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID.strip() or settings.TELEGRAM_CHAT_ID.strip()
    if not admin_chat:
        raise HTTPException(status_code=400, detail="未配置 TELEGRAM_ADMIN_CHAT_ID，无法发送测试消息")

    test_msg = (
        "<b>🔔 [Encrypted Ledger] Telegram 机器人连通性测试成功！</b>\n\n"
        "• 权限级别: <b>超级管理员 (Superadmin)</b>\n"
        "• 状态: <b>实时警报通道已就绪</b>\n"
        "• 支持指令: <code>/status</code>, <code>/positions</code>, <code>/panic</code>, <code>/cycle</code>, <code>/risk</code>"
    )
    ok = await telegram_bot.send_message(admin_chat, test_msg)
    if not ok:
        raise HTTPException(status_code=502, detail="Telegram 消息发送失败，请核对 Bot Token 及 Chat ID 是否正确")
    return {"status": "success", "message": "Telegram 测试通知已成功发出，请检查您的手机或客户端"}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive and process incoming Telegram Bot updates for interactive commands."""
    try:
        data = await request.json()
        reply = await telegram_bot.process_telegram_update(data)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ------------------------------------------------------------------------------
# Dynamic Universe Management
# ------------------------------------------------------------------------------

@router.post("/universe/add", dependencies=[Depends(verify_admin_session)])
async def add_instrument_to_universe(req: AddInstrumentRequest):
    """Dynamically adds a custom cryptocurrency into the active trading universe."""
    try:
        universe_manager.add_instrument(req.model_dump())
        return {"status": "success", "message": f"标的 {req.name.upper()} 已成功添加至交易池"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/universe/{symbol}", dependencies=[Depends(verify_admin_session)])
async def remove_instrument_from_universe(symbol: str):
    """Dynamically removes a cryptocurrency from the trading universe."""
    success = universe_manager.remove_instrument(symbol)
    if not success:
        raise HTTPException(status_code=404, detail=f"标的 {symbol.upper()} 未在交易池中找到")
    return {"status": "success", "message": f"标的 {symbol.upper()} 已从交易池中移除"}


@router.put("/universe/{symbol}", dependencies=[Depends(verify_admin_session)])
async def update_instrument_in_universe(symbol: str, updates: Dict[str, Any]):
    """Update risk or precision settings for an existing instrument."""
    success = universe_manager.update_instrument(symbol, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"标的 {symbol.upper()} 未在交易池中找到")
    return {"status": "success", "message": f"标的 {symbol.upper()} 配置已更新"}


# ------------------------------------------------------------------------------
# System-level Authenticated Disaster Recovery (AES-256 PBKDF2)
# ------------------------------------------------------------------------------

class CreateBackupRequest(BaseModel):
    password: str
    note: Optional[str] = ""


class RestoreBackupRequest(BaseModel):
    password: str
    backup_b64: Optional[str] = None
    filename: Optional[str] = None


@router.post("/backup/create", dependencies=[Depends(verify_admin_session)])
async def trigger_create_backup(req: CreateBackupRequest):
    """Generates an AES-256 encrypted disaster recovery backup archive."""
    try:
        from app.core.backup import create_encrypted_backup
        res = create_encrypted_backup(req.password, req.note or "")
        return {"status": "success", "message": "系统灾备包加密生成成功", "backup": res}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建系统灾备失败: {e}")


@router.get("/backup/list", dependencies=[Depends(verify_admin_session)])
async def list_system_backups():
    """List all available system disaster recovery archives."""
    from app.core.backup import list_backups
    return list_backups()


@router.get("/backup/download/{filename}", dependencies=[Depends(verify_admin_session)])
async def download_system_backup(filename: str):
    """Download an encrypted disaster recovery backup file (.enc)."""
    import os
    from fastapi.responses import FileResponse
    from app.core.backup import BACKUP_DIR
    safe_name = os.path.basename(filename)
    target = BACKUP_DIR / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="灾备文件不存在")
    return FileResponse(path=str(target), filename=safe_name, media_type="application/octet-stream")


@router.post("/backup/restore", dependencies=[Depends(verify_admin_session)])
async def trigger_restore_backup(req: RestoreBackupRequest):
    """Restores entire system state from encrypted backup using master password."""
    import base64
    import os
    from app.core.backup import restore_encrypted_backup, BACKUP_DIR

    raw_bytes = None
    if req.backup_b64:
        try:
            raw_bytes = base64.b64decode(req.backup_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Base64 数据格式损坏")
    elif req.filename:
        safe_name = os.path.basename(req.filename)
        target = BACKUP_DIR / safe_name
        if not target.exists():
            raise HTTPException(status_code=404, detail="指定的灾备归档文件未找到")
        raw_bytes = target.read_bytes()
    else:
        raise HTTPException(status_code=400, detail="必须提供 backup_b64 或 filename")

    try:
        res = restore_encrypted_backup(raw_bytes, req.password)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"灾备还原异常: {e}")


@router.delete("/backup/{filename}", dependencies=[Depends(verify_admin_session)])
async def remove_system_backup(filename: str):
    """Delete a specific backup archive file."""
    from app.core.backup import delete_backup_file
    deleted = delete_backup_file(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="灾备文件不存在")
    return {"status": "success", "message": f"灾备文件 {filename} 已成功删除"}


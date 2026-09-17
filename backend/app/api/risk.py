"""
Encrypted Ledger - Risk Control Center API
Exposes the 17-factor execution parameters, sandbox simulator, circuit breaker status,
and dynamic Python Risk Interceptor Plugins lifecycle & test engine.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.api.auth import verify_admin_session
from app.core.config import settings
from app.risk.constants import dump_risk_constants_summary
from app.risk.interceptors import interceptor_pipeline
from app.intelligence.circuit_breaker import circuit_breaker
from app.risk.interceptor_manager import (
    list_plugins,
    get_plugin_code,
    save_plugin_code,
    toggle_plugin,
    delete_plugin,
    run_sandbox_test,
    load_config,
    save_config,
)

router = APIRouter(prefix="/risk", tags=["Risk Management"])


class UpdateRiskConstantsRequest(BaseModel):
    preset: Optional[str] = None  # "conservative", "balanced", "aggressive"
    max_concurrent_positions: Optional[int] = None
    max_same_direction_positions: Optional[int] = None
    max_margin_equity_ratio: Optional[float] = None
    min_leverage: Optional[float] = None
    max_leverage: Optional[float] = None
    per_trade_ratio: Optional[float] = None
    min_risk_reward: Optional[float] = None
    min_entry_confidence: Optional[float] = None
    max_daily_loss_usdt: Optional[float] = None
    time_stop_hours: Optional[float] = None
    stop_cooldown_minutes: Optional[int] = None


class SandboxSimulationRequest(BaseModel):
    symbol: str
    side: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    confidence: float
    notional_usd: float
    leverage: float
    account_balance_usd: float


class SavePluginRequest(BaseModel):
    filename: str
    code: str


class TogglePluginRequest(BaseModel):
    filename: str
    enabled: bool


class ReorderPluginsRequest(BaseModel):
    order: List[str]


@router.get("/constants", dependencies=[Depends(verify_admin_session)])
async def get_risk_constants():
    """Retrieve current single source of truth risk parameters."""
    return dump_risk_constants_summary()


@router.post("/constants", dependencies=[Depends(verify_admin_session)])
async def update_risk_constants(req: UpdateRiskConstantsRequest):
    """Update risk parameters or apply one-click risk presets."""
    if req.preset == "conservative":
        settings.RISK_MAX_LEVERAGE = 3.0
        settings.RISK_MIN_ENTRY_CONFIDENCE = 85.0
        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.15
        settings.RISK_PER_TRADE_RATIO = 0.015
    elif req.preset == "balanced":
        settings.RISK_MAX_LEVERAGE = 5.0
        settings.RISK_MIN_ENTRY_CONFIDENCE = 80.0
        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.20
        settings.RISK_PER_TRADE_RATIO = 0.02
    elif req.preset == "aggressive":
        settings.RISK_MAX_LEVERAGE = 10.0
        settings.RISK_MIN_ENTRY_CONFIDENCE = 70.0
        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.35
        settings.RISK_PER_TRADE_RATIO = 0.03

    if req.max_concurrent_positions is not None:
        settings.RISK_MAX_CONCURRENT_POSITIONS = req.max_concurrent_positions
    if req.max_same_direction_positions is not None:
        settings.RISK_MAX_SAME_DIRECTION_POSITIONS = req.max_same_direction_positions
    if req.max_margin_equity_ratio is not None:
        settings.RISK_MAX_MARGIN_EQUITY_RATIO = req.max_margin_equity_ratio
    if req.min_leverage is not None:
        settings.RISK_MIN_LEVERAGE = req.min_leverage
    if req.max_leverage is not None:
        settings.RISK_MAX_LEVERAGE = req.max_leverage
    if req.per_trade_ratio is not None:
        settings.RISK_PER_TRADE_RATIO = req.per_trade_ratio
    if req.min_risk_reward is not None:
        settings.RISK_MIN_RISK_REWARD = req.min_risk_reward
    if req.min_entry_confidence is not None:
        settings.RISK_MIN_ENTRY_CONFIDENCE = req.min_entry_confidence
    if req.max_daily_loss_usdt is not None:
        settings.RISK_MAX_DAILY_LOSS_USDT = req.max_daily_loss_usdt
    if req.time_stop_hours is not None:
        settings.RISK_TIME_STOP_HOURS = req.time_stop_hours
    if req.stop_cooldown_minutes is not None:
        settings.RISK_STOP_COOLDOWN_MINUTES = req.stop_cooldown_minutes

    return {"status": "success", "message": "风控参数已更新生效", "constants": dump_risk_constants_summary()}


@router.get("/circuit-breaker")
async def get_circuit_breaker_status():
    """Check whether black swan circuit breaker is currently active."""
    return circuit_breaker.get_state()


@router.post("/circuit-breaker/reset", dependencies=[Depends(verify_admin_session)])
async def reset_circuit_breaker():
    """Manually reset and clear circuit breaker."""
    circuit_breaker.manual_reset()
    return {"status": "success", "message": "熔断器已手动复位正常状态"}


@router.post("/sandbox/simulate", dependencies=[Depends(verify_admin_session)])
async def simulate_interceptor(req: SandboxSimulationRequest):
    """
    Online sandbox simulator: tests whether hypothetical trade parameters
    would pass or fail the Fail-Closed physical interceptor pipeline.
    """
    res = interceptor_pipeline.evaluate_order_intent(
        symbol=req.symbol,
        side=req.side,
        entry_price=req.entry_price,
        stop_loss_price=req.stop_loss_price,
        take_profit_price=req.take_profit_price,
        confidence=req.confidence,
        notional_usd=req.notional_usd,
        leverage=req.leverage,
        account_balance_usd=req.account_balance_usd,
        current_positions=[],
        factor_snapshot={"pillar_1_trend": {"adx": 25.0}}
    )
    return {
        "passed": res.passed,
        "blocked_by": res.blocked_by,
        "reason": res.reason,
        "details": res.details
    }


# ==============================================================================
# Python Risk Interceptor Plugins Lifecycle & Sandbox Endpoints
# ==============================================================================

@router.get("/plugins", dependencies=[Depends(verify_admin_session)])
async def get_plugins():
    """List all installed physical risk interceptor plugins."""
    return list_plugins()


@router.get("/plugins/{filename}", dependencies=[Depends(verify_admin_session)])
async def get_plugin(filename: str):
    """Retrieve raw Python code and metadata for a specific plugin."""
    try:
        return get_plugin_code(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="插件文件不存在")


@router.post("/plugins", dependencies=[Depends(verify_admin_session)])
async def save_plugin(req: SavePluginRequest):
    """Save or create a Python risk interceptor plugin with AST syntax validation."""
    try:
        updated = save_plugin_code(req.filename, req.code)
        return {"status": "success", "message": f"插件 [{req.filename}] 保存并热生效成功", "plugin": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存插件失败: {e}")


@router.put("/plugins/{filename}", dependencies=[Depends(verify_admin_session)])
async def update_plugin(filename: str, req: SavePluginRequest):
    """Update existing Python risk plugin code."""
    try:
        updated = save_plugin_code(filename, req.code)
        return {"status": "success", "message": f"插件 [{filename}] 热更新成功", "plugin": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新插件失败: {e}")


@router.delete("/plugins/{filename}", dependencies=[Depends(verify_admin_session)])
async def remove_plugin(filename: str):
    """Delete a custom risk interceptor plugin."""
    try:
        delete_plugin(filename)
        return {"status": "success", "message": f"插件 [{filename}] 已安全移除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除插件失败: {e}")


@router.post("/plugins/toggle", dependencies=[Depends(verify_admin_session)])
async def toggle_plugin_status(req: TogglePluginRequest):
    """Toggle a plugin's active status."""
    res = toggle_plugin(req.filename, req.enabled)
    return {"status": "success", "message": f"插件 [{req.filename}] 状态已变更为 {'启用' if req.enabled else '停用'}", "result": res}


@router.post("/plugins/reorder", dependencies=[Depends(verify_admin_session)])
async def reorder_plugins(req: ReorderPluginsRequest):
    """Update the execution sequence order of risk interceptor plugins."""
    cfg = load_config()
    cfg["pipeline_order"] = req.order
    save_config(cfg)
    return {"status": "success", "message": "插件流水线执行顺序已更新", "plugins": list_plugins()}


@router.post("/plugins/sandbox-test", dependencies=[Depends(verify_admin_session)])
async def run_plugins_sandbox_test():
    """
    Executes an instant sandbox stress test across 5 realistic institutional trade scenarios.
    Measures per-plugin latency and verifies Fail-Closed blocking logic.
    """
    try:
        report = run_sandbox_test()
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"沙箱测试运行异常: {e}")

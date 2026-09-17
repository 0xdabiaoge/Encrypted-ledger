"""
Encrypted Ledger - Risk Control Center API
Exposes the 17-factor execution parameters, sandbox simulator, and circuit breaker status.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from app.api.auth import verify_admin_session
from app.risk.constants import dump_risk_constants_summary
from app.risk.interceptors import interceptor_pipeline
from app.intelligence.circuit_breaker import circuit_breaker

router = APIRouter(prefix="/risk", tags=["Risk Management"])


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


@router.get("/constants", dependencies=[Depends(verify_admin_session)])
async def get_risk_constants():
    """Retrieve current single source of truth risk parameters."""
    return dump_risk_constants_summary()


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

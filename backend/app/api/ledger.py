"""
Encrypted Ledger - Ledger Audit & Performance API
Inspects immutable double-entry records, historical fill slips, and decision audit trails.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from app.api.auth import verify_admin_session
from app.database.db import get_db_session
from app.database.models import TradeDecision
from app.ledger.double_entry import double_entry_engine

router = APIRouter(prefix="/ledger", tags=["Double-Entry Ledger"])


@router.get("/entries", dependencies=[Depends(verify_admin_session)])
async def get_ledger_entries(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Fetch double-entry records with policy hash and latency metrics."""
    return await double_entry_engine.get_recent_entries(limit=limit, offset=offset)


@router.get("/summary", dependencies=[Depends(verify_admin_session)])
async def get_performance_summary():
    """Retrieve cumulative statistics: Win rate, Realized PnL, Profit Factor, Fees."""
    return await double_entry_engine.get_performance_summary()


@router.get("/decisions", dependencies=[Depends(verify_admin_session)])
async def get_decisions_audit(limit: int = Query(30, ge=1, le=100), session=Depends(get_db_session)):
    """Retrieve historical AI council decisions and interceptor approvals."""
    stmt = select(TradeDecision).order_by(TradeDecision.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    records = res.scalars().all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": r.symbol,
            "action": r.action,
            "confidence": r.confidence,
            "leverage": r.suggested_leverage,
            "entry_target": r.entry_target_price,
            "stop_loss": r.stop_loss_price,
            "take_profit": r.take_profit_price,
            "rr_ratio": r.risk_reward_ratio,
            "passed_interceptors": r.passed_interceptors,
            "intercept_reason": r.intercept_reason,
            "policy_hash": r.policy_hash
        }
        for r in records
    ]

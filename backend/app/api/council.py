"""
Encrypted Ledger - Council & Policy Management API
Policy snapshot archive, 0.5s atomic rollback, and heuristic self-evolution memory.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.api.auth import verify_admin_session
from app.ledger.policy_snapshot import policy_engine
from app.council.self_evolution import self_evolution

router = APIRouter(prefix="/council", tags=["Council & Policy"])


class CreateSnapshotRequest(BaseModel):
    version_tag: str
    description: Optional[str] = ""


class RollbackRequest(BaseModel):
    version_tag: str


@router.get("/policy/active")
async def get_active_policy():
    """Retrieve currently active 4-in-1 policy bundle with SHA-256 fingerprint."""
    return policy_engine.get_active_policy()


@router.get("/policy/archives", dependencies=[Depends(verify_admin_session)])
async def list_policy_archives():
    """List all historically archived policy versions."""
    return policy_engine.list_archived_snapshots()


@router.post("/policy/snapshot", dependencies=[Depends(verify_admin_session)])
async def create_snapshot(req: CreateSnapshotRequest):
    """Archive current system state as an immutable policy snapshot."""
    try:
        res = policy_engine.capture_current_policy(req.version_tag, req.description or "")
        return {"status": "success", "snapshot": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/policy/rollback", dependencies=[Depends(verify_admin_session)])
async def rollback_policy(req: RollbackRequest):
    """Execute 0.5s atomic rollback to an archived policy version."""
    try:
        res = policy_engine.rollback_to_version(req.version_tag)
        return {"status": "success", "restored": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evolution/memory")
async def get_trading_memory():
    """Read white-box heuristic trading memory rules."""
    return {"memory_markdown": self_evolution.get_current_memory()}


@router.post("/evolution/trigger", dependencies=[Depends(verify_admin_session)])
async def trigger_evolution_review():
    """Trigger manual closed-trade review and self-evolution update."""
    return await self_evolution.run_review_cycle()


@router.get("/prompt-tokens")
async def list_prompt_tokens():
    """Retrieve all available dynamic prompt token slots for prompt engineering."""
    from app.intelligence.prompt_renderer import get_available_prompt_tokens
    return get_available_prompt_tokens()


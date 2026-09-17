"""Encrypted Ledger API Package"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.market import router as market_router
from app.api.trading import router as trading_router
from app.api.ledger import router as ledger_router
from app.api.risk import router as risk_router
from app.api.intelligence import router as intelligence_router
from app.api.council import router as council_router
from app.api.system import router as system_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(market_router)
api_v1_router.include_router(trading_router)
api_v1_router.include_router(ledger_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(intelligence_router)
api_v1_router.include_router(council_router)
api_v1_router.include_router(system_router)

__all__ = ["api_v1_router"]

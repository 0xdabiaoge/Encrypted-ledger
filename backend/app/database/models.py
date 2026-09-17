"""
Encrypted Ledger - Database Models & Schema
Double-entry ledger, trade decisions audit, policy version snapshots, and security state.
"""
from __future__ import annotations

import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Index
)
from app.database.db import Base


class LedgerEntry(Base):
    """
    Immutable Double-Entry Ledger Record.
    Every filled trade, fee, funding transfer, and balance shift is logged here.
    """
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    venue = Column(String(32), nullable=False)        # "okx" | "binance"
    symbol = Column(String(32), nullable=False, index=True)      # e.g. "BTC"
    inst_id = Column(String(64), nullable=False)     # e.g. "BTC-USDT-SWAP" / "BTCUSDT"
    
    entry_type = Column(String(32), nullable=False)   # "OPEN_LONG" | "CLOSE_LONG" | "OPEN_SHORT" | "CLOSE_SHORT" | "FUNDING" | "FEE"
    side = Column(String(16), nullable=False)         # "buy" | "sell"
    
    fill_price = Column(Float, nullable=False)
    fill_qty = Column(Float, nullable=False)          # native contracts or coins
    notional_usd = Column(Float, nullable=False)      # USD nominal value
    
    fee_usd = Column(Float, default=0.0)
    funding_usd = Column(Float, default=0.0)
    realized_pnl_usd = Column(Float, default=0.0)
    account_equity_after = Column(Float, default=0.0)
    
    # Audit trail & cryptographic integrity
    order_id = Column(String(128), nullable=False, index=True)
    algo_id = Column(String(128), default="")
    policy_hash = Column(String(64), nullable=False, index=True) # SHA-256
    execution_latency_ms = Column(Float, default=0.0)
    slippage_bps = Column(Float, default=0.0)         # Slippage in basis points
    note = Column(Text, default="")

    __table_args__ = (
        Index("idx_ledger_venue_symbol", "venue", "symbol"),
    )


class TradeDecision(Base):
    """
    Auditable AI Council & Interceptor Decision Log.
    100% of LLM reasoning, factor slices, and interceptor gate evaluations are preserved.
    """
    __tablename__ = "trade_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    symbol = Column(String(32), nullable=False, index=True)
    venue_recommended = Column(String(32), nullable=False)
    action = Column(String(32), nullable=False)       # "BUY" | "SELL" | "HOLD" | "CLOSE"
    confidence = Column(Float, nullable=False)        # 0.0 ~ 100.0 %
    
    suggested_leverage = Column(Float, default=3.0)
    entry_target_price = Column(Float, default=0.0)
    stop_loss_price = Column(Float, default=0.0)
    take_profit_price = Column(Float, default=0.0)
    risk_reward_ratio = Column(Float, default=0.0)
    
    # Interceptor pipeline outcome
    passed_interceptors = Column(Boolean, default=False)
    intercept_reason = Column(String(255), default="")
    
    # Detailed inputs & reasoning
    council_debate_json = Column(Text, default="{}")
    factor_snapshot_json = Column(Text, default="{}")
    calculus_snapshot_json = Column(Text, default="{}")
    macro_sentiment_json = Column(Text, default="{}")
    policy_hash = Column(String(64), default="")


class PolicySnapshotRecord(Base):
    """
    Snapshot archive for 100% reproducible policy versions.
    Allows 0.5s rollback with complete SHA-256 fingerprinting.
    """
    __tablename__ = "policy_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    version_tag = Column(String(64), unique=True, nullable=False)
    sha256_hash = Column(String(64), unique=True, nullable=False)
    author = Column(String(64), default="system")
    description = Column(Text, default="")
    
    payload_json = Column(Text, nullable=False)  # Full config, prompts, interceptor rules, pool
    is_active = Column(Boolean, default=False, index=True)


class AdminUser(Base):
    """Administrator credentials for control plane authentication."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="superadmin")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

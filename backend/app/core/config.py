"""
Encrypted Ledger - Core Application Configuration
Loads settings from environment variables and .env file with robust Pydantic v2 validation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 1. Base App
    APP_NAME: str = "Encrypted Ledger"
    APP_ENV: str = "production"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"

    # Paths
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "data")
    LOGS_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "logs")

    # Security
    ADMIN_SETUP_TOKEN: str = "encrypted_ledger_setup_token_2026"
    ADMIN_SECRET_KEY: str = ""
    FERNET_KEY_FILE: str = "data/.encrypted_ledger_secret.key"

    LOGIN_RATE_LIMIT: int = 1
    LOGIN_IP_WINDOW_SECONDS: int = 300
    LOGIN_IP_MAX_FAILURES: int = 10
    LOGIN_IP_BLOCK_SECONDS: int = 900
    TRUSTED_PROXIES: str = "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

    # 2. Exchanges: OKX & Binance
    OKX_ENV: str = "demo"  # demo | live
    OKX_LIVE_API_KEY: str = ""
    OKX_LIVE_SECRET_KEY: str = ""
    OKX_LIVE_PASSPHRASE: str = ""
    OKX_DEMO_API_KEY: str = ""
    OKX_DEMO_SECRET_KEY: str = ""
    OKX_DEMO_PASSPHRASE: str = ""

    BINANCE_ENV: str = "demo"  # demo | live
    BINANCE_LIVE_API_KEY: str = ""
    BINANCE_LIVE_SECRET_KEY: str = ""
    BINANCE_DEMO_API_KEY: str = ""
    BINANCE_DEMO_SECRET_KEY: str = ""

    PREFERRED_VENUE: str = "auto"  # auto | okx | binance
    ROUTING_MODE: str = "lowest_slippage"  # lowest_slippage | fee_optimized | balanced

    # 3. Execution Layer Risk Parameters
    RISK_MAX_CONCURRENT_POSITIONS: int = 0
    RISK_MAX_SAME_DIRECTION_POSITIONS: int = 3
    RISK_MAX_MARGIN_EQUITY_RATIO: float = 0.20
    RISK_SINGLE_ASSET_EQUITY_RATIO: float = 0.30
    RISK_MAX_SINGLE_ASSET_MARGIN_USDT: float = 600.0
    RISK_MIN_LEVERAGE: float = 2.0
    RISK_MAX_LEVERAGE: float = 5.0

    RISK_PER_TRADE_RATIO: float = 0.02
    RISK_MIN_RISK_REWARD: float = 2.0
    RISK_MIN_ENTRY_CONFIDENCE: float = 80.0

    RISK_MAX_DAILY_LOSS_USDT: float = 150.0
    RISK_DAILY_LOSS_EQUITY_RATIO: float = 0.05
    RISK_TIME_STOP_HOURS: float = 8.0
    RISK_TIME_STOP_ATR_BAND: float = 0.15
    RISK_STOP_COOLDOWN_MINUTES: int = 30

    RISK_MAX_SCALE_IN_COUNT: int = 1
    RISK_MIN_SCALE_IN_PROFIT_RATIO: float = 0.08
    RISK_MIN_SCALE_IN_CONFIDENCE: float = 75.0

    # 4. Intelligence & News
    NEWS_HARVEST_INTERVAL_SECONDS: int = 600
    ENABLE_CIRCUIT_BREAKER: int = 1
    CIRCUIT_BREAKER_FREEZE_SECONDS: int = 1800

    # 5. LLM / Council
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-3.8-flash-high"
    LLM_REASONING_EFFORT: str = "high"
    LLM_TIMEOUT_SECONDS: int = 120
    COUNCIL_MODE: str = "council_debate"

    # 6. Notifications & Telegram Bot
    NOTIFY_TELEGRAM_ENABLED: int = 1
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""
    TELEGRAM_CHAT_ID: str = ""
    NOTIFY_WECHAT_ENABLED: int = 0
    WECHAT_WEBHOOK_URL: str = ""
    NOTIFY_WEBHOOK_ENABLED: int = 0
    CUSTOM_WEBHOOK_URL: str = ""

    # 7. Commercial Access & Data Masking
    REGISTRATION_MODE: str = "open"  # "open" | "invite_only"
    MASK_PUBLIC_DATA: int = 1        # 1: mask sensitive balance & position details for unauthenticated / guest viewers

    def ensure_directories(self):
        """Ensure runtime directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        (self.DATA_DIR / "policy_archives").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

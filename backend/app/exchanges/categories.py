"""
Encrypted Ledger - Symbol Categorization & Routing Rules
Distinguishes between Mainstream Tier-1 Assets (OKX / Binance)
and Meme / Small-Cap Altcoins (Gate.io Priority).
"""
from __future__ import annotations

from typing import Literal

# 顶级主流价值币（高流动性、极小点差，强制走 OKX 与 Binance 进行 SOR 滑点撮合）
MAINSTREAM_SYMBOLS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOT",
    "LINK", "LTC", "BCH", "NEAR", "SUI", "APT", "ATOM", "TRX",
    "MATIC", "POL", "UNI", "FIL", "ARB", "OP", "ETC"
}

# 知名 Meme 币与高波动小市值币种（Gate.io 深度优势与费率优势明显）
KNOWN_MEME_AND_ALTCOINS = {
    "PEPE", "DOGE", "SHIB", "FLOKI", "BONK", "WIF", "MEME",
    "TURBO", "BOME", "NEIRO", "POPCAT", "MEW", "BRETT", "1000SATS",
    "ORDI", "TRUMP", "FARTCOIN", "ACT", "GOAT", "PNUT", "MOODENG",
    "LUNC", "PEOPLE", "AIDOGE", "BABYDOGE", "CHEEMS", "PENGU",
    "SPX", "GIGA", "MOG", "COW", "CETUS", "DRIFT"
}

SymbolCategory = Literal["MAINSTREAM", "MEME_ALTCOIN"]


def extract_base_asset(symbol: str) -> str:
    """提取基础币种名称，如 BTC-USDT-SWAP -> BTC, PEPEUSDT -> PEPE"""
    s = symbol.upper().strip()
    for sep in ["-", "_", "/"]:
        if sep in s:
            return s.split(sep)[0]
    if s.endswith("USDT"):
        return s[:-4]
    if s.endswith("USD"):
        return s[:-3]
    return s


def categorize_symbol(symbol: str) -> SymbolCategory:
    """
    判定币种品类：
    1. 若在 MAINSTREAM_SYMBOLS 中，归类为 MAINSTREAM（OKX / Binance 撮合）
    2. 若在 KNOWN_MEME_AND_ALTCOINS 中，归类为 MEME_ALTCOIN（Gate.io 优先）
    3. 默认情况下，若不属于主流大币种，均归为 MEME_ALTCOIN
    """
    base = extract_base_asset(symbol)
    if base in MAINSTREAM_SYMBOLS:
        return "MAINSTREAM"
    return "MEME_ALTCOIN"


def is_meme_or_altcoin(symbol: str) -> bool:
    """快捷判定是否为 Meme 或小市值山寨币"""
    return categorize_symbol(symbol) == "MEME_ALTCOIN"

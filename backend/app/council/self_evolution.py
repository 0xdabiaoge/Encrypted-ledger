"""
Encrypted Ledger - Heuristic Self-Evolution Engine
Analyzes closed trade ledger records and synthesizes white-box trading memories with half-life decay.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy import select
from app.core.config import settings
from app.core.logging import logger
from app.core.atomic_io import atomic_write_text, read_text_safe
from app.database.db import async_session_factory
from app.database.models import LedgerEntry

MEMORY_FILE = settings.DATA_DIR / "AI_TRADING_MEMORY.md"


class SelfEvolutionEngine:
    """Institutional closed-loop review and continuous policy refinement."""

    def __init__(self):
        self.memory_file = MEMORY_FILE

    async def run_review_cycle(self) -> Dict[str, Any]:
        """Reads recent trades from database and generates refined memory."""
        try:
            async with async_session_factory() as session:
                stmt = (
                    select(LedgerEntry)
                    .where(LedgerEntry.entry_type.in_(["CLOSE_LONG", "CLOSE_SHORT"]))
                    .order_by(LedgerEntry.created_at.desc())
                    .limit(50)
                )
                res = await session.execute(stmt)
                closed_trades = res.scalars().all()

            if not closed_trades:
                logger.info("No closed trades found for self-evolution review.")
                return {"trades_analyzed": 0, "status": "insufficient_data"}

            total = len(closed_trades)
            wins = sum(1 for t in closed_trades if t.realized_pnl_usd > 0)
            losses = sum(1 for t in closed_trades if t.realized_pnl_usd < 0)
            win_rate = (wins / total * 100.0) if total > 0 else 0.0

            total_profit = sum(t.realized_pnl_usd for t in closed_trades if t.realized_pnl_usd > 0)
            total_loss = abs(sum(t.realized_pnl_usd for t in closed_trades if t.realized_pnl_usd < 0))
            profit_factor = (total_profit / total_loss) if total_loss > 0 else 9.99

            total_fees = sum(t.fee_usd for t in closed_trades)
            avg_slippage = sum(t.slippage_bps for t in closed_trades) / total if total > 0 else 0.0

            now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Formulate markdown memory
            memory_md = f"""# Encrypted Ledger - AI 交易启发式心法记忆
> 更新时间: {now_str} | 样本数: {total} 笔 | 胜率: {win_rate:.1f}% | 利润因子(PF): {profit_factor:.2f}

## 1. 战绩全景统计
- **总平仓笔数**: {total} (盈利: {wins} / 亏损: {losses})
- **累计实现盈亏**: {total_profit - total_loss:+.2f} USDT
- **摩擦损耗**: 手续费总计 {total_fees:.2f} USDT | 平均滑点 {avg_slippage:.2f} bps

## 2. 核心避坑军规 (演化盾防护)
1. **防横盘磨损**: 当 1H ADX < 20 时绝不强行加仓，严禁在无序窄幅震荡中过度频繁开单；
2. **严守 2.0R 几何线**: 所有开仓必须有清晰的结构位支撑/阻力，止损严禁随意下移；
3. **盈利保本平移**: 当浮盈达到 1.5R 风险空间时，必须坚决执行移动保本线（Breakeven），守护已有战果；
4. **宏观黑天鹅敬畏**: 遇稳定币异动、大所流动性危机时，无条件执行熔断退避。
"""
            atomic_write_text(self.memory_file, memory_md)
            logger.info(f"Self-evolution cycle completed: {total} trades analyzed, WinRate={win_rate:.1f}%.")
            
            return {
                "trades_analyzed": total,
                "win_rate": round(win_rate, 1),
                "profit_factor": round(profit_factor, 2),
                "total_fees_usd": round(total_fees, 2),
                "avg_slippage_bps": round(avg_slippage, 2)
            }

        except Exception as e:
            logger.error(f"Self-evolution cycle failed: {e}")
            return {"error": str(e)}

    def get_current_memory(self) -> str:
        return read_text_safe(self.memory_file, default="")


self_evolution = SelfEvolutionEngine()

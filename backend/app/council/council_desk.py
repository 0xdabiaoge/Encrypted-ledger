"""
Encrypted Ledger - Multi-Model Investment Council Desk
Simulates a Tier-1 hedge fund trading desk with specialized analyst seats and CIO final arbitrage.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.council.llm_gateway import llm_gateway
from app.risk.constants import dump_risk_constants_summary


SYSTEM_PROMPT_CIO = """你现在是 Encrypted Ledger 顶级对冲基金的首席投资官 (CIO)。
你的使命是根据交易标的的实时五大因子、微积分物理量、全网宏观情报和持仓风控约束，输出机构级、数学严谨的交易决议。

【机构军规与硬约束】
1. 真实盈亏比 R:R 必须严格大于等于 2.0（即 |TP - Entry| / |SL - Entry| >= 2.0）；
2. 4H 趋势顺势铁律：大周期处于空头承压时绝对严禁做多；处于强多头通道时绝对严禁做空；
3. 信心分低于 80% 时必须输出 action = "HOLD" / "WAIT"；
4. 杠杆必须落在 [2.0, 5.0] 区间内；
5. 你必须严格以 JSON 格式输出决策，字段定义如下：
{
  "symbol": "BTC",
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 85.0,
  "suggested_leverage": 3.0,
  "entry_target_price": 65000.0,
  "stop_loss_price": 63800.0,
  "take_profit_price": 67500.0,
  "risk_reward_ratio": 2.08,
  "reasoning": "简明扼要的决策理由，综合考虑了动量速度、盘口微观及宏观新闻"
}
"""


class InvestmentCouncilDesk:
    """Orchestrates investment council debate and generates final trade proposals."""

    @staticmethod
    def _build_rule_based_fallback(
        symbol: str,
        current_price: float,
        factors: Dict[str, Any],
        atr: float
    ) -> Dict[str, Any]:
        """Mathematical rule-based proposal used when LLM is unconfigured or unresponsive."""
        score = float(factors.get("alpha_score", 50.0))
        confidence = float(factors.get("confidence", 50.0))
        signal = factors.get("signal", "HOLD")

        if signal in ("STRONG_BUY", "BUY") and confidence >= 80.0:
            action = "BUY"
            sl_dist = 1.8 * atr if atr > 0 else current_price * 0.015
            sl_price = round(current_price - sl_dist, 4)
            tp_price = round(current_price + 2.2 * sl_dist, 4)
            rr = round((tp_price - current_price) / (current_price - sl_price), 2)
            reason = f"数理因子高分触发 ({score:.1f}分)，微积分加速度多头共振，几何R:R达到{rr}"
        elif signal in ("STRONG_SELL", "SELL") and confidence >= 80.0:
            action = "SELL"
            sl_dist = 1.8 * atr if atr > 0 else current_price * 0.015
            sl_price = round(current_price + sl_dist, 4)
            tp_price = round(current_price - 2.2 * sl_dist, 4)
            rr = round((current_price - tp_price) / (sl_price - current_price), 2)
            reason = f"数理因子弱势击穿 ({score:.1f}分)，微积分下行速度扩大，几何R:R达到{rr}"
        else:
            action = "HOLD"
            sl_price = 0.0
            tp_price = 0.0
            rr = 0.0
            reason = f"置信度或因子未达开仓门槛 (Score: {score:.1f}, Conf: {confidence:.1f}%)，执行空仓等待"

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "suggested_leverage": 3.0,
            "entry_target_price": current_price,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "risk_reward_ratio": rr,
            "reasoning": f"[数理确定性引擎] {reason}",
            "source": "deterministic_quant_engine"
        }

    async def deliberate_on_instrument(
        self,
        symbol: str,
        current_price: float,
        factors: Dict[str, Any],
        macro_news: List[Dict[str, Any]],
        account_equity: float,
        trading_memory: str = ""
    ) -> Dict[str, Any]:
        """
        Conducts deliberation for a specific instrument.
        Uses LLM if configured; gracefully falls back to deterministic quant engine.
        """
        atr = float(factors.get("pillar_2_volatility", {}).get("atr", current_price * 0.015))

        # Check if LLM is enabled and configured
        if not settings.LLM_API_KEY:
            return self._build_rule_based_fallback(symbol, current_price, factors, atr)

        try:
            user_content = f"""
【待分析标的】: {symbol}
【当前最新市价】: {current_price}
【标的五大因子矩阵】:
{json.dumps(factors, ensure_ascii=False, indent=2)}

【近期全球宏观要闻与情绪】:
{json.dumps(macro_news[:6], ensure_ascii=False, indent=2)}

【系统硬风控约束基准 (账户净值: {account_equity:.2f}U)】:
{json.dumps(dump_risk_constants_summary(account_equity), ensure_ascii=False, indent=2)}

【历史自省白盒心法记忆】:
{trading_memory or "暂无历史教训，严格恪守纪律"}

请做出最终拍板决议，以标准 JSON 输出：
"""
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_CIO},
                {"role": "user", "content": user_content}
            ]

            raw_resp = await llm_gateway.generate_chat_completion(messages, temperature=0.1)
            decision = json.loads(raw_resp)
            decision["source"] = "llm_council_desk"
            return decision

        except Exception as e:
            logger.warning(f"LLM deliberation for {symbol} failed ({e}), falling back to deterministic quant engine.")
            return self._build_rule_based_fallback(symbol, current_price, factors, atr)


council_desk = InvestmentCouncilDesk()

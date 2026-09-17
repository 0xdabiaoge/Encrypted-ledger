"""
Encrypted Ledger - Multi-Agent Investment Council Desk
Simulates a Tier-1 quantitative hedge fund investment committee:
- Seat 1: Senior Trend-Pullback Trader (顺势波段操盘官)
- Seat 2: Senior Momentum-Breakout Trader (动能突破进攻官)
- Seat 3: Senior Quantitative & Microstructure Analyst (数理量化筹码官)
- Seat 4: Macro Sentiment & Black-Swan Sentinel (宏观舆情风控官)
- Seat 5: Chief Investment Officer (首席投资官 - 终审裁决)
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.council.council_policy import council_policy_manager
from app.council.llm_gateway import llm_gateway
from app.risk.constants import dump_risk_constants_summary


class InvestmentCouncilDesk:
    """
    Orchestrates the 4+1 multi-agent investment committee debate,
    cross-examinations, and CIO definitive trade contract generation.
    """

    def __init__(self):
        self._latest_deliberations: Dict[str, Any] = {}
        self._global_debate_history: List[Dict[str, Any]] = []

    def get_latest_debate_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent multi-agent deliberation debate records."""
        return self._global_debate_history[-limit:]

    def _generate_specialized_seat_opinions(
        self,
        symbol: str,
        current_price: float,
        factors: Dict[str, Any],
        macro_news: List[Dict[str, Any]],
        atr: float
    ) -> List[Dict[str, Any]]:
        """
        Generate specialized algorithmic proposals from the 4 analyst seats.
        Each seat focuses strictly on its domain of expertise.
        """
        seats_config = {s["id"]: s for s in council_policy_manager.get_seats()}
        opinions = []

        # 1. 顺势波段操盘官 (Trend-Pullback Trader)
        trend_pillar = factors.get("pillar_1_trend", {})
        adx = float(trend_pillar.get("adx", 20.0))
        trend_dir = trend_pillar.get("direction", "NEUTRAL")
        macro_4h = trend_pillar.get("macro_4h_channel", "NEUTRAL")

        if macro_4h == "BULLISH" and adx >= 22.0:
            t_action = "BUY"
            t_conf = min(92.0, 75.0 + adx * 0.5)
            t_entry = round(current_price * 0.998, 4)
            t_sl = round(current_price - 1.8 * atr, 4)
            t_tp = round(current_price + 2.5 * 1.8 * atr, 4)
            t_reason = f"4H宏观顺势多头通道明确，1H回踩关键均线支撑，ADX={adx:.1f}趋势强劲，坚决顺大势低吸反磨损。"
        elif macro_4h == "BEARISH" and adx >= 22.0:
            t_action = "SELL"
            t_conf = min(92.0, 75.0 + adx * 0.5)
            t_entry = round(current_price * 1.002, 4)
            t_sl = round(current_price + 1.8 * atr, 4)
            t_tp = round(current_price - 2.5 * 1.8 * atr, 4)
            t_reason = f"4H宏观空头承压结构，大周期反弹受阻均线压制，ADX={adx:.1f}，提议高空阻击破位。"
        else:
            t_action = "HOLD"
            t_conf = 55.0
            t_entry = current_price
            t_sl = 0.0
            t_tp = 0.0
            t_reason = f"宏观4H通道尚未确立强单边趋势 (ADX={adx:.1f})，建议克制盲目开仓，等待波段回踩确认。"

        trend_meta = seats_config.get("seat_trend", {})
        opinions.append({
            "seat_id": "seat_trend",
            "name": trend_meta.get("name", "顺势波段操盘官"),
            "role_title": trend_meta.get("role_title", "Senior Trend Trader"),
            "avatar": trend_meta.get("avatar", "📈"),
            "action": t_action,
            "confidence": round(t_conf, 1),
            "entry_target": t_entry,
            "stop_loss": t_sl,
            "take_profit": t_tp,
            "opinion": t_reason,
            "weight": trend_meta.get("weight", 0.25)
        })

        # 2. 动能突破进攻官 (Momentum-Breakout Trader)
        calc = factors.get("calculus", {})
        vel = float(calc.get("velocity", 0.0))
        acc = float(calc.get("acceleration", 0.0))
        burst = factors.get("pillar_3_volume", {}).get("volume_burst_ratio", 1.0)

        if vel > 0 and acc > 0 and burst >= 1.3:
            m_action = "BUY"
            m_conf = min(95.0, 80.0 + burst * 5.0)
            m_entry = round(current_price, 4)
            m_sl = round(current_price - 1.5 * atr, 4)
            m_tp = round(current_price + 2.4 * 1.5 * atr, 4)
            m_reason = f"微积分一阶速度v={vel:.4f}>0且二阶加速度a={acc:.4f}>0非线性爆发，量比放大{burst:.1f}倍，主张立即追击主升浪。"
        elif vel < 0 and acc < 0 and burst >= 1.3:
            m_action = "SELL"
            m_conf = min(95.0, 80.0 + burst * 5.0)
            m_entry = round(current_price, 4)
            m_sl = round(current_price + 1.5 * atr, 4)
            m_tp = round(current_price - 2.4 * 1.5 * atr, 4)
            m_reason = f"微积分下行速度扩大，二阶加速度急剧恶化，带量击穿支撑，主张动能做空。"
        else:
            m_action = "HOLD"
            m_conf = 50.0
            m_entry = current_price
            m_sl = 0.0
            m_tp = 0.0
            m_reason = f"动能指标平淡 (速度v={vel:.4f}, 加速度a={acc:.4f})，未检测到非线性突破临界点，假突破高危区严禁追单。"

        momentum_meta = seats_config.get("seat_momentum", {})
        opinions.append({
            "seat_id": "seat_momentum",
            "name": momentum_meta.get("name", "动能突破进攻官"),
            "role_title": momentum_meta.get("role_title", "Senior Momentum Trader"),
            "avatar": momentum_meta.get("avatar", "⚡"),
            "action": m_action,
            "confidence": round(m_conf, 1),
            "entry_target": m_entry,
            "stop_loss": m_sl,
            "take_profit": m_tp,
            "opinion": m_reason,
            "weight": momentum_meta.get("weight", 0.25)
        })

        # 3. 数理量化筹码官 (Quantitative & Microstructure Analyst)
        micro = factors.get("pillar_4_microstructure", {})
        smart = factors.get("pillar_5_smart_money", {})
        imb = float(micro.get("imbalance_ratio", 0.0))
        ratio = float(smart.get("long_short_account_ratio", 1.0))
        spread_bps = float(micro.get("spread_bps", 1.5))

        if imb > 0.15 and ratio <= 1.3 and spread_bps < 3.0:
            q_action = "BUY"
            q_conf = min(90.0, 78.0 + imb * 40.0)
            q_entry = round(current_price, 4)
            q_sl = round(current_price - 1.8 * atr, 4)
            q_tp = round(current_price + 2.2 * 1.8 * atr, 4)
            q_reason = f"盘口买盘失衡度显著占优 (Imbalance={imb*100:.1f}%)，散户多空比合理({ratio:.2f})未见拥挤拥堵，期望值E(X)显著为正。"
        elif imb < -0.15 and ratio >= 1.6 and spread_bps < 3.0:
            q_action = "SELL"
            q_conf = min(90.0, 78.0 + abs(imb) * 40.0)
            q_entry = round(current_price, 4)
            q_sl = round(current_price + 1.8 * atr, 4)
            q_tp = round(current_price - 2.2 * 1.8 * atr, 4)
            q_reason = f"盘口卖盘压单厚重 (Imbalance={imb*100:.1f}%)，多空散户比超买严重({ratio:.2f})主力暗中派发，空头赔率极佳。"
        else:
            q_action = "HOLD"
            q_conf = 52.0
            q_entry = current_price
            q_sl = 0.0
            q_tp = 0.0
            q_reason = f"盘口微观结构处于平衡胶着态 (Imbalance={imb*100:.1f}%)，滑点或大户持仓暂无显著统计套利优势。"

        quant_meta = seats_config.get("seat_quant", {})
        opinions.append({
            "seat_id": "seat_quant",
            "name": quant_meta.get("name", "数理量化筹码官"),
            "role_title": quant_meta.get("role_title", "Senior Quantitative Analyst"),
            "avatar": quant_meta.get("avatar", "🧮"),
            "action": q_action,
            "confidence": round(q_conf, 1),
            "entry_target": q_entry,
            "stop_loss": q_sl,
            "take_profit": q_tp,
            "opinion": q_reason,
            "weight": quant_meta.get("weight", 0.25)
        })

        # 4. 宏观舆情风控官 (Macro Sentiment & Sentinel)
        news_count = len(macro_news)
        has_black_swan = False
        news_summary = "全球宏观处于常态温和波动，未见黑天鹅恶性利空"

        black_swan_keywords = ["sec 调查", "binance 崩盘", "usdt 脱锚", "核危机", "战争爆发", "制裁", "停机", "冻结"]
        for item in macro_news[:8]:
            title = str(item.get("title", "")).lower()
            if any(k in title for k in black_swan_keywords):
                has_black_swan = True
                news_summary = f"捕获重大潜在尾部风险快讯: {item.get('title')[:30]}..."
                break

        if has_black_swan:
            mc_action = "HOLD"
            mc_conf = 95.0
            mc_reason = f"【重大警报】检测到宏观极值风险事件，行使风控一票否决权，绝对禁止开仓开辟新敞口！"
        else:
            mc_action = "HOLD" if t_action == "HOLD" and m_action == "HOLD" else (t_action if t_action == m_action else "HOLD")
            mc_conf = 82.0
            mc_reason = f"7x24宏观情报正常接入 ({news_count}条)，市场总体情绪平稳，允许在物理风控预算内执行高期望值策略。"

        macro_meta = seats_config.get("seat_macro", {})
        opinions.append({
            "seat_id": "seat_macro",
            "name": macro_meta.get("name", "宏观舆情风控官"),
            "role_title": macro_meta.get("role_title", "Macro & Sentiment Sentinel"),
            "avatar": macro_meta.get("avatar", "🛡️"),
            "action": mc_action,
            "confidence": round(mc_conf, 1),
            "entry_target": current_price,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "opinion": mc_reason,
            "weight": macro_meta.get("weight", 0.25)
        })

        return opinions

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
        Execute multi-agent council debate across all active seats and produce
        the final CIO synthesis contract.
        """
        atr = float(factors.get("pillar_2_volatility", {}).get("atr", current_price * 0.015))

        # 1. Gather baseline opinions from the 4 specialized seats
        seat_opinions = self._generate_specialized_seat_opinions(
            symbol=symbol,
            current_price=current_price,
            factors=factors,
            macro_news=macro_news,
            atr=atr
        )

        seats_config = {s["id"]: s for s in council_policy_manager.get_seats()}

        # 1.1 For seats with assigned LLM models, execute independent LLM reasoning
        for op in seat_opinions:
            seat_id = op.get("seat_id")
            s_cfg = seats_config.get(seat_id, {})
            model_id = s_cfg.get("model_id")
            if model_id:
                try:
                    s_prompt = s_cfg.get("prompt") or op.get("opinion")
                    s_temp = float(s_cfg.get("temperature", 0.2))
                    u_content = (
                        f"待研判标的: {symbol}, 当前基准价: {current_price}, ATR: {atr:.2f}\n"
                        f"五大因子指标: {json.dumps(factors, ensure_ascii=False)}\n"
                        f"宏观要闻: {json.dumps(macro_news[:3], ensure_ascii=False)}\n"
                        "请根据你的专属席位角色哲学与审查要点，输出严格 JSON "
                        '(格式: {"action": "BUY"|"SELL"|"HOLD", "confidence": float, "entry_target": float, "stop_loss": float, "take_profit": float, "opinion": "80字内简述"}):'
                    )
                    s_messages = [
                        {"role": "system", "content": s_prompt},
                        {"role": "user", "content": u_content}
                    ]
                    raw_s = await llm_gateway.generate_with_model_id(model_id, s_messages, temperature=s_temp)
                    parsed_s = json.loads(raw_s)
                    if parsed_s.get("action") in ("BUY", "SELL", "HOLD"):
                        op["action"] = parsed_s["action"]
                    if "confidence" in parsed_s and parsed_s["confidence"] is not None:
                        op["confidence"] = float(parsed_s["confidence"])
                    if "entry_target" in parsed_s and parsed_s["entry_target"]:
                        op["entry_target"] = float(parsed_s["entry_target"])
                    if "stop_loss" in parsed_s and parsed_s["stop_loss"]:
                        op["stop_loss"] = float(parsed_s["stop_loss"])
                    if "take_profit" in parsed_s and parsed_s["take_profit"]:
                        op["take_profit"] = float(parsed_s["take_profit"])
                    if parsed_s.get("opinion"):
                        op["opinion"] = str(parsed_s["opinion"])[:100]
                    op["llm_model_used"] = model_id
                except Exception as e:
                    logger.warning(f"Seat {seat_id} LLM reasoning with model {model_id} failed ({e}), keeping algorithmic baseline.")

        # 2. Check if LLM is configured for CIO arbitration
        cio_cfg = council_policy_manager.get_seat("seat_cio") or {}
        cio_model_id = cio_cfg.get("model_id")
        has_cio_model = bool(cio_model_id) or bool(settings.LLM_API_KEY)

        if has_cio_model:
            try:
                cio_system = cio_cfg.get("prompt") if cio_cfg else "你现在是 Encrypted Ledger 首席投资官 (CIO)。"

                user_content = f"""
【待审阅交易标的】: {symbol}
【当前基准市价】: {current_price}

【投委会四大席位研判提案】:
{json.dumps(seat_opinions, ensure_ascii=False, indent=2)}

【标的五大因子矩阵】:
{json.dumps(factors, ensure_ascii=False, indent=2)}

【近期全球宏观要闻】:
{json.dumps(macro_news[:5], ensure_ascii=False, indent=2)}

【执行层 17 项物理风控约束 (账户总净值: {account_equity:.2f} USDT)】:
{json.dumps(dump_risk_constants_summary(account_equity), ensure_ascii=False, indent=2)}

【历史自省白盒心法】:
{trading_memory or "严守纪律，保本第一"}

请进行最高终审裁决，以标准 JSON 输出最终决议（包含 consensus_summary 与 reasoning 字段）：
"""
                messages = [
                    {"role": "system", "content": cio_system},
                    {"role": "user", "content": user_content}
                ]
                raw_resp = await llm_gateway.generate_with_model_id(cio_model_id, messages, temperature=float(cio_cfg.get("temperature", 0.1)))
                decision = json.loads(raw_resp)
                decision["source"] = f"multi_agent_llm_council ({cio_model_id or 'default'})"
                decision["debate_transcript"] = seat_opinions
                decision["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

                self._record_debate(symbol, decision)
                return decision

            except Exception as e:
                logger.warning(f"LLM multi-agent arbitration failed ({e}), falling back to deterministic consensus engine.")

        # 3. Deterministic Consensus Engine (Rule-based CIO arbitration)
        buy_votes = sum(s["weight"] for s in seat_opinions if s["action"] == "BUY")
        sell_votes = sum(s["weight"] for s in seat_opinions if s["action"] == "SELL")
        hold_votes = sum(s["weight"] for s in seat_opinions if s["action"] == "HOLD")

        macro_seat = next((s for s in seat_opinions if s["seat_id"] == "seat_macro"), None)
        is_vetoed_by_macro = macro_seat and "一票否决" in macro_seat.get("opinion", "")

        if is_vetoed_by_macro or hold_votes >= 0.50:
            final_action = "HOLD"
            final_conf = 60.0
            final_entry = current_price
            final_sl = 0.0
            final_tp = 0.0
            final_rr = 0.0
            cio_summary = "投委会达成共识：当前宏观或盘口未形成强一致共振，严守资本安全，执行空仓待机。"
            cio_reason = "席位分歧较大或宏观存在不确定性，不符合高置信度 (>=80%) 严苛入场标准。"
        elif buy_votes >= 0.50:
            final_action = "BUY"
            final_conf = round(min(94.0, 78.0 + buy_votes * 18.0), 1)
            sl_dist = 1.8 * atr if atr > 0 else current_price * 0.015
            final_entry = round(current_price, 4)
            final_sl = round(current_price - sl_dist, 4)
            final_tp = round(current_price + 2.3 * sl_dist, 4)
            final_rr = round((final_tp - final_entry) / (final_entry - final_sl), 2)
            cio_summary = f"投委会加权赞成开多 (赞成权重: {buy_votes*100:.0f}%)：顺势波段与微积分动能同向共振，多头胜率突出。"
            cio_reason = f"CIO终审通过开多提案：几何盈亏比R:R={final_rr}>=2.0，入场置信度{final_conf}%满足门禁，附带原生防滑点止损单。"
        elif sell_votes >= 0.50:
            final_action = "SELL"
            final_conf = round(min(94.0, 78.0 + sell_votes * 18.0), 1)
            sl_dist = 1.8 * atr if atr > 0 else current_price * 0.015
            final_entry = round(current_price, 4)
            final_sl = round(current_price + sl_dist, 4)
            final_tp = round(current_price - 2.3 * sl_dist, 4)
            final_rr = round((final_entry - final_tp) / (final_sl - final_entry), 2)
            cio_summary = f"投委会加权赞成做空 (做空权重: {sell_votes*100:.0f}%)：大周期承压，盘口卖盘压制，空头动能发散。"
            cio_reason = f"CIO终审通过做空提案：几何盈亏比R:R={final_rr}>=2.0，入场置信度{final_conf}%满足门禁。"
        else:
            final_action = "HOLD"
            final_conf = 50.0
            final_entry = current_price
            final_sl = 0.0
            final_tp = 0.0
            final_rr = 0.0
            cio_summary = "投委会博弈陷入僵局，各席位权重均衡且未达确定性阈值，执行观望。"
            cio_reason = "多空博弈无单边优势，严禁在震荡杂波中过度交易磨损本金。"

        decision = {
            "symbol": symbol,
            "action": final_action,
            "confidence": final_conf,
            "suggested_leverage": 3.0,
            "entry_target_price": final_entry,
            "stop_loss_price": final_sl,
            "take_profit_price": final_tp,
            "risk_reward_ratio": final_rr,
            "consensus_summary": cio_summary,
            "reasoning": cio_reason,
            "source": "deterministic_multi_agent_consensus",
            "debate_transcript": seat_opinions,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self._record_debate(symbol, decision)
        return decision

    def _record_debate(self, symbol: str, decision: Dict[str, Any]) -> None:
        """Cache latest multi-agent debate for UI consumption."""
        self._latest_deliberations[symbol] = decision
        self._global_debate_history.append({
            "symbol": symbol,
            "action": decision.get("action"),
            "confidence": decision.get("confidence"),
            "consensus_summary": decision.get("consensus_summary"),
            "timestamp": decision.get("timestamp"),
            "debate_transcript": decision.get("debate_transcript", [])
        })
        if len(self._global_debate_history) > 50:
            self._global_debate_history.pop(0)

    def get_latest_symbol_debate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest debate for a specific coin."""
        return self._latest_deliberations.get(symbol)


council_desk = InvestmentCouncilDesk()

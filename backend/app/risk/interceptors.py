"""
Encrypted Ledger - Fail-Closed Python Physical Interceptors
Non-bypassable execution gatekeeper pipeline. If any check fails or raises an error, orders are blocked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.intelligence.circuit_breaker import circuit_breaker
from app.risk.constants import (
    get_effective_1r_risk_budget,
    get_effective_single_asset_margin,
)


@dataclass
class InterceptResult:
    passed: bool
    blocked_by: str
    reason: str
    details: Dict[str, Any]


class PhysicalInterceptorPipeline:
    """Institutional execution-layer physical gatekeeper pipeline."""

    @staticmethod
    def evaluate_order_intent(
        symbol: str,
        side: str,                  # "buy" (long) | "sell" (short)
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        confidence: float,
        notional_usd: float,
        leverage: float,
        account_balance_usd: float,
        current_positions: List[Any],
        factor_snapshot: Dict[str, Any],
        candles_4h: Optional[List[Dict[str, Any]]] = None
    ) -> InterceptResult:
        """
        Runs the full Fail-Closed physical check pipeline.
        Any exception or constraint violation leads to immediate rejection.
        """
        try:
            # ------------------------------------------------------------------
            # Gate 0: Black-Swan Circuit Breaker
            # ------------------------------------------------------------------
            is_cb_active, cb_data = circuit_breaker.is_active()
            if is_cb_active:
                return InterceptResult(
                    passed=False,
                    blocked_by="00_CIRCUIT_BREAKER",
                    reason=f"黑天鹅熔断处于激活状态: {cb_data.get('keyword', '')} - {cb_data.get('action', '')}",
                    details={"circuit_breaker": cb_data}
                )

            # ------------------------------------------------------------------
            # Gate 1: Confidence Gatekeeper (AI 置信度门禁)
            # ------------------------------------------------------------------
            conf_threshold = settings.RISK_MIN_ENTRY_CONFIDENCE
            if confidence < conf_threshold:
                return InterceptResult(
                    passed=False,
                    blocked_by="01_CONFIDENCE_GATEKEEPER",
                    reason=f"AI 置信度不足 ({confidence:.1f}% < 门禁 {conf_threshold:.1f}%)，强制观望",
                    details={"confidence": confidence, "threshold": conf_threshold}
                )

            # ------------------------------------------------------------------
            # Gate 2: ADX Volatility & Chop Filter (趋势杂波过滤)
            # ------------------------------------------------------------------
            p1_trend = factor_snapshot.get("pillar_1_trend", {})
            adx = float(p1_trend.get("adx", 20.0))
            if adx < 18.0:
                return InterceptResult(
                    passed=False,
                    blocked_by="02_ADX_VOLATILITY_FILTER",
                    reason=f"1H ADX 趋势强度过低 ({adx:.1f} < 18.0)，处于无序震荡垃圾市，严禁开仓",
                    details={"adx": adx}
                )

            # ------------------------------------------------------------------
            # Gate 3: Geometric 2.0R Risk-Reward (真实 2.0R 盈亏比硬门禁)
            # ------------------------------------------------------------------
            if entry_price <= 0 or stop_loss_price <= 0 or take_profit_price <= 0:
                return InterceptResult(
                    passed=False,
                    blocked_by="03_RISK_REWARD_GATEKEEPER",
                    reason="无效的价格几何配置（入场价/止损价/止盈价必须大于0）",
                    details={"entry": entry_price, "sl": stop_loss_price, "tp": take_profit_price}
                )

            is_long = (side.lower() == "buy")
            if is_long:
                if stop_loss_price >= entry_price or take_profit_price <= entry_price:
                    return InterceptResult(
                        passed=False,
                        blocked_by="03_RISK_REWARD_GATEKEEPER",
                        reason="做多几何方向错误：止损价必须低于入场价，止盈价必须高于入场价",
                        details={"entry": entry_price, "sl": stop_loss_price, "tp": take_profit_price}
                    )
                risk_dist = entry_price - stop_loss_price
                reward_dist = take_profit_price - entry_price
            else:
                if stop_loss_price <= entry_price or take_profit_price >= entry_price:
                    return InterceptResult(
                        passed=False,
                        blocked_by="03_RISK_REWARD_GATEKEEPER",
                        reason="做空几何方向错误：止损价必须高于入场价，止盈价必须低于入场价",
                        details={"entry": entry_price, "sl": stop_loss_price, "tp": take_profit_price}
                    )
                risk_dist = stop_loss_price - entry_price
                reward_dist = entry_price - take_profit_price

            if risk_dist <= 0:
                return InterceptResult(
                    passed=False,
                    blocked_by="03_RISK_REWARD_GATEKEEPER",
                    reason="风险距离不能为零或负数",
                    details={"risk_dist": risk_dist}
                )

            rr_ratio = reward_dist / risk_dist
            min_rr = settings.RISK_MIN_RISK_REWARD
            if rr_ratio < min_rr - 0.01:  # Allow 0.01 float tolerance
                return InterceptResult(
                    passed=False,
                    blocked_by="03_RISK_REWARD_GATEKEEPER",
                    reason=f"盈亏比不达标 (真实盈亏比 R:R = {rr_ratio:.2f} < 刚性底线 {min_rr:.1f})",
                    details={"calculated_rr": round(rr_ratio, 2), "min_rr": min_rr}
                )

            # ------------------------------------------------------------------
            # Gate 4: 4H Macro Trend Alignment (4H 大周期顺势铁律)
            # ------------------------------------------------------------------
            if candles_4h and len(candles_4h) >= 20:
                closes_4h = [c["close"] for c in candles_4h]
                ema20_4h = sum(closes_4h[-20:]) / 20.0
                curr_px = closes_4h[-1]
                if is_long and curr_px < ema20_4h * 0.965:
                    return InterceptResult(
                        passed=False,
                        blocked_by="04_MACRO_TREND_FILTER",
                        reason="4H 宏观处于严重空头承压通道，严禁逆势摸顶或接飞刀做多",
                        details={"curr_px": curr_px, "ema20_4h": ema20_4h}
                    )
                elif not is_long and curr_px > ema20_4h * 1.035:
                    return InterceptResult(
                        passed=False,
                        blocked_by="04_MACRO_TREND_FILTER",
                        reason="4H 宏观处于强大多头扩张通道，严禁逆势摸顶开空",
                        details={"curr_px": curr_px, "ema20_4h": ema20_4h}
                    )

            # ------------------------------------------------------------------
            # Gate 5: Position & Exposure Limits (敞口与同向持仓上限)
            # ------------------------------------------------------------------
            same_dir_count = sum(1 for p in current_positions if (p.side.lower() == ("long" if is_long else "short")))
            if same_dir_count >= settings.RISK_MAX_SAME_DIRECTION_POSITIONS:
                return InterceptResult(
                    passed=False,
                    blocked_by="05_EXPOSURE_LIMIT",
                    reason=f"已达同向持仓上限 ({same_dir_count} 仓 >= 上限 {settings.RISK_MAX_SAME_DIRECTION_POSITIONS} 仓)，防止 Beta 踩踏",
                    details={"same_dir_count": same_dir_count, "cap": settings.RISK_MAX_SAME_DIRECTION_POSITIONS}
                )

            # Margin limit check
            required_margin = notional_usd / leverage if leverage > 0 else notional_usd
            max_margin = account_balance_usd * settings.RISK_MAX_MARGIN_EQUITY_RATIO
            if required_margin > max_margin:
                return InterceptResult(
                    passed=False,
                    blocked_by="05_MARGIN_LIMIT",
                    reason=f"单笔所需保证金 ({required_margin:.2f}U) 超过账户可用 20% 硬顶 ({max_margin:.2f}U)",
                    details={"required_margin": required_margin, "max_margin": max_margin}
                )

            # All gates passed
            return InterceptResult(
                passed=True,
                blocked_by="",
                reason="All physical fail-closed gates passed successfully.",
                details={"calculated_rr": round(rr_ratio, 2), "confidence": confidence}
            )

        except Exception as e:
            logger.critical(f"Physical interceptor raised unhandled exception, triggering fail-closed: {e}")
            return InterceptResult(
                passed=False,
                blocked_by="FAIL_CLOSED_EXCEPTION",
                reason=f"拦截管线执行异常，触发 Fail-Closed 熔断拒绝: {str(e)}",
                details={"error": str(e)}
            )


interceptor_pipeline = PhysicalInterceptorPipeline()

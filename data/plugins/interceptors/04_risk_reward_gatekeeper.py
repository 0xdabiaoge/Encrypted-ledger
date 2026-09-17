"""
[Plugin] 几何盈亏比不变量硬门禁 (2.0R Risk-Reward Gatekeeper)
Version: 1.0.0
Author: Quantum Risk Sentinel
Description: 强校验止盈与止损空间比率，必须预期收益率 / 最大可能回撤 >= 2.0。
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    entry = float(decision.get("entry_price", 0.0) or 0.0)
    tp = float(decision.get("take_profit_price", 0.0) or 0.0)
    sl = float(decision.get("stop_loss_price", 0.0) or 0.0)
    action = str(decision.get("action", "") or "").upper()

    if entry <= 0 or tp <= 0 or sl <= 0:
        return False, "缺少有效的入场价、止盈价或止损价"

    if action == "BUY_LONG":
        risk = entry - sl
        reward = tp - entry
    elif action == "SELL_SHORT":
        risk = sl - entry
        reward = entry - tp
    else:
        return True, "观望指令跳过盈亏比校验"

    if risk <= 0:
        return False, "止损价格设置与开仓方向几何逻辑颠倒"
    if reward <= 0:
        return False, "止盈价格设置与开仓方向几何逻辑颠倒"

    rr = reward / risk
    if rr < 2.0:
        return False, f"预期盈亏比过低 ({rr:.2f}R < 机构级底线 2.0R)，阻断开仓"

    return True, f"盈亏比达标 ({rr:.2f}R >= 2.0R)"

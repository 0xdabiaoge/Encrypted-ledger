"""
[Plugin] 宏观多空通道趋势过滤器 (Macro Trend Filter)
Version: 1.0.0
Author: Quantum Risk Sentinel
Description: 严禁在大级别多头通道中逆势做空，或在空头通道中逆势做多。
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    macro = str(package.get("macro_4h", "") or "").upper()
    action = str(decision.get("action", "") or "").upper()

    if "BULL" in macro and action == "SELL_SHORT":
        return False, "4H 处于强多头通道，严禁逆势摸顶做空 (Macro Trend Block)"
    if "BEAR" in macro and action == "BUY_LONG":
        return False, "4H 处于强空头通道，严禁逆势抄底做多 (Macro Trend Block)"

    return True, "宏观趋势顺势过滤校验通过"

"""
[Plugin] 智能体置信度安全门禁 (Confidence Gatekeeper)
Version: 1.0.0
Author: Quantum Risk Sentinel
Description: 拦截所有低于动态置信度安全底线 (80%) 的低确定性开仓指令。
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    confidence = float(decision.get("confidence", 0.0) or 0.0)
    inst_id = str(package.get("instId", "") or package.get("symbol", "")).upper()

    # 高频/高波动标的强制 82% 门禁，一般标的 80%
    threshold = 82.0 if any(m in inst_id for m in ["DOGE", "PEPE", "SHIB", "BONK"]) else 80.0
    if confidence < threshold:
        return False, f"AI 决策置信度不足 ({confidence:.1f}% < 门限 {threshold:.1f}%)，拦截入场"

    return True, f"AI 置信度达标 ({confidence:.1f}% >= {threshold:.1f}%)"

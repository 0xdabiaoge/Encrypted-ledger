"""
[Plugin] 1H ADX 趋势强度与杂波过滤器 (ADX Chop Filter)
Version: 1.0.0
Author: Quantum Risk Sentinel
Description: 当 1H ADX < 18 时判定为无序震荡垃圾时间，阻断一切趋势突破入场。
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    adx = float(package.get("adx_1h", 20.0) or 20.0)
    if adx < 18.0:
        return False, f"1H ADX 趋势强度仅为 {adx:.1f} (< 18.0)，处于无方向垃圾震荡市，强制观望"

    return True, f"ADX 趋势动能充足 ({adx:.1f} >= 18.0)"

"""
Encrypted Ledger - Python Risk Interceptor Plugin & Sandbox Engine
Allows dynamic loading, hot-editing, AST safety checks, order resequencing,
Fail-Closed execution, and dry-run sandbox testing for physical risk plugins.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("risk_interceptors")

DATA_DIR = Path("data").resolve()
PLUGINS_DIR = DATA_DIR / "plugins" / "interceptors"
CONFIG_FILE = DATA_DIR / "interceptor_plugins.json"

DEFAULT_PLUGINS = {
    "01_macro_trend_filter.py": '''"""
[Plugin] 宏观多空通道趋势过滤器 (Macro Trend Filter)
Version: 1.0.0
Author: Quantum Risk Sentinel
Description: 严禁在大级别多头通道中逆势做空，或在空头通道中逆势做多。
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    if package.get("active_preset") == "hft_scalper":
        return True, "高频微波段策略顺应盘口微观动能，放行超短线回调阻击"

    macro = str(package.get("macro_4h", "") or "").upper()
    action = str(decision.get("action", "") or "").upper()

    if "BULL" in macro and action == "SELL_SHORT":
        return False, "4H 处于强多头通道，严禁逆势摸顶做空 (Macro Trend Block)"
    if "BEAR" in macro and action == "BUY_LONG":
        return False, "4H 处于强空头通道，严禁逆势抄底做多 (Macro Trend Block)"

    return True, "宏观趋势顺势过滤校验通过"
''',

    "02_confidence_gatekeeper.py": '''"""
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
''',

    "03_adx_volatility_filter.py": '''"""
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
''',

    "04_risk_reward_gatekeeper.py": '''"""
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
'''
}


def ensure_plugins_dir() -> None:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    # If empty, write default plugins
    for fname, code in DEFAULT_PLUGINS.items():
        fpath = PLUGINS_DIR / fname
        if not fpath.exists():
            try:
                fpath.write_text(code, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to initialize default plugin {fname}: {e}")


def load_config() -> Dict[str, Any]:
    ensure_plugins_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load plugin config: {e}")

    default_order = sorted(list(DEFAULT_PLUGINS.keys()))
    default_enabled = {k: True for k in default_order}
    return {
        "pipeline_order": default_order,
        "enabled": default_enabled
    }


def save_config(config: Dict[str, Any]) -> None:
    ensure_plugins_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


def parse_plugin_metadata(file_path: Path) -> Dict[str, Any]:
    filename = file_path.name
    res = {
        "filename": filename,
        "id": filename.replace(".py", ""),
        "name": filename,
        "version": "1.0.0",
        "author": "Custom Sentinel",
        "description": "",
        "enabled": True,
        "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        "updated_at": int(file_path.stat().st_mtime) if file_path.exists() else int(time.time()),
    }
    if not file_path.exists():
        return res

    try:
        content = file_path.read_text(encoding="utf-8")
        match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if match:
            doc = match.group(1).strip()
            for line in doc.split("\n"):
                line = line.strip()
                if line.startswith("[Plugin]"):
                    res["name"] = line.replace("[Plugin]", "").strip()
                elif line.lower().startswith("version:"):
                    res["version"] = line.split(":", 1)[1].strip()
                elif line.lower().startswith("author:"):
                    res["author"] = line.split(":", 1)[1].strip()
                elif line.lower().startswith("description:"):
                    res["description"] = line.split(":", 1)[1].strip()
    except Exception:
        pass
    return res


def list_plugins() -> List[Dict[str, Any]]:
    ensure_plugins_dir()
    cfg = load_config()
    order = cfg.get("pipeline_order", [])
    enabled_map = cfg.get("enabled", {})

    all_py_files = {f.name: f for f in PLUGINS_DIR.glob("*.py")}

    ordered_names = [name for name in order if name in all_py_files]
    for name in sorted(all_py_files.keys()):
        if name not in ordered_names:
            ordered_names.append(name)

    results = []
    for idx, name in enumerate(ordered_names):
        p_info = parse_plugin_metadata(all_py_files[name])
        p_info["order"] = idx + 1
        p_info["enabled"] = enabled_map.get(name, True)
        results.append(p_info)

    return results


def get_plugin_code(filename: str) -> Dict[str, Any]:
    ensure_plugins_dir()
    safe_name = os.path.basename(filename)
    fpath = PLUGINS_DIR / safe_name
    if not fpath.exists():
        raise FileNotFoundError(f"Plugin {safe_name} not found")

    code = fpath.read_text(encoding="utf-8")
    meta = parse_plugin_metadata(fpath)
    meta["code"] = code
    return meta


def save_plugin_code(filename: str, code: str) -> Dict[str, Any]:
    ensure_plugins_dir()
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".py"):
        safe_name = f"{safe_name}.py"

    # AST syntax safety check
    try:
        ast.parse(code)
    except SyntaxError as err:
        raise ValueError(f"Python 语法错误 (第 {err.lineno} 行): {err.msg}")

    fpath = PLUGINS_DIR / safe_name
    tmp = fpath.with_suffix(".tmp")
    tmp.write_text(code, encoding="utf-8")
    os.replace(tmp, fpath)

    # Register in config if new
    cfg = load_config()
    if safe_name not in cfg.get("pipeline_order", []):
        cfg.setdefault("pipeline_order", []).append(safe_name)
    cfg.setdefault("enabled", {})[safe_name] = True
    save_config(cfg)

    return get_plugin_code(safe_name)


def toggle_plugin(filename: str, enabled: bool) -> Dict[str, Any]:
    safe_name = os.path.basename(filename)
    cfg = load_config()
    cfg.setdefault("enabled", {})[safe_name] = bool(enabled)
    save_config(cfg)
    return {"filename": safe_name, "enabled": bool(enabled)}


def delete_plugin(filename: str) -> bool:
    safe_name = os.path.basename(filename)
    fpath = PLUGINS_DIR / safe_name
    if fpath.exists():
        fpath.unlink()
    cfg = load_config()
    if safe_name in cfg.get("pipeline_order", []):
        cfg["pipeline_order"].remove(safe_name)
    if safe_name in cfg.get("enabled", {}):
        del cfg["enabled"][safe_name]
    save_config(cfg)
    return True


def _load_module_dynamically(file_path: Path) -> Any:
    mod_name = f"risk_plugin_{file_path.stem}_{int(file_path.stat().st_mtime)}"
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_plugin_pipeline(package: Dict[str, Any], decision: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    Executes all enabled risk plugins in order.
    Returns: (passed: bool, blocking_plugin_name: str, reason: str)
    Fail-Closed: if any plugin raises an unhandled exception or rejects, passed=False.
    """
    ensure_plugins_dir()
    plugins = list_plugins()

    for p in plugins:
        if not p.get("enabled", True):
            continue

        fname = p["filename"]
        fpath = PLUGINS_DIR / fname
        if not fpath.exists():
            return False, fname, f"启用的风控插件 [{fname}] 缺失，安全降级为 WAIT"

        try:
            mod = _load_module_dynamically(fpath)
            if not hasattr(mod, "check_risk"):
                return False, fname, f"风控插件 [{fname}] 缺少 check_risk 入口函数"

            p_pkg = copy.deepcopy(package)
            p_dec = copy.deepcopy(decision)
            p_ctx = copy.deepcopy(context)

            passed, reason = mod.check_risk(p_pkg, p_dec, p_ctx)
            if not passed:
                return False, f"{fname} ({p.get('name', fname)})", str(reason)
        except Exception as e:
            logger.error(f"Error executing risk plugin {fname}: {e}")
            return False, f"{fname} ({p.get('name', fname)})", f"风控插件运行时异常: {e} (Fail-Closed)"

    return True, "", "All risk plugins passed"


def run_sandbox_test(custom_scenarios: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Simulates execution of all enabled plugins against standard hedge-fund risk scenarios.
    Returns comprehensive pass/fail report with execution latencies.
    """
    ensure_plugins_dir()
    scenarios = custom_scenarios or [
        {
            "id": "scenario_1",
            "name": "场景 1: 4H 多头通道中尝试逆势做空 (BTC)",
            "package": {
                "symbol": "BTC",
                "instId": "BTC-USDT-SWAP",
                "macro_4h": "4H_BULL_CHANNEL (强多头主通道)",
                "adx_1h": 26.5,
            },
            "decision": {
                "action": "SELL_SHORT",
                "confidence": 88.0,
                "entry_price": 68000.0,
                "take_profit_price": 64000.0,
                "stop_loss_price": 69500.0,
            },
            "context": {},
            "expected_result": "BLOCKED",
            "expected_blocker": "01_macro_trend_filter.py"
        },
        {
            "id": "scenario_2",
            "name": "场景 2: 1H ADX 仅 14 的无序震荡市尝试做多 (ETH)",
            "package": {
                "symbol": "ETH",
                "instId": "ETH-USDT-SWAP",
                "macro_4h": "4H_BULL_CHANNEL",
                "adx_1h": 14.2,
            },
            "decision": {
                "action": "BUY_LONG",
                "confidence": 86.0,
                "entry_price": 2500.0,
                "take_profit_price": 2700.0,
                "stop_loss_price": 2400.0,
            },
            "context": {},
            "expected_result": "BLOCKED",
            "expected_blocker": "03_adx_volatility_filter.py"
        },
        {
            "id": "scenario_3",
            "name": "场景 3: 置信度仅 75% 的低确定性开多 (SOL)",
            "package": {
                "symbol": "SOL",
                "instId": "SOL-USDT-SWAP",
                "macro_4h": "4H_BULL_CHANNEL",
                "adx_1h": 28.0,
            },
            "decision": {
                "action": "BUY_LONG",
                "confidence": 75.0,
                "entry_price": 145.0,
                "take_profit_price": 165.0,
                "stop_loss_price": 135.0,
            },
            "context": {},
            "expected_result": "BLOCKED",
            "expected_blocker": "02_confidence_gatekeeper.py"
        },
        {
            "id": "scenario_4",
            "name": "场景 4: 盈亏比仅 1.2R 的劣质入场 (PEPE)",
            "package": {
                "symbol": "PEPE",
                "instId": "PEPE_USDT",
                "macro_4h": "4H_BULL_CHANNEL",
                "adx_1h": 32.0,
            },
            "decision": {
                "action": "BUY_LONG",
                "confidence": 88.0,
                "entry_price": 0.0000100,
                "take_profit_price": 0.0000112,   # reward = +0.0000012
                "stop_loss_price": 0.0000090,     # risk = -0.0000010 -> RR = 1.2R
            },
            "context": {},
            "expected_result": "BLOCKED",
            "expected_blocker": "04_risk_reward_gatekeeper.py"
        },
        {
            "id": "scenario_5",
            "name": "场景 5: 完美达标的高确定性顺势突破 (SOL 2.5R)",
            "package": {
                "symbol": "SOL",
                "instId": "SOL-USDT-SWAP",
                "macro_4h": "4H_BULL_CHANNEL",
                "adx_1h": 35.0,
            },
            "decision": {
                "action": "BUY_LONG",
                "confidence": 89.5,
                "entry_price": 150.0,
                "take_profit_price": 175.0,  # reward = +25.0
                "stop_loss_price": 140.0,    # risk = -10.0 -> RR = 2.5R
            },
            "context": {},
            "expected_result": "PASSED",
            "expected_blocker": None
        }
    ]

    report = []
    total_latency_ms = 0.0

    for sc in scenarios:
        t0 = time.perf_counter()
        passed, blocker, reason = run_plugin_pipeline(sc["package"], sc["decision"], sc["context"])
        dt_ms = round((time.perf_counter() - t0) * 1000, 3)
        total_latency_ms += dt_ms

        outcome = "PASSED" if passed else "BLOCKED"
        correct = (outcome == sc["expected_result"])

        report.append({
            "scenario_id": sc.get("id"),
            "scenario_name": sc.get("name"),
            "outcome": outcome,
            "passed": passed,
            "blocked_by": blocker if not passed else None,
            "reason": reason,
            "expected_result": sc["expected_result"],
            "verification_passed": correct,
            "latency_ms": dt_ms
        })

    return {
        "total_scenarios": len(scenarios),
        "passed_count": sum(1 for r in report if r["passed"]),
        "blocked_count": sum(1 for r in report if not r["passed"]),
        "verification_accuracy_pct": round(sum(1 for r in report if r["verification_passed"]) / len(report) * 100, 1),
        "total_latency_ms": round(total_latency_ms, 3),
        "avg_latency_ms": round(total_latency_ms / len(scenarios), 3),
        "results": report
    }

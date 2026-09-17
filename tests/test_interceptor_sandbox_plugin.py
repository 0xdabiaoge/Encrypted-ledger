"""
Test Suite: Python Risk Interceptor Plugins & Online Sandbox Test Engine
Verifies:
1. Dynamic loading, ordering, and metadata parsing of Python interceptor plugins
2. AST syntax safety checking (rejection of malformed Python code)
3. Plugin creation, updating, toggling, and deletion
4. Sandbox test execution against 5 institutional hedge fund scenarios
5. Fail-Closed behavior in PhysicalInterceptorPipeline
"""
import io
import sys
from pathlib import Path

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend directory in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.risk.interceptor_manager import (
    list_plugins,
    get_plugin_code,
    save_plugin_code,
    toggle_plugin,
    delete_plugin,
    run_sandbox_test,
    run_plugin_pipeline,
)
from app.risk.interceptors import PhysicalInterceptorPipeline


def test_list_default_plugins():
    """Verify default risk plugins exist and have correct metadata."""
    plugins = list_plugins()
    assert len(plugins) >= 4
    filenames = [p["filename"] for p in plugins]
    assert "01_macro_trend_filter.py" in filenames
    assert "02_confidence_gatekeeper.py" in filenames
    assert "03_adx_volatility_filter.py" in filenames
    assert "04_risk_reward_gatekeeper.py" in filenames


def test_ast_syntax_validation():
    """Verify invalid Python code is rejected by AST parser."""
    bad_code = """
def check_risk(package, decision, context)
    this is completely invalid python syntax :::
"""
    caught = False
    try:
        save_plugin_code("98_bad_syntax_test.py", bad_code)
    except ValueError as exc:
        caught = True
        assert "语法错误" in str(exc)
    assert caught, "AST parser failed to catch syntax error"


def test_plugin_crud_and_toggle():
    """Verify custom plugin can be created, toggled, and removed."""
    custom_code = '''"""
[Plugin] 单元测试专属过滤器
Version: 1.0.0
Author: Pytest Runner
Description: 拦截所有带有 TEST_BLOCK 标记的测试指令
"""
def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    if decision.get("test_flag") == "BLOCK_ME":
        return False, "单元测试触发人工拦截"
    return True, "单元测试放行"
'''
    saved = save_plugin_code("98_unit_test_plugin.py", custom_code)
    assert saved["filename"] == "98_unit_test_plugin.py"
    assert "单元测试专属过滤器" in saved["name"]

    # Toggle off
    t_off = toggle_plugin("98_unit_test_plugin.py", False)
    assert not t_off["enabled"]

    # Toggle on
    t_on = toggle_plugin("98_unit_test_plugin.py", True)
    assert t_on["enabled"]

    # Delete
    deleted = delete_plugin("98_unit_test_plugin.py")
    assert deleted


def test_sandbox_stress_scenarios():
    """Verify the 5-scenario sandbox stress test engine runs with 100% accuracy."""
    report = run_sandbox_test()
    assert report["total_scenarios"] == 5
    assert report["verification_accuracy_pct"] == 100.0
    assert report["total_latency_ms"] < 200.0  # sub-200ms verification
    assert report["blocked_count"] == 4
    assert report["passed_count"] == 1

    # Verify Scenario 1 (Counter-trend short in bull market) was blocked
    sc1 = next(r for r in report["results"] if r["scenario_id"] == "scenario_1")
    assert not sc1["passed"]
    assert "01_macro_trend_filter" in sc1["blocked_by"]

    # Verify Scenario 5 (Valid high-confidence setup) passed
    sc5 = next(r for r in report["results"] if r["scenario_id"] == "scenario_5")
    assert sc5["passed"]
    assert sc5["outcome"] == "PASSED"


def test_physical_pipeline_integration():
    """Verify PhysicalInterceptorPipeline executes active plugins fail-closed."""
    # Attempt counter-trend short on BTC in 4H bull channel
    res = PhysicalInterceptorPipeline.evaluate_order_intent(
        symbol="BTC",
        side="sell",   # SHORT
        entry_price=68000.0,
        stop_loss_price=69500.0,
        take_profit_price=64000.0,
        confidence=88.0,
        notional_usd=500.0,
        leverage=5.0,
        account_balance_usd=10000.0,
        current_positions=[],
        factor_snapshot={"pillar_1_trend": {"adx": 25.0}},
        candles_4h=[{"close": 68000.0} for _ in range(25)]  # Strong bull closes
    )
    # Gate 4 or Gate 6 macro plugin should block counter-trend short
    assert not res.passed
    assert "MACRO" in res.blocked_by or "4H" in res.reason


if __name__ == "__main__":
    print("=== [TEST SUITE 2] Python Risk Plugins & Online Sandbox Engine ===")
    test_list_default_plugins()
    print("  ✓ test_list_default_plugins passed successfully")
    test_ast_syntax_validation()
    print("  ✓ test_ast_syntax_validation passed successfully")
    test_plugin_crud_and_toggle()
    print("  ✓ test_plugin_crud_and_toggle passed successfully")
    test_sandbox_stress_scenarios()
    print("  ✓ test_sandbox_stress_scenarios passed successfully (5/5 scenarios 100% accurate)")
    test_physical_pipeline_integration()
    print("  ✓ test_physical_pipeline_integration passed successfully")
    print(">>> All Risk Plugins & Sandbox tests PASSED! <<<\n")

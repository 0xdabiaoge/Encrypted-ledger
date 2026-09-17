"""
Test Suite: Prompt Studio Dynamic Token Badges & Placeholder Rendering
Verifies:
1. Available token slot badges list and metadata definitions
2. Dynamic placeholder substitution for live calculus, macro, smart money, and telemetry
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

from app.intelligence.prompt_renderer import (
    get_available_prompt_tokens,
    render_prompt_template,
)


def test_available_prompt_tokens():
    """Verify all 9 dynamic token slot badges are declared."""
    tokens = get_available_prompt_tokens()
    assert len(tokens) >= 9
    token_keys = [t["token"] for t in tokens]
    assert "{{macro_4h}}" in token_keys
    assert "{{calculus_1h}}" in token_keys
    assert "{{smart_money}}" in token_keys
    assert "{{orderbook_imbalance}}" in token_keys
    assert "{{sentiment_index}}" in token_keys
    assert "{{hft_micro_scalp}}" in token_keys
    assert "{{risk_limit}}" in token_keys
    assert "{{timestamp_beijing}}" in token_keys
    assert "{{closed_trades_summary}}" in token_keys


def test_render_prompt_template():
    """Verify template placeholders are replaced with real numbers."""
    raw_prompt = """
Target: BTC
Macro State: {{macro_4h}}
Calculus Momentum: {{calculus_1h}}
Orderbook Imbalance: {{orderbook_imbalance}}
Smart Money: {{smart_money}}
Execution Guard: {{hft_micro_scalp}}
Risk Constraints: {{risk_limit}}
Current Time: {{timestamp_beijing}}
Performance: {{closed_trades_summary}}
"""
    factors = {
        "pillar_1_trend": {
            "price_velocity_bps_min": 14.5,
            "price_accel_bps_min2": 3.2,
            "adx": 28.5
        },
        "long_short_ratio": 1.45,
        "orderbook_imbalance": 0.285
    }
    ctx = {
        "macro_4h": "4H_BULL_EXPANSION",
        "closed_summary": "胜率 75% | 累计 10 笔"
    }

    rendered = render_prompt_template(raw_prompt, symbol="BTC", factor_snapshot=factors, context=ctx)

    # Ensure no unresolved placeholders remain
    assert "{{" not in rendered
    assert "}}" not in rendered

    # Ensure injected values exist
    assert "4H_BULL_EXPANSION" in rendered
    assert "v=+14.50 bps/min" in rendered
    assert "a=+3.20 bps/min²" in rendered
    assert "+0.2850" in rendered
    assert "多空人数比 1.45" in rendered
    assert "CST" in rendered
    assert "胜率 75%" in rendered


if __name__ == "__main__":
    print("=== [TEST SUITE 3] Prompt Studio Dynamic Token Badges & Calculus Rendering ===")
    test_available_prompt_tokens()
    print("  ✓ test_available_prompt_tokens passed successfully (9 dynamic badges declared)")
    test_render_prompt_template()
    print("  ✓ test_render_prompt_template passed successfully (calculus/macro dynamically rendered)")
    print(">>> All Prompt Studio Token Renderer tests PASSED! <<<\n")

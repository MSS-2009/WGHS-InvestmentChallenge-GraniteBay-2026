"""Tests for reinvestment risk simulation of the reserve ladder (r8-reinvest)."""
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from reinvest_risk import (
    build_headline_ladder,
    check_schedule_against_lp,
    compute_extra_cash_lock,
    roll_forward,
)


def test_toy_two_payment_schedule_hand_arithmetic():
    """Two-payment toy schedule verified against hand arithmetic to the cent.

    Schedule:
      - Month 0: Inflow +$10,000.00
      - Month 1: Payment 1 -$15,000.00; Inflow +$10,000.00
      - Month 2: Payment 2 -$15,000.00

    Hand Arithmetic at 0%:
      - Month 0: Inflow $10,000.00, earns 0% -> cash entering Month 1 = $10,000.00
      - Month 1: Payment 1 due $15,000.00
                 Shortfall 1 = $15,000.00 - $10,000.00 = $5,000.00
                 Remaining cash = $0.00
                 Inflow +$10,000.00 arrives during Month 1
                 Cash earns 0% -> cash entering Month 2 = $10,000.00
      - Month 2: Payment 2 due $15,000.00
                 Shortfall 2 = $15,000.00 - $10,000.00 = $5,000.00
                 Remaining cash = $0.00
      - Total Shortfall at 0% = $5,000.00 + $5,000.00 = $10,000.00

    Hand Arithmetic at 3% (simple monthly rate r/12 = 0.03 / 12 = 0.0025 = 0.25%):
      - Month 0: Inflow $10,000.00
                 Interest = $10,000.00 * 0.0025 = $25.00
                 Cash entering Month 1 = $10,000.00 + $25.00 = $10,025.00
      - Month 1: Payment 1 due $15,000.00
                 Shortfall 1 = $15,000.00 - $10,025.00 = $4,975.00
                 Remaining cash = $0.00
                 Inflow +$10,000.00 arrives during Month 1
                 Interest = $10,000.00 * 0.0025 = $25.00
                 Cash entering Month 2 = $10,000.00 + $25.00 = $10,025.00
      - Month 2: Payment 2 due $15,000.00
                 Shortfall 2 = $15,000.00 - $10,025.00 = $4,975.00
                 Remaining cash = $0.00
      - Total Shortfall at 3% = $4,975.00 + $4,975.00 = $9,950.00
    """
    flow_by_m = {0: 10_000.0, 1: 10_000.0}
    pay_by_m = {1: 15_000.0, 2: 15_000.0}

    # 1. Verify 0% roll-forward matches hand arithmetic to the cent
    res_0 = roll_forward(flow_by_m, pay_by_m, rates=0.00, start_m=0, end_m=2)
    assert np.allclose(res_0["shortfalls"], [5000.0, 5000.0], atol=1e-2)
    assert np.isclose(res_0["total_shortfall"], 10000.0, atol=1e-2)

    # 2. Verify 3% roll-forward matches hand arithmetic to the cent
    res_3 = roll_forward(flow_by_m, pay_by_m, rates=0.03, start_m=0, end_m=2)
    assert np.allclose(res_3["shortfalls"], [4975.0, 4975.0], atol=1e-2)
    assert np.isclose(res_3["total_shortfall"], 9950.0, atol=1e-2)

    # 3. Verify extra cash needed at lock
    # At 0%: need $10,000.00 extra cash
    extra_0 = compute_extra_cash_lock(flow_by_m, pay_by_m, rates=0.00, start_m=0, end_m=2)
    assert np.isclose(extra_0, 10000.0, atol=1e-2)
    res_0_funded = roll_forward(flow_by_m, pay_by_m, rates=0.00, start_m=0, end_m=2, extra_cash=extra_0)
    assert np.isclose(res_0_funded["total_shortfall"], 0.0, atol=1e-6)

    # At 3%: need 4975/1.0025 + 4975/(1.0025^2) = 4962.5935 + 4950.2180 = 9912.81
    extra_3 = compute_extra_cash_lock(flow_by_m, pay_by_m, rates=0.03, start_m=0, end_m=2)
    assert np.isclose(extra_3, 9912.81, atol=1e-2)
    res_3_funded = roll_forward(flow_by_m, pay_by_m, rates=0.03, start_m=0, end_m=2, extra_cash=extra_3)
    assert np.isclose(res_3_funded["total_shortfall"], 0.0, atol=1e-6)


def test_toy_funded_at_3pct_short_at_0pct():
    """Toy schedule that funds fully at 3% (zero shortfall) but misses at 0%.

    Schedule:
      - Month 0: Inflow $10,000.00
      - Month 1: Payment 1 $10,020.00, Inflow $10,000.00
      - Month 2: Payment 2 $10,000.00

    Hand Arithmetic at 3% (r/12 = 0.0025):
      - Month 0: $10,000.00 * 1.0025 = $10,025.00
      - Month 1: $10,025.00 >= $10,020.00 -> Shortfall = $0.00, Surplus = $5.00
                 +$10,000.00 inflow -> $10,005.00 * 1.0025 = $10,030.0125
      - Month 2: $10,030.0125 >= $10,000.00 -> Shortfall = $0.00
      Total Shortfall at 3% = $0.00

    Hand Arithmetic at 0%:
      - Month 0: $10,000.00
      - Month 1: Payment $10,020.00 -> Shortfall = $20.00, Remaining = $0.00
                 +$10,000.00 inflow
      - Month 2: Payment $10,000.00 -> Shortfall = $0.00
      Total Shortfall at 0% = $20.00
    """
    flow_by_m = {0: 10_000.0, 1: 10_000.0}
    pay_by_m = {1: 10_020.0, 2: 10_000.0}

    res_3 = roll_forward(flow_by_m, pay_by_m, rates=0.03, start_m=0, end_m=2)
    assert np.isclose(res_3["total_shortfall"], 0.0, atol=1e-6)
    assert np.allclose(res_3["shortfalls"], [0.0, 0.0], atol=1e-6)

    res_0 = roll_forward(flow_by_m, pay_by_m, rates=0.00, start_m=0, end_m=2)
    assert np.isclose(res_0["total_shortfall"], 20.0, atol=1e-2)
    assert np.allclose(res_0["shortfalls"], [20.0, 0.0], atol=1e-2)


def test_headline_ladder_schedule_checks():
    """Verify schedule checks on the headline curve pass: 3% surplus ~ 0, 0% shortfall in range."""
    lad = build_headline_ladder()
    checks = check_schedule_against_lp(lad["curve"], lad["active"], lad["lp_3"], lad["lp_0"], lad["pays"])

    # Check 1: 3% final surplus is zero to machine precision
    assert abs(checks["final_surplus_3"]) < 1e-4

    # Check 2: 0% final shortfall is in expected range (~$8,256.53)
    assert 8000.0 < checks["shortfall_0"] < 8500.0
    assert np.isclose(checks["shortfall_0"], 8256.53, atol=1e-2)

    # Monthly roll forward with headline ladder flows at 3% produces zero shortfall on every payment
    res_real_3 = roll_forward(lad["flow_by_m"], lad["pay_by_m"], rates=0.03, start_m=2, end_m=182)
    assert np.isclose(res_real_3["total_shortfall"], 0.0, atol=1e-6)
    assert np.all(res_real_3["shortfalls"] == 0.0)

    # Monthly roll forward with headline ladder flows at 0% produces exactly $8,256.53 shortfall
    res_real_0 = roll_forward(lad["flow_by_m"], lad["pay_by_m"], rates=0.00, start_m=2, end_m=182)
    assert np.isclose(res_real_0["total_shortfall"], 8256.53, atol=1e-2)

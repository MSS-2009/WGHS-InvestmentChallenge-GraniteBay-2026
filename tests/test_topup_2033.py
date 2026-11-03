import datetime as dt
import sys
from pathlib import Path

import numpy as np

# Ensure scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lgm.curve import ZeroCurve
from lgm.instruments import TreasuryStrip
from topup_2033 import solve_topup_lp


def test_topup_2033_toy_case_0pct():
    """Toy case at 0% yield: 2 payments, 2 instruments.

    Payment 0: 2033-01-01, $1,000.00
    Payment 1: 2034-01-01, $1,000.00
    Cash on hand: $700.00
    Held portfolio: $0.00 at T_0, $600.00 at T_1

    Instruments:
      Strip A (maturing 2034-01-01): price = 1.0, pays 1.0 at T_1
      Strip B (maturing 2035-01-01): price = 1.0, pays 1.0 at T_2 (after T_1)

    Hand calculation:
      T_0: shortfall = 1000 - 700 = $300.00 (cash injected = $300.00)
      T_1: deficit = 1000 - 600 = $400.00 (delivered by Strip A at cost $400.00)
      Total cost = 300.00 + 400.00 = $700.00
    """
    settle = dt.date(2033, 1, 1)
    curve_0 = ZeroCurve(settle, np.array([1.0, 5.0]), np.array([0.0, 0.0]))

    payments = [
        (dt.date(2033, 1, 1), 1000.0),
        (dt.date(2034, 1, 1), 1000.0),
    ]
    held_cash = np.array([0.0, 600.0])
    cash_on_hand = 700.0

    inst_A = TreasuryStrip("STRIP_2034", dt.date(2034, 1, 1))
    inst_B = TreasuryStrip("STRIP_2035", dt.date(2035, 1, 1))
    instruments = [inst_A, inst_B]

    res = solve_topup_lp(curve_0, cash_on_hand, instruments, payments, held_cash)

    expected_cost = 700.00
    assert abs(res["cost"] - expected_cost) < 0.005, f"Expected {expected_cost}, got {res['cost']}"
    assert abs(res["x_cash"] - 300.00) < 0.005


def test_topup_2033_toy_case_positive_yield():
    """Toy case with positive yield: Strip A is strictly cheaper than rolling cash.

    Continuous yield = 5% flat:
      df(1.0) = exp(-0.05 * 1.0) = 0.9512294245...
      Strip A price per dollar = df(1.0) = 0.9512294245...
      Strip B delivers at T_2 (provides 0 to T_1)

    Hand calculation:
      T_0: shortfall = 1000 - 700 = $300.00 (cash injected = $300.00)
      T_1: deficit = 1000 - 600 = $400.00
           delivering $400.00 with Strip A costs 400.0 * exp(-0.05) = $380.4917698...
      Total top-up cost = 300.00 + 380.4917698... = $680.4917698...
    """
    settle = dt.date(2033, 1, 1)
    knots = np.array([1.0, 2.0, 5.0])
    log_df = -0.05 * knots
    curve = ZeroCurve(settle, knots, log_df)

    payments = [
        (dt.date(2033, 1, 1), 1000.0),
        (dt.date(2034, 1, 1), 1000.0),
    ]
    held_cash = np.array([0.0, 600.0])
    cash_on_hand = 700.0

    inst_A = TreasuryStrip("STRIP_2034", dt.date(2034, 1, 1))
    inst_B = TreasuryStrip("STRIP_2035", dt.date(2035, 1, 1))
    instruments = [inst_A, inst_B]

    res = solve_topup_lp(curve, cash_on_hand, instruments, payments, held_cash)

    # Hand calculation to the cent:
    expected_strip_cost = 400.0 * np.exp(-0.05) # 380.4917698
    expected_total_cost = 300.0 + expected_strip_cost # 680.4917698
    expected_cents = round(expected_total_cost, 2) # 680.49

    assert abs(res["cost"] - expected_total_cost) < 0.005, f"Expected {expected_total_cost:.4f}, got {res['cost']:.4f}"
    assert round(res["cost"], 2) == expected_cents
    assert abs(res["x_cash"] - 300.00) < 0.005
    assert abs(res["holdings_bought"]["STRIP_2034"] - expected_strip_cost) < 0.005

"""Tests for policy robustness analysis and reports/policy_robust.csv."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from lgm.strategies import IPS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_CSV = REPORTS_DIR / "policy_robust.csv"

SHIFTS = [
    "base",
    "eq_cma_p25",
    "eq_cma_lowest",
    "eq_cma_highest",
    "eq_vol_0.8",
    "eq_vol_1.2",
    "tails_tdof3",
    "tails_gaussian",
    "rates_minus_75bp",
    "rates_plus_75bp",
    "bond_er_doubled",
]

POLICIES = ["IPS", "P2361", "P2485", "P2305", "P2333", "P1729", "P0964"]

OBJECTIVES = [
    "median",
    "p5",
    "cvar5",
    "ce_gamma2",
    "ce_gamma4",
    "ce_gamma8",
    "secured_2031_median",
]


def test_policy_robust_csv_exists_and_complete():
    assert OUTPUT_CSV.exists(), f"Missing {OUTPUT_CSV}"
    df = pd.read_csv(OUTPUT_CSV)

    assert len(df) == len(SHIFTS) * len(POLICIES)  # 77 rows
    assert set(df["shift"].unique()) == set(SHIFTS)
    assert set(df["name"].unique()) == set(POLICIES)

    # All expected columns present
    expected_cols = [
        "shift",
        "policy_id",
        "name",
        "lock_2027",
        "equity_share",
        "equity_share_end",
        "floor_share",
        "floor_year",
        "ratchet_trigger",
        "ratchet_share",
        "funded",
        "median",
        "p5",
        "cvar5",
        "ce_gamma2",
        "ce_gamma4",
        "ce_gamma8",
        "secured_2031_median",
    ] + [f"regret_{obj}" for obj in OBJECTIVES]

    for col in expected_cols:
        assert col in df.columns, f"Missing column {col}"


def test_regrets_non_negative_and_zero_for_winner():
    df = pd.read_csv(OUTPUT_CSV)

    for shift in SHIFTS:
        sub = df[df["shift"] == shift]
        for obj in OBJECTIVES:
            regret_col = f"regret_{obj}"
            regrets = sub[regret_col].values
            # All regrets >= 0
            assert np.all(regrets >= -1e-6), f"Negative regret in {shift} {obj}"
            # At least one winner has regret == 0
            assert np.any(np.isclose(regrets, 0.0, atol=1e-4)), f"No zero regret winner in {shift} {obj}"

"""Tests for Taiwan short-term interest rates data loader."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lgm.data import twrates


def test_money_market_rates_offline_and_structure():
    """Verify offline loading, structure, date range, and column parsing."""
    df = twrates.money_market_rates(refresh=False, decimal=True)
    assert not df.empty
    assert len(df) >= 472
    assert df.index[0] == pd.Timestamp("1987-05-31")
    assert df.index[-1] >= pd.Timestamp("2026-08-31")

    # Check key columns
    assert "Commercial paper-Secondary market-31-90 days" in df.columns
    assert "Interbank call loans" in df.columns


def test_cp_90d_cross_checks():
    """Cross-check Taiwan 90-day CP rates against CBC official benchmarks."""
    cp_dec = twrates.cp_90d(refresh=False, decimal=True)
    cp_pct = twrates.cp_90d(refresh=False, decimal=False)

    # 1. August 2026: 1.78%
    assert abs(cp_pct.loc["2026-08-31"] - 1.78) < 1e-4
    assert abs(cp_dec.loc["2026-08-31"] - 0.0178) < 1e-6

    # 2. December 2024: 1.75%
    assert abs(cp_pct.loc["2024-12-31"] - 1.75) < 1e-4
    assert abs(cp_dec.loc["2024-12-31"] - 0.0175) < 1e-6

    # 3. January 2016: 0.40%
    assert abs(cp_pct.loc["2016-01-31"] - 0.40) < 1e-4
    assert abs(cp_dec.loc["2016-01-31"] - 0.0040) < 1e-6


def test_interbank_call_cross_checks():
    """Cross-check Taiwan overnight call loan rates against CBC official benchmarks."""
    call_dec = twrates.interbank_call(refresh=False, decimal=True)
    call_pct = twrates.interbank_call(refresh=False, decimal=False)

    # 1. August 2026: 0.822%
    assert abs(call_pct.loc["2026-08-31"] - 0.822) < 1e-4
    assert abs(call_dec.loc["2026-08-31"] - 0.00822) < 1e-6

    # 2. December 2024: 0.820%
    assert abs(call_pct.loc["2024-12-31"] - 0.820) < 1e-4
    assert abs(call_dec.loc["2024-12-31"] - 0.00820) < 1e-6

    # 3. January 2016: 0.233%
    assert abs(call_pct.loc["2016-01-31"] - 0.233) < 1e-4
    assert abs(call_dec.loc["2016-01-31"] - 0.00233) < 1e-6

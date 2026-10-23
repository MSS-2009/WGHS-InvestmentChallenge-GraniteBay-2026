"""Keyless data sources added in October 2026 (read from the cached raw files)."""
import numpy as np
import pandas as pd

from lgm.data import fed, french, treasury
from lgm.growth.core import _view_stats


def test_kim_wright_columns_and_units():
    kw = fed.kim_wright()
    assert {"FF1", "FFTP1", "FF10", "FY10", "FYTP10"} <= set(kw.columns)
    last = kw.dropna().iloc[-1]
    assert 0.0 < last["FY10"] < 0.15 and abs(last["FYTP10"]) < 0.05      # decimals, not percent
    assert kw.index.max() >= pd.Timestamp("2026-10-01")


def test_h10_usd_twd_is_plausible():
    s = fed.usd_twd()
    assert s.index.min() == pd.Timestamp("2000-01-03")
    assert s.between(25, 40).all()


def test_breakeven_is_nominal_minus_real():
    be = treasury.breakevens(start=2026, end=2026)
    d = pd.Timestamp("2026-10-20")
    nominal, real = treasury.load_year(2026), treasury.real_year(2026)
    nominal.index = pd.to_datetime(nominal.index)
    assert np.isclose(be.loc[d, 5.0], (nominal.loc[d, 5.0] - real.loc[d, 5.0]) / 100)
    assert 0.01 < be.loc[d, 10.0] < 0.04


def test_history_sources_do_not_shrink_a_single_forecasters_uncertainty():
    cfg = {"single_source_std": 0.025, "view_std_floor": 0.015}
    q, s = _view_stats([0.035, 0.0224], cfg, forecasters=1)
    assert np.isclose(q, (0.035 + 0.0224) / 2) and s == 0.025
    q, s = _view_stats([0.002, 0.017, 0.010], cfg, forecasters=2)
    assert np.isclose(q, 0.010) and s == 0.015


def test_french_library_parses_the_first_monthly_table():
    p6 = french.monthly("6_Portfolios_2x3")
    assert "BIG HiBM" in p6.columns and p6.index.min() == pd.Timestamp("1926-07-31")
    assert p6.abs().max().max() < 1.0                                    # decimals

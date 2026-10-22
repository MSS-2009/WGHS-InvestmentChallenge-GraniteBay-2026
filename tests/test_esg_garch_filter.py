"""Tests for GARCH variance filtering (Task 1 of r2-esg)."""
import numpy as np
import pytest

from lgm.asof import DATA_END
from lgm.calibrate import calibrate_equity_garch, filter_equity_garch
from lgm.data import yahoo
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params


def test_filter_recovers_simulated_garch_h():
    """Filtering the generator's own simulated returns exactly recovers its simulated garch_h path."""
    core = build_core()
    gcal = calibrate_equity_garch()
    alpha, beta = gcal["alpha"], gcal["beta"]

    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = (alpha, beta, 1.0)
    sc = simulate(p, n=20, seed=11)

    assert sc.garch_h is not None

    # Filter each scenario's asset-0 returns
    mu0 = np.log1p(p.eq_geo[0]) / 12.0
    var0 = p.cov[0, 0] * (p.eq_vol_scale ** 2)

    # 1D test per scenario
    for i in range(5):
        r = sc.eq_log[i, :, 0]
        h_rec = filter_equity_garch(r, alpha=alpha, beta=beta, mu=mu0, var_uncond=var0, h0=1.0)
        assert np.allclose(sc.garch_h[i], h_rec, atol=1e-12)

    # 2D vectorized test across all scenarios
    all_r = sc.eq_log[:, :, 0]
    all_h = filter_equity_garch(all_r, alpha=alpha, beta=beta, mu=mu0, var_uncond=var0, h0=1.0)
    assert np.allclose(sc.garch_h, all_h, atol=1e-12)


def test_filter_matches_today_state_september_2026():
    """Filtering historical VTI returns up to September 2026 matches the ~0.70 reported in r1."""
    gcal = calibrate_equity_garch()
    ret = yahoo.monthly_returns(["VTI"], start="2001-01-01")["VTI"].loc[:DATA_END].dropna()
    r = np.log1p(ret)

    h_path = filter_equity_garch(r, alpha=gcal["alpha"], beta=gcal["beta"])
    today_h = h_path[-1]

    # Must match calibrate_equity_garch's reported h0_today exactly
    assert np.isclose(today_h, gcal["h0_today"], atol=1e-10)
    # Must match ~0.70 (0.705)
    assert round(today_h, 2) == 0.70

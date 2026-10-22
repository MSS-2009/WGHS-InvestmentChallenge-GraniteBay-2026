import numpy as np
import pytest

from lgm.growth import black_litterman as bl


def test_no_views_returns_equilibrium_and_market_weights():
    cov = np.array([[0.04, 0.012], [0.012, 0.09]])
    w = np.array([0.7, 0.3])
    delta = 2.5
    pi = bl.implied_returns(cov, w, delta)
    # a view with huge uncertainty leaves the prior unchanged
    mu, _ = bl.posterior(cov, pi, np.array([[1.0, -1.0]]), np.array([0.05]), np.array([[1e6]]), 0.05)
    assert np.allclose(mu, pi, atol=1e-6)
    w_opt = bl.optimise(pi, cov, delta, np.zeros(2), np.ones(2))
    assert np.allclose(w_opt, w, atol=1e-4)


def test_confident_view_moves_posterior_toward_view():
    cov = np.array([[0.04, 0.012], [0.012, 0.09]])
    w = np.array([0.5, 0.5])
    pi = bl.implied_returns(cov, w, 2.5)
    P, Q = np.array([[1.0, -1.0]]), np.array([0.04])
    mu, _ = bl.posterior(cov, pi, P, Q, np.array([[1e-8]]), 0.05)
    assert abs((mu[0] - mu[1]) - 0.04) < 1e-4


def test_resampled_optimum_is_feasible_and_near_market_without_views():
    cov = np.array([[0.04, 0.03, 0.01], [0.03, 0.04, 0.01], [0.01, 0.01, 0.09]])
    w = np.array([0.4, 0.4, 0.2])
    pi = bl.implied_returns(cov, w, 2.5)
    lb, ub = 0.5 * w, 2 * w
    a = np.array([1.0, 0.0, 0.0])
    mean, sd = bl.resampled_optimise(pi, 0.05 * cov * 0.01, cov, 2.5, lb, ub, [(a, 0.4)], n=200, w0=w)
    assert abs(mean.sum() - 1) < 1e-9
    assert (mean >= lb - 1e-9).all() and (mean <= ub + 1e-9).all() and mean @ a <= 0.4 + 1e-9
    assert np.allclose(mean, w, atol=0.03)


def test_risk_aversion_makes_the_market_earn_its_excess_and_anchoring_keeps_it():
    from lgm.growth import black_litterman as bl

    rng = np.random.default_rng(4)
    a = rng.standard_normal((6, 6))
    cov = a @ a.T / 600 + np.eye(6) * 1e-3
    w = rng.dirichlet(np.ones(6))
    delta = bl.risk_aversion(cov, w, 0.05)
    pi = bl.implied_returns(cov, w, delta)
    assert w @ pi == pytest.approx(0.05)
    mu = pi + rng.normal(0, 0.01, 6)                  # a posterior that moved the market's return
    anchored = bl.anchor_to_prior(mu, pi, w)
    assert w @ anchored == pytest.approx(w @ pi)
    assert np.allclose(np.diff(anchored), np.diff(mu))   # relative returns, hence fully invested weights, unchanged


def test_ar1_recovers_persistence():
    import pandas as pd

    from lgm.calibrate import ar1

    rng = np.random.default_rng(5)
    x = np.zeros(20_000)
    for t in range(1, len(x)):
        x[t] = 0.3 + 0.9 * x[t - 1] + rng.standard_normal()
    phi, resid = ar1(pd.Series(x))
    assert phi == pytest.approx(0.9, abs=0.01)
    assert resid.std() == pytest.approx(1.0, abs=0.02) and len(resid) == len(x) - 1

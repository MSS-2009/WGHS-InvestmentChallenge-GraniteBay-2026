import numpy as np

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

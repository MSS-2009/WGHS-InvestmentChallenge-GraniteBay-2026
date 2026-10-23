"""Black-Litterman (He & Litterman, 1999) and a constrained mean-variance optimiser.

Notation (annual, arithmetic, excess of cash):
  Sigma  covariance of asset returns             w_mkt  market-cap weights
  delta  risk aversion = market excess / market variance
  Pi     = delta * Sigma @ w_mkt                 (equilibrium returns the market implies)
  P, Q   view portfolios and their expected excess returns; Omega their uncertainty
  tau    scales uncertainty in Pi (prior is N(Pi, tau*Sigma))
Posterior mean  mu = [(tau S)^-1 + P' O^-1 P]^-1 [(tau S)^-1 Pi + P' O^-1 Q]
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize


def implied_returns(cov: np.ndarray, w_mkt: np.ndarray, delta: float) -> np.ndarray:
    return delta * cov @ w_mkt


def risk_aversion(cov: np.ndarray, w_mkt: np.ndarray, market_excess: float) -> float:
    return market_excess / float(w_mkt @ cov @ w_mkt)


def anchor_to_prior(mu: np.ndarray, pi: np.ndarray, w_mkt: np.ndarray) -> np.ndarray:
    """Shift a posterior so the market portfolio earns what the prior gives it. With relative views only,
    the market's posterior return still moves with the views' covariance with the market (here by +0.11
    to +0.39 points depending on small risk changes); the level belongs to the consensus that sets delta.
    A uniform shift leaves fully invested optimal weights unchanged."""
    return mu + float(w_mkt @ pi - w_mkt @ mu)


def posterior(cov, pi, P, Q, omega, tau):
    ts_inv = np.linalg.inv(tau * cov)
    o_inv = np.linalg.inv(omega)
    A = np.linalg.inv(ts_inv + P.T @ o_inv @ P)
    mu = A @ (ts_inv @ pi + P.T @ o_inv @ Q)
    return mu, cov + A


def optimise(mu, cov, delta, lb, ub, ineq: list[tuple[np.ndarray, float]] | None = None, w0=None):
    """max w'mu - delta/2 w'Sigma w  s.t. sum w = 1, lb <= w <= ub, a'w <= b for each (a, b)."""
    n = len(mu)
    w0 = np.clip(np.full(n, 1 / n) if w0 is None else w0, lb, ub)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}]
    for a, b in (ineq or []):
        cons.append({"type": "ineq", "fun": (lambda w, a=a, b=b: b - a @ w), "jac": (lambda w, a=a: -a)})
    f = lambda w: -(w @ mu - 0.5 * delta * w @ cov @ w)
    g = lambda w: -(mu - delta * cov @ w)
    res = minimize(f, w0, jac=g, bounds=list(zip(lb, ub)), constraints=cons, method="SLSQP",
                   options={"maxiter": 500, "ftol": 1e-12})
    if not res.success:
        raise RuntimeError(res.message)
    return res.x


def resampled_optimise(mu, mu_cov, cov, delta, lb, ub, ineq=None, n: int = 500, seed: int = 0, w0=None):
    """Average of constrained optima over draws of expected returns from N(mu, mu_cov), the
    Black-Litterman posterior (Michaud 1998 resampling). A single optimum sits on its limits and
    swaps weight between near-identical funds when an input moves slightly; the average does not,
    and it remains feasible because the constraints are linear. Returns (mean, std) of the weights."""
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(mu_cov + 1e-12 * np.eye(len(mu)))
    ws = np.array([optimise(mu + L @ rng.standard_normal(len(mu)), cov, delta, lb, ub, ineq, w0=w0) for _ in range(n)])
    return ws.mean(0), ws.std(0)


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

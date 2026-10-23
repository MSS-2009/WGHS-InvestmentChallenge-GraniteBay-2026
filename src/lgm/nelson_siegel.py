"""Nelson-Siegel yield-curve factors (Diebold & Li, 2006).

z(tau) = b1 + b2 * L2(tau) + b3 * L3(tau)
  L2 = (1 - e^{-lam tau}) / (lam tau)          slope loading
  L3 = L2 - e^{-lam tau}                       curvature loading
b1 is the long-run level, -b2 the slope (long minus short), b3 the hump.
lam = 0.7308 per year (Diebold-Li's 0.0609 per month) puts peak curvature at ~2.5 years.
Rates here are continuously compounded zero rates in decimals.
"""
from __future__ import annotations

import numpy as np

LAMBDA = 0.0609 * 12


def loadings(tau: np.ndarray, lam: float = LAMBDA) -> np.ndarray:
    tau = np.maximum(np.asarray(tau, dtype=float), 1e-6)
    x = lam * tau
    l2 = (1 - np.exp(-x)) / x
    l3 = l2 - np.exp(-x)
    return np.stack([np.ones_like(tau), l2, l3], axis=-1)


def fit(tau: np.ndarray, z: np.ndarray, lam: float = LAMBDA) -> np.ndarray:
    X = loadings(tau, lam)
    beta, *_ = np.linalg.lstsq(X, z, rcond=None)
    return beta


def zero(beta: np.ndarray, tau: np.ndarray, lam: float = LAMBDA) -> np.ndarray:
    """beta (..., 3) and tau (k,) -> zero rates (..., k)."""
    return np.einsum("...f,kf->...k", beta, loadings(tau, lam))

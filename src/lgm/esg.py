"""Economic scenario generator (monthly).

State per scenario and month:
- Nelson-Siegel factors (level, slope, curvature) of the continuously compounded zero curve,
  AR(1) toward long-run means. A fixed residual keeps today's curve exact at month 0.
- Equity log returns for US, developed ex-US and emerging markets.
- US CPI inflation (year over year), AR(1) toward its long-run mean.
- log USD/TWD (positive = the dollar buys more Taiwan dollars) and a Taiwan building-cost index.
Shocks are jointly Student-t (one common mixing variable per month), so bad months hit
stocks, rates and FX together, as in 2008 and 2020.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import nelson_siegel as ns
from .curve import ZeroCurve

TAU_GRID = np.array([0.0833, 0.25, 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30], dtype=float)


@dataclass
class ESGParams:
    months: int
    beta0: np.ndarray                # starting NS factors
    resid: np.ndarray                # today's curve minus NS fit on TAU_GRID (cc, decimals)
    beta_mu: np.ndarray              # long-run NS factors
    phi: np.ndarray                  # monthly AR(1) per factor
    cov: np.ndarray                  # (K+5, K+5) monthly joint shock covariance: K equities, 3 rate
                                     # factors, inflation, USD/TWD (in that order)
    eq_geo: np.ndarray               # (K,) annual median (geometric) equity returns, gross of fees
    eq_vol_scale: float = 1.0
    infl0: float = 0.0374
    infl_mu: float = 0.03
    infl_phi: float = 0.966
    fx_drift: float = 0.0            # annual log drift of USD/TWD
    tw_cost_growth: float = 0.04     # Taiwan building-cost inflation, annual
    tw_cost_vol: float = 0.015
    t_dof: float | None = 5.0        # Student-t degrees of freedom; None = Gaussian
    rate_floor: float = -0.005
    eq_mu_cov: np.ndarray | None = None  # (K, K) annual covariance of expected equity returns
    eq_garch: tuple[float, float] | dict | None = None  # optional (alpha, beta) or dict for GARCH(1,1) vol clustering
    tw_cost_phi: float | None = None  # monthly AR(1) persistence; None = legacy i.i.d.
    tw_cost_infl0: float | None = None  # initial inflation rate (annual); None = tw_cost_growth
    tw_cost_corr: float | None = None  # correlation of tw_cost innovations with US CPI shock


@dataclass
class Scenarios:
    beta: np.ndarray       # (N, M+1, 3)
    eq_log: np.ndarray     # (N, M, K)
    infl: np.ndarray       # (N, M+1)
    fx_log: np.ndarray     # (N, M+1), 0 at start
    tw_cost_log: np.ndarray  # (N, M+1), 0 at start
    resid: np.ndarray
    rate_floor: float = -0.005
    m0: int = 0            # absolute month of index 0 (non-zero for nested simulations)
    eq_drift_err: np.ndarray | None = None
    garch_h: np.ndarray | None = None
    tw_cost_infl: np.ndarray | None = None

    @property
    def n(self) -> int:
        return self.beta.shape[0]

    def zero_cc(self, m: int, tau) -> np.ndarray:
        """(N, k) continuously compounded zero rates at month m."""
        tau = np.atleast_1d(np.asarray(tau, dtype=float))
        z = ns.zero(self.beta[:, m - self.m0, :], tau) + np.interp(tau, TAU_GRID, self.resid)[None, :]
        return np.maximum(z, self.rate_floor)

    def df(self, m: int, tau) -> np.ndarray:
        tau = np.atleast_1d(np.asarray(tau, dtype=float))
        return np.exp(-self.zero_cc(m, tau) * np.maximum(tau, 0.0)[None, :])

    def curve(self, i: int, m: int, date) -> ZeroCurve:
        """Scenario i's curve at month m as a ZeroCurve object (for LP pricing)."""
        knots = np.concatenate([[0.0], TAU_GRID])
        z = self.zero_cc(m, TAU_GRID)[i]
        return ZeroCurve(date, knots, np.concatenate([[0.0], -z * TAU_GRID]))


def initial_state(curve: ZeroCurve) -> tuple[np.ndarray, np.ndarray]:
    z = np.log1p(curve.zero(TAU_GRID))
    beta0 = ns.fit(TAU_GRID, z)
    return beta0, z - ns.zero(beta0, TAU_GRID)


def simulate(p: ESGParams, n: int, seed: int = 0, antithetic: bool = True,
             start: dict | None = None, m0: int = 0) -> Scenarios:
    """Simulate n scenarios for p.months months. `start` overrides month-0 state
    (keys: beta, infl, fx_log, tw_cost_log, each (n,...)) for nested simulation."""
    rng = np.random.default_rng(seed)
    M, k = p.months, p.cov.shape[0]
    half = (n + 1) // 2 if antithetic else n
    z = rng.standard_normal((half, M, k))
    if p.t_dof:
        w = np.sqrt((p.t_dof - 2) / rng.chisquare(p.t_dof, size=(half, M, 1)))
        z = z * w
    if antithetic:
        z = np.concatenate([z, -z], axis=0)[:n]
    chol = np.linalg.cholesky(p.cov)
    shocks = z @ chol.T                                       # (n, M, K+5)
    K = len(p.eq_geo)
    shocks[..., :K] *= p.eq_vol_scale

    garch_h = None
    if p.eq_garch is not None:
        if isinstance(p.eq_garch, (tuple, list)):
            alpha, beta = float(p.eq_garch[0]), float(p.eq_garch[1])
            h0 = float(p.eq_garch[2]) if len(p.eq_garch) > 2 else 1.0
            factor_idx = 0
        elif isinstance(p.eq_garch, dict):
            alpha = float(p.eq_garch["alpha"])
            beta = float(p.eq_garch["beta"])
            h0 = float(p.eq_garch.get("h0", 1.0))
            factor_idx = int(p.eq_garch.get("factor_idx", 0))
        else:
            alpha = float(p.eq_garch.alpha)
            beta = float(p.eq_garch.beta)
            h0 = float(getattr(p.eq_garch, "h0", 1.0))
            factor_idx = int(getattr(p.eq_garch, "factor_idx", 0))

        omega = 1.0 - alpha - beta
        garch_h = np.ones((n, M))
        if start is not None and "garch_h" in start:
            start_h = np.asarray(start["garch_h"])
            garch_h[:, 0] = start_h if start_h.ndim > 0 else np.full(n, float(start_h))
        else:
            garch_h[:, 0] = h0

        var0 = p.cov[factor_idx, factor_idx] * (p.eq_vol_scale ** 2)
        for m in range(M):
            shocks[:, m, :K] *= np.sqrt(garch_h[:, m, None])
            if m < M - 1:
                garch_h[:, m + 1] = omega + alpha * (shocks[:, m, factor_idx] ** 2 / var0) + beta * garch_h[:, m]

    eq_mu = np.log1p(p.eq_geo) / 12.0                         # median growth preserved
    eq_drift_err = None
    if start is not None and "eq_drift_err" in start:
        err = np.asarray(start["eq_drift_err"])
        if err.ndim == 1:
            eq_drift_err = np.tile(err, (n, 1))
        else:
            eq_drift_err = err
    elif p.eq_mu_cov is not None:
        vals, vecs = np.linalg.eigh(p.eq_mu_cov)
        vals = np.maximum(vals, 0.0)
        chol_mu = vecs @ np.diag(np.sqrt(vals))
        z_mu = rng.standard_normal((half, K))
        err_half = z_mu @ chol_mu.T
        if antithetic:
            eq_drift_err = np.concatenate([err_half, -err_half], axis=0)[:n]
        else:
            eq_drift_err = err_half[:n]

    if eq_drift_err is not None:
        eq_log = eq_mu[None, None, :] + (eq_drift_err / 12.0)[:, None, :] + shocks[..., :K]
    else:
        eq_log = eq_mu[None, None, :] + shocks[..., :K]

    beta = np.empty((n, M + 1, 3))
    infl = np.empty((n, M + 1))
    beta[:, 0] = p.beta0 if start is None else start["beta"]
    infl[:, 0] = p.infl0 if start is None else start["infl"]
    if start is not None:
        beta_shift = start.get("beta_shift")
        if beta_shift is not None:
            beta[:, 0] = beta[:, 0] + beta_shift
    for m in range(M):
        beta[:, m + 1] = p.beta_mu + p.phi * (beta[:, m] - p.beta_mu) + shocks[:, m, K:K + 3]
        infl[:, m + 1] = p.infl_mu + p.infl_phi * (infl[:, m] - p.infl_mu) + shocks[:, m, K + 3]
    fx0 = 0.0 if start is None else start["fx_log"][:, None]
    fx_log = np.concatenate([np.zeros((n, 1)), np.cumsum(p.fx_drift / 12 + shocks[..., K + 4], axis=1)], axis=1) + fx0
    if p.tw_cost_phi is not None:
        phi = float(p.tw_cost_phi)
        mu = float(p.tw_cost_growth)
        vol = float(p.tw_cost_vol)
        sig_eps = vol * np.sqrt(max(1.0 - phi**2, 0.0))
        tw_cost_infl = np.empty((n, M + 1))
        if start is not None and "tw_cost_infl" in start:
            s_infl = np.asarray(start["tw_cost_infl"])
            tw_cost_infl[:, 0] = s_infl if s_infl.ndim > 0 else np.full(n, float(s_infl))
        elif p.tw_cost_infl0 is not None:
            tw_cost_infl[:, 0] = float(p.tw_cost_infl0)
        else:
            tw_cost_infl[:, 0] = mu

        if antithetic:
            z_half = rng.standard_normal((half, M))
            z_tw = np.concatenate([z_half, -z_half], axis=0)[:n]
        else:
            z_tw = rng.standard_normal((n, M))

        if p.tw_cost_corr is not None and p.tw_cost_corr != 0.0:
            rho = float(p.tw_cost_corr)
            cpi_std = np.sqrt(p.cov[K + 3, K + 3])
            z_cpi = shocks[..., K + 3] / (cpi_std if cpi_std > 0 else 1.0)
            z_tw = rho * z_cpi + np.sqrt(max(1.0 - rho**2, 0.0)) * z_tw

        for m in range(M):
            tw_cost_infl[:, m + 1] = mu + phi * (tw_cost_infl[:, m] - mu) + sig_eps * z_tw[:, m]

        tw = tw_cost_infl[:, 1:] / 12.0
        tw0 = 0.0 if start is None else start["tw_cost_log"][:, None]
        tw_cost_log = np.concatenate([np.zeros((n, 1)), np.cumsum(tw, axis=1)], axis=1) + tw0
    else:
        tw = np.log1p(p.tw_cost_growth) / 12 + p.tw_cost_vol / np.sqrt(12) * rng.standard_normal((n, M))
        tw0 = 0.0 if start is None else start["tw_cost_log"][:, None]
        tw_cost_log = np.concatenate([np.zeros((n, 1)), np.cumsum(tw, axis=1)], axis=1) + tw0
        tw_cost_infl = None
    return Scenarios(beta, eq_log, infl, fx_log, tw_cost_log, p.resid, p.rate_floor, m0, eq_drift_err, garch_h, tw_cost_infl)

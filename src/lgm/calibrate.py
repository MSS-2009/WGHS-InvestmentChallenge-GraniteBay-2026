"""Calibrate the economic scenario generator to history.

Persistence, volatility and cross-correlation come from data; long-run *levels* (expected
returns, the normal yield curve, inflation) come from the assumption profile, because
history's averages (e.g. near-zero rates in 2009-2021) are poor forecasts of 2027-2033.

Windows
- Rate factors: month-end Treasury par curves, Jan 1994 - Sep 2026, bootstrapped to zeros.
- Equities, inflation, USD/TWD and their correlation with rate shocks: Aug 2007 - Sep 2026
  (the common window for VTI, VEA and VWO).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats, optimize, special
from sklearn.covariance import LedoitWolf

from . import nelson_siegel as ns
from .curve import ParCurve, bootstrap
from .asof import DATA_END
from .data import fed, fred, treasury, yahoo

TAU_FIT = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30], dtype=float)
FACTOR_NAMES = ["level", "slope", "curvature"]
SHOCK_NAMES = ["eq_US", "eq_DEV", "eq_EM", "d_level", "d_slope", "d_curv", "d_infl", "fx_TWD"]


@dataclass
class Calibration:
    phi: np.ndarray            # (3,) monthly AR(1) coefficients for NS factors
    infl_phi: float            # monthly AR(1) coefficient for YoY inflation
    cov: np.ndarray            # (8, 8) monthly covariance of joint shocks, SHOCK_NAMES order
    factor_hist: pd.DataFrame  # fitted NS factors by month
    window: tuple[str, str]
    notes: dict


def usd_twd_monthly() -> pd.Series:
    """Month-end USD/TWD from the Federal Reserve's H.10 noon buying rates (official), from 2000."""
    return fed.usd_twd().resample("ME").last().ffill()


def zero_curve_from_row(date, row: pd.Series):
    pts = {float(t): float(v) for t, v in row.dropna().items()}
    if len(pts) < 5:
        return None
    return bootstrap(ParCurve.from_points(date, pts))


def factor_history(start: str = "1994-01-01") -> pd.DataFrame:
    par = treasury.history(1990, 2026)
    month_end = par.resample("ME").last().loc[start:]
    rows = []
    for d, row in month_end.iterrows():
        zc = zero_curve_from_row(d.date(), row)
        if zc is None:
            continue
        z_cc = np.log(1 + zc.zero(TAU_FIT))
        rows.append((d, *ns.fit(TAU_FIT, z_cc)))
    return pd.DataFrame(rows, columns=["date", *FACTOR_NAMES]).set_index("date")


def ar1(x: pd.Series) -> tuple[float, pd.Series]:
    """OLS AR(1) with intercept; returns phi and residuals."""
    y, xl = x.iloc[1:].values, x.iloc[:-1].values
    X = np.column_stack([np.ones_like(xl), xl])
    (c, phi), *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = pd.Series(y - (c + phi * xl), index=x.index[1:])
    return float(phi), resid


def kendall_corrected(phi: np.ndarray, n_obs: int, cap: float = 0.995) -> np.ndarray:
    """Kendall (1954) correction of OLS AR(1) coefficients, which are biased toward mean reversion in
    persistent series: phi + (1 + 3 phi) / T, capped below a unit root."""
    phi = np.asarray(phi, dtype=float)
    return np.minimum(phi + (1 + 3 * phi) / n_obs, cap)


def variance_ratio(changes: np.ndarray, h: int) -> float:
    """Variance of overlapping h-period sums over h times the one-period variance (Lo-MacKinlay, both
    around the sample mean). Below 1: mean reversion; above 1: trending."""
    r = np.asarray(changes, dtype=float)
    x, mu = np.r_[0.0, np.cumsum(r)], r.mean()
    return float(((x[h:] - x[:-h] - h * mu) ** 2).mean() / (h * ((r - mu) ** 2).mean()))


def variance_ratio_test(changes: np.ndarray, h: int, n_null: int = 20_000, seed: int = 0) -> dict:
    """The ratio against an i.i.d. null built by resampling the same changes (same length and tails, so
    the small-sample downward bias of overlapping ratios is in the null too). p: share of null ratios at
    or below the observed one, i.e. the evidence for mean reversion."""
    r = np.asarray(changes, dtype=float)
    rng = np.random.default_rng(seed)
    null = np.array([variance_ratio(rng.choice(r, len(r)), h) for _ in range(n_null)])
    vr = variance_ratio(r, h)
    return {"variance_ratio": vr, "null_median": float(np.median(null)), "p_mean_reversion": float((null <= vr).mean())}


def calibrate(eq_window_start: str = "2007-08-31", end: str = DATA_END) -> Calibration:
    fh = factor_history()
    phis, resids = [], []
    for f in FACTOR_NAMES:
        phi, res = ar1(fh[f].loc[:end])
        phis.append(min(phi, 0.995))
        resids.append(res.rename("d_" + {"level": "level", "slope": "slope", "curvature": "curv"}[f]))
    cpi = fred.cpi()["CPIAUCNS"]
    infl = (cpi / cpi.shift(12) - 1).dropna()
    infl.index = infl.index + pd.offsets.MonthEnd(0)
    infl_phi, infl_res = ar1(infl.loc["1994-01-01":end])
    eq = yahoo.monthly_returns(["VTI", "VEA", "VWO"], start="2007-01-01")
    eq = np.log1p(eq).rename(columns={"VTI": "eq_US", "VEA": "eq_DEV", "VWO": "eq_EM"})
    fx = usd_twd_monthly()
    fx = np.log(fx).diff().rename("fx_TWD")   # + = USD buys more TWD
    joint = pd.concat([eq, *resids, infl_res.rename("d_infl"), fx], axis=1, sort=True).loc[eq_window_start:end].dropna()
    joint = joint[SHOCK_NAMES]
    # Shrink the *correlation* matrix (Ledoit-Wolf on standardised data), keep sample vols.
    sd = joint.std().values
    lw = LedoitWolf().fit((joint.values - joint.values.mean(0)) / sd)
    corr = lw.covariance_ / np.sqrt(np.outer(np.diag(lw.covariance_), np.diag(lw.covariance_)))
    cov = corr * np.outer(sd, sd)
    notes = {
        "months_rates": int(fh.loc[:end].shape[0]),
        "months_joint": int(joint.shape[0]),
        "ledoit_wolf_shrinkage": float(lw.shrinkage_),
        "ann_vol": {k: float(sd[i] * np.sqrt(12)) for i, k in enumerate(SHOCK_NAMES)},
        "corr_shrunk": pd.DataFrame(corr, index=SHOCK_NAMES, columns=SHOCK_NAMES).round(2),
    }
    return Calibration(np.array(phis), float(min(infl_phi, 0.995)), cov, fh,
                       (str(joint.index.min().date()), str(joint.index.max().date())), notes)


def calibrate_assets(history_tickers: list[str], window_start: str = "2017-08-31", end: str = DATA_END,
                     vol_from: str = "2005-01-01", extra_returns: pd.DataFrame | None = None) -> dict:
    """Joint monthly shock covariance for K equity assets plus the 5 macro shocks
    (3 rate factors, inflation, USD/TWD), in that order.

    Correlations come from the common window (limited by the youngest fund) and are shrunk
    with Ledoit-Wolf; each equity volatility comes from its longest history since `vol_from`
    so that 2008-type markets are represented in risk even when correlations cannot be.
    `extra_returns` (monthly simple returns, month-end index) adds assets that are not tickers,
    such as a stock basket; they follow the history tickers in the asset order.
    """
    fh = factor_history()
    resids = []
    for f, short in zip(FACTOR_NAMES, ["level", "slope", "curv"]):
        _, res = ar1(fh[f].loc[:end])
        resids.append(res.rename("d_" + short))
    cpi = fred.cpi()["CPIAUCNS"]
    infl = (cpi / cpi.shift(12) - 1).dropna()
    infl.index = infl.index + pd.offsets.MonthEnd(0)
    _, infl_res = ar1(infl.loc["1994-01-01":end])
    fx = usd_twd_monthly()
    fx = np.log(fx).diff().rename("fx_TWD")
    eq = np.log1p(yahoo.monthly_returns(history_tickers, start="2000-01-01"))
    extra = np.log1p(extra_returns) if extra_returns is not None else pd.DataFrame(index=eq.index)
    eq = pd.concat([eq, extra], axis=1, sort=True)
    assets = list(history_tickers) + list(extra.columns)
    names = assets + ["d_level", "d_slope", "d_curv", "d_infl", "fx_TWD"]
    joint = pd.concat([eq, *resids, infl_res.rename("d_infl"), fx], axis=1, sort=True).loc[window_start:end].dropna()[names]
    sd = joint.std().values.copy()
    for i, t in enumerate(assets):              # long-history vols for equities
        r = extra[t] if t in extra else np.log1p(yahoo.monthly_returns([t], start="2000-01-01")[t])
        sd[i] = float(r.dropna().loc[vol_from:end].std())
    lw = LedoitWolf().fit((joint.values - joint.values.mean(0)) / joint.std().values)
    corr = lw.covariance_ / np.sqrt(np.outer(np.diag(lw.covariance_), np.diag(lw.covariance_)))
    return {"cov": corr * np.outer(sd, sd), "corr": pd.DataFrame(corr, index=names, columns=names),
            "names": names, "months": int(joint.shape[0]), "shrinkage": float(lw.shrinkage_),
            "window": (str(joint.index.min().date()), str(joint.index.max().date())),
            "ann_vol": dict(zip(names, sd * np.sqrt(12)))}


def calibrate_cma_dispersion(cma_path: str | Path | None = None, groups: list | None = None) -> np.ndarray:
    """Calibrate (K, K) annual expected-return covariance from cross-firm dispersion in config/cma.yaml.

    Maps firms' US, intl_dev, and EM forecasts to the K assets by region as defined in
    src/lgm/growth/universe.py.
    """
    from .growth.universe import CORE

    if cma_path is None:
        cma_path = Path(__file__).resolve().parents[2] / "config" / "cma.yaml"
    with open(cma_path) as f:
        cfg = yaml.safe_load(f)

    df = pd.DataFrame(cfg["firms"]).T[["us", "intl_dev", "em"]].astype(float)
    cma_cov = df.cov().values  # (3, 3) sample covariance, ddof=1

    groups = CORE if groups is None else groups
    # Map each group/asset to one of the 3 CMA regions: 0 -> us, 1 -> intl_dev, 2 -> em
    region_idx = []
    for g in groups:
        reg = g.region if hasattr(g, "region") else str(g)
        if reg in ("US", "us", "eq_US"):
            region_idx.append(0)
        elif reg in ("EMxChina", "China", "em", "EM", "eq_EM"):
            region_idx.append(2)
        else:  # Europe, Japan, PacificXJ, Canada, intl_dev, DEV, eq_DEV
            region_idx.append(1)

    K = len(groups)
    M = np.zeros((K, 3))
    for i, r in enumerate(region_idx):
        M[i, r] = 1.0

    return M @ cma_cov @ M.T


def calibrate_equity_garch(ticker: str = "VTI", start: str = "2001-01-01", end: str = DATA_END,
                           dof: float | None = 5.0) -> dict:
    """Calibrate GARCH(1,1) volatility process on monthly equity history (VTI 2001-2026).

    Uses variance targeting (omega = var * (1 - alpha - beta)) to strictly pin the unconditional
    variance to the historical sample variance. Maximizes Student-t (with `dof`) log-likelihood.
    Returns fitted parameters, unconditional annual volatility, today's estimated state, and
    autocorrelation of squared monthly returns at lags 1-6.
    """
    from scipy.optimize import minimize
    from scipy.special import gammaln

    ret = yahoo.monthly_returns([ticker], start=start)[ticker].loc[:end].dropna()
    r = np.log1p(ret).values
    mu = float(r.mean())
    eps = r - mu
    var_uncond = float(np.var(eps))

    def nll(params):
        alpha, beta = params
        if alpha <= 0 or beta <= 0 or alpha + beta >= 0.99:
            return 1e10
        omega = var_uncond * (1.0 - alpha - beta)
        T = len(eps)
        h = np.empty(T)
        h[0] = var_uncond
        for t in range(1, T):
            h[t] = omega + alpha * eps[t - 1] ** 2 + beta * h[t - 1]
        if dof is not None:
            s2 = h * (dof - 2.0) / dof
            return -float(np.sum(gammaln((dof + 1) / 2) - gammaln(dof / 2) - 0.5 * np.log(np.pi * dof * s2)
                                 - 0.5 * (dof + 1) * np.log(1 + eps ** 2 / (dof * s2))))
        else:
            return 0.5 * float(np.sum(np.log(h) + eps ** 2 / h))

    res = minimize(nll, [0.10, 0.75], bounds=[(0.001, 0.40), (0.001, 0.95)])
    alpha, beta = float(res.x[0]), float(res.x[1])
    omega = var_uncond * (1.0 - alpha - beta)

    T = len(eps)
    h = np.empty(T)
    h[0] = var_uncond
    for t in range(1, T):
        h[t] = omega + alpha * eps[t - 1] ** 2 + beta * h[t - 1]

    s_hist = pd.Series(eps ** 2)
    ac = [float(s_hist.autocorr(lag)) for lag in range(1, 7)]

    return {
        "alpha": alpha,
        "beta": beta,
        "omega": omega,
        "persistence": alpha + beta,
        "uncond_vol_ann": float(np.sqrt(var_uncond * 12)),
        "h0_unconditional": 1.0,
        "h0_today": float(h[-1] / var_uncond),
        "autocorr_lags_1_6": ac,
        "ticker": ticker,
        "window": (str(ret.index.min().date()), str(ret.index.max().date())),
        "n_months": len(r),
    }


def filter_equity_garch(returns: np.ndarray | pd.Series,
                        alpha: float | None = None,
                        beta: float | None = None,
                        mu: float | np.ndarray | None = None,
                        var_uncond: float | np.ndarray | None = None,
                        h0: float | np.ndarray = 1.0) -> np.ndarray:
    """Run GARCH(1,1) variance recursion over a monthly return series.

    Returns the variance state h at every month, using the same normalisation as esg.simulate
    (unconditional variance = 1.0, so h is a multiplier).

    Parameters:
    - returns: 1D array of length M or 2D array of shape (N, M).
    - alpha, beta: GARCH parameters. If None, uses calibrated parameters from calibrate_equity_garch().
    - mu: expected monthly log return. If None, uses sample mean of returns.
    - var_uncond: unconditional monthly variance. If None, uses sample variance of (returns - mu).
    - h0: initial variance state multiplier (default 1.0).

    Returns:
    - h: array of shape matching returns (length M or shape (N, M)) with h[..., 0] = h0.
    """
    if alpha is None or beta is None:
        cal = calibrate_equity_garch()
        alpha = cal["alpha"] if alpha is None else alpha
        beta = cal["beta"] if beta is None else beta
        if var_uncond is None:
            var_uncond = cal["uncond_vol_ann"] ** 2 / 12.0

    arr = np.asarray(returns, dtype=float)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr[None, :]

    N, M = arr.shape
    if mu is None:
        mu = arr.mean(axis=1, keepdims=True)
    elif np.ndim(mu) == 0:
        mu = float(mu)

    if var_uncond is None:
        var_uncond = np.var(arr - mu, axis=1, keepdims=True)
    elif np.ndim(var_uncond) == 0:
        var_uncond = float(var_uncond)

    omega = 1.0 - alpha - beta
    h = np.empty((N, M), dtype=float)
    h[:, 0] = h0

    for m in range(M - 1):
        diff = arr[:, m] - (mu[:, 0] if isinstance(mu, np.ndarray) and mu.ndim == 2 else mu)
        denom = (var_uncond[:, 0] if isinstance(var_uncond, np.ndarray) and var_uncond.ndim == 2 else var_uncond)
        innov_sq = diff ** 2 / denom
        h[:, m + 1] = omega + alpha * innov_sq + beta * h[:, m]

    return h[0] if is_1d else h


def calibrate_tail_dof(x: np.ndarray | pd.Series) -> dict:
    """Calibrate Student-t degrees of freedom for a 1D residual series.

    Returns:
      n_obs: sample size
      mean: sample mean
      std: sample standard deviation (ddof=1)
      excess_kurtosis: Fisher excess kurtosis (normal = 0)
      df_mom: moment-matched degrees of freedom: 4 + 6 / kurt (if kurt > 0 else inf)
      df_mle: maximum-likelihood degrees of freedom from scipy.stats.t.fit
    """
    vals = np.asarray(x, dtype=float)
    vals = vals[~np.isnan(vals)]
    n = len(vals)
    if n < 4:
        return {"n_obs": n, "mean": float("nan"), "std": float("nan"),
                "excess_kurtosis": float("nan"), "df_mom": float("nan"), "df_mle": float("nan")}
    mean = float(np.mean(vals))
    std = float(np.std(vals, ddof=1))
    kurt = float(stats.kurtosis(vals))
    df_mom = float(4.0 + 6.0 / kurt) if kurt > 0 else float("inf")
    try:
        df_mle, _, _ = stats.t.fit(vals)
        df_mle = float(df_mle)
    except Exception:
        df_mle = float("nan")
    return {
        "n_obs": n,
        "mean": mean,
        "std": std,
        "excess_kurtosis": kurt,
        "df_mom": df_mom,
        "df_mle": df_mle,
    }


def fit_multivariate_t(data: np.ndarray) -> dict:
    """Maximum likelihood and Mardia kurtosis fit of multivariate Student-t degrees of freedom."""
    X = np.asarray(data, dtype=float)
    N, d = X.shape
    S = np.cov(X, rowvar=False)
    invS = np.linalg.inv(S)
    mahal = np.sum((X @ invS) * X, axis=1)

    def neg_ll(nu):
        ll = N * (special.gammaln((nu + d) / 2.0) - special.gammaln(nu / 2.0)
                  - 0.5 * d * np.log((nu - 2.0) * np.pi) - 0.5 * np.linalg.slogdet(S)[1])
        ll -= 0.5 * (nu + d) * np.sum(np.log(1.0 + mahal / (nu - 2.0)))
        return -ll

    res = optimize.minimize_scalar(neg_ll, bounds=(2.01, 100.0), method="bounded")
    r = mahal.var() / (2.0 * d)
    nu_mardia = float((4.0 * r - 2.0) / (r - 1.0)) if r > 1.0 else float("inf")
    return {
        "df_mle": float(res.x),
        "df_mardia": nu_mardia,
        "mahal_mean": float(mahal.mean()),
        "mahal_var": float(mahal.var()),
    }


def crash_correlation(eq_returns: np.ndarray | pd.Series, rate_changes: np.ndarray | pd.Series,
                      q: float = 0.05) -> tuple[float, float]:
    """Correlation between equity returns and rate changes: full sample vs worst q (default 5%) of equity returns."""
    eq = np.asarray(eq_returns, dtype=float).ravel()
    rc = np.asarray(rate_changes, dtype=float).ravel()
    mask = ~np.isnan(eq) & ~np.isnan(rc)
    eq, rc = eq[mask], rc[mask]
    if len(eq) < 3:
        return float("nan"), float("nan")
    full_corr = float(np.corrcoef(eq, rc)[0, 1])
    q_val = np.percentile(eq, q * 100.0)
    crash_mask = eq <= q_val
    if np.sum(crash_mask) < 2 or np.std(eq[crash_mask]) == 0 or np.std(rc[crash_mask]) == 0:
        crash_corr = float("nan")
    else:
        crash_corr = float(np.corrcoef(eq[crash_mask], rc[crash_mask])[0, 1])
    return full_corr, crash_corr


def calibrate_block_tails(end: str = DATA_END) -> dict:
    """Calibrate tail degrees of freedom across all shock blocks from historical data."""
    fh = factor_history()
    resids = {}
    rate_res_list = []
    for f, short in zip(FACTOR_NAMES, ["level", "slope", "curv"]):
        _, res = ar1(fh[f].loc[:end])
        name = "d_" + short
        resids[name] = res
        rate_res_list.append(res)

    # 5y and 10y zero rate changes
    for tau in [5.0, 10.0]:
        z = pd.Series(ns.zero(fh.loc[:end].values, np.array([tau]))[:, 0], index=fh.loc[:end].index)
        resids[f"d_rate{int(tau)}y"] = z.diff().dropna()

    cpi = fred.cpi()["CPIAUCNS"]
    infl = (cpi / cpi.shift(12) - 1).dropna()
    infl.index = infl.index + pd.offsets.MonthEnd(0)
    _, infl_res = ar1(infl.loc["1994-01-01":end])
    resids["d_infl"] = infl_res

    fx = usd_twd_monthly()
    fx_diff = np.log(fx).diff().dropna().loc[:end]
    resids["fx_TWD"] = fx_diff

    eq = yahoo.monthly_returns(["VTI", "VEA", "VWO"], start="2000-01-01")
    eq = np.log1p(eq).loc["2007-08-31":end]
    for col in ["VTI", "VEA", "VWO"]:
        resids[f"eq_{col}"] = eq[col].dropna()

    block_stats = {k: calibrate_tail_dof(v) for k, v in resids.items()}

    # Multivariate t fit on 3 rate factors
    rate_mat = pd.concat(rate_res_list, axis=1).dropna().values
    block_stats["rates_3d_joint"] = fit_multivariate_t(rate_mat)

    # Historical crash correlations (VTI vs 5y rate change, and core sleeve vs 5y rate change)
    dz_5y = resids["d_rate5y"]
    vti = eq["VTI"]
    eq_core = 0.6 * eq["VTI"] + 0.3 * eq["VEA"] + 0.1 * eq["VWO"]
    common_us = pd.concat([vti.rename("eq"), dz_5y.rename("dr")], axis=1, sort=True).dropna()
    common_core = pd.concat([eq_core.rename("eq"), dz_5y.rename("dr")], axis=1, sort=True).dropna()

    us_full, us_crash = crash_correlation(common_us["eq"], common_us["dr"])
    core_full, core_crash = crash_correlation(common_core["eq"], common_core["dr"])

    block_stats["crash_correlation"] = {
        "vti_vs_5y_rate": {"full": us_full, "crash_worst5pct": us_crash, "n_months": len(common_us)},
        "core_vs_5y_rate": {"full": core_full, "crash_worst5pct": core_crash, "n_months": len(common_core)},
    }
    return block_stats


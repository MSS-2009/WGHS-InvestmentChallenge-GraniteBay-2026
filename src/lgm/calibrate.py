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

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from . import nelson_siegel as ns
from .curve import ParCurve, bootstrap
from .data import fred, treasury, yahoo

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
    """Month-end USD/TWD from daily data, dropping bad prints (e.g. 3.67 on one day in Dec 2014)."""
    fx = yahoo.history("TWD=X", start="2003-01-01", interval="1d")["close"]
    fx = fx[(fx > 20) & (fx < 45)]
    return fx.resample("ME").last().ffill()


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


def calibrate(eq_window_start: str = "2007-08-31", end: str = "2026-09-30") -> Calibration:
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


def calibrate_assets(history_tickers: list[str], window_start: str = "2017-08-31", end: str = "2026-09-30",
                     vol_from: str = "2005-01-01") -> dict:
    """Joint monthly shock covariance for K equity assets plus the 5 macro shocks
    (3 rate factors, inflation, USD/TWD), in that order.

    Correlations come from the common window (limited by the youngest fund) and are shrunk
    with Ledoit-Wolf; each equity volatility comes from its longest history since `vol_from`
    so that 2008-type markets are represented in risk even when correlations cannot be.
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
    names = list(history_tickers) + ["d_level", "d_slope", "d_curv", "d_infl", "fx_TWD"]
    joint = pd.concat([eq, *resids, infl_res.rename("d_infl"), fx], axis=1, sort=True).loc[window_start:end].dropna()[names]
    sd = joint.std().values.copy()
    for i, t in enumerate(history_tickers):     # long-history vols for equities
        r = np.log1p(yahoo.monthly_returns([t], start="2000-01-01")[t]).loc[vol_from:end]
        sd[i] = float(r.std())
    lw = LedoitWolf().fit((joint.values - joint.values.mean(0)) / joint.std().values)
    corr = lw.covariance_ / np.sqrt(np.outer(np.diag(lw.covariance_), np.diag(lw.covariance_)))
    return {"cov": corr * np.outer(sd, sd), "corr": pd.DataFrame(corr, index=names, columns=names),
            "names": names, "months": int(joint.shape[0]), "shrinkage": float(lw.shrinkage_),
            "window": (str(joint.index.min().date()), str(joint.index.max().date())),
            "ann_vol": dict(zip(names, sd * np.sqrt(12)))}

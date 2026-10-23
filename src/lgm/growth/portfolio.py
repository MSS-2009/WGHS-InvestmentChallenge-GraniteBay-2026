"""Core + satellite: the stock satellite as one more asset in the Black-Litterman system.

The satellite is an HRP-weighted basket of the selected stocks, rebalanced monthly to fixed
weights. In equilibrium it earns its CAPM-implied return (zero alpha by construction). The
stock-selection view enters Black-Litterman as alpha over that equilibrium return, relative to
the US large-cap ETFs that fund it, so the posterior alpha is shrunk by the view's uncertainty.
The satellite is carved out of VUG/VTV pro rata: the core's region and style decisions stand.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..asof import DATA_END
from ..calibrate import calibrate_assets
from ..data import yahoo
from . import black_litterman as bl
from .core import to_arithmetic
from .qualitative import hrp_weights
from .universe import CORE

FUNDING = ("us_growth", "us_value")
STYLE = ("us_growth", "us_value", "us_small")     # benchmark for the alpha view (Sharpe style analysis)
SHORT_CACHE_START = pd.Timestamp("2018-01-01")    # the screen cached prices from 2018 only


def long_prices(tickers: list[str], start: str = "2000-01-01") -> pd.DataFrame:
    """Month-end adjusted prices with full history (for long-history volatility)."""
    cols = {}
    for t in tickers:
        h = yahoo.history(t, start=start, interval="1mo")
        if h.index.min() == SHORT_CACHE_START:
            h = yahoo.history(t, start=start, interval="1mo", refresh=True)
        cols[t] = h["adjclose"].resample("ME").last()
    return pd.DataFrame(cols)


def satellite_weights(tickers: list[str], end: str = DATA_END, months: int = 60) -> pd.Series:
    r = long_prices(tickers).pct_change().loc[:end].iloc[-months:]
    return hrp_weights(r)


def basket_returns(w: pd.Series, end: str = DATA_END) -> pd.Series:
    """Fixed-weight basket, renormalised over the names trading in each month. Before every name
    existed this has survivorship bias in its mean, so only its volatility and correlations are used."""
    r = long_prices(list(w.index)).pct_change().loc[:end].iloc[1:]
    ww = r.notna().mul(w, axis=1)
    ww = ww.div(ww.sum(1), axis=0)
    out = (r.fillna(0) * ww).sum(1)
    return out[ww.notna().all(1)].rename("SAT")


def with_satellite(core: dict, sat_returns: pd.Series, view: dict, groups=CORE) -> dict:
    """Prior, views and posterior for the K core groups plus the satellite (last asset)."""
    K = len(groups)
    cal = calibrate_assets([g.history for g in groups], extra_returns=sat_returns.to_frame("SAT"))
    cov = cal["cov"][:K + 1, :K + 1] * 12
    var = np.diag(cov)
    w_mkt = np.r_[core["w_mkt"], 0.0]
    pi = bl.implied_returns(cov, w_mkt, core["delta"])
    idx = [i for i, g in enumerate(groups) if g.key in STYLE]
    b = style_weights(cov, idx, K)
    p_sat = np.zeros(K + 1)
    p_sat[idx] = -b
    p_sat[K] = 1.0
    views = [(v[0], np.r_[v[1], 0.0], v[2], v[3]) for v in core["views"]]
    views.append(("Satellite alpha over its style benchmark", p_sat, float(p_sat @ pi) + view["alpha"], view["std"]))
    def post(vs):
        P = np.array([v[1] for v in vs])
        Q = to_arithmetic(P, np.array([v[2] for v in vs]), cov)
        Q[len(core["views"]):] = [v[2] for v in vs[len(core["views"]):]]   # the alpha view is already arithmetic
        m = bl.posterior(cov, pi, P, Q, np.diag([v[3] ** 2 for v in vs]), core["cfg"]["tau"])[0]
        return bl.anchor_to_prior(m, pi, w_mkt) if core["cfg"].get("anchor_market_to_consensus", True) else m

    mu, mu_core_views = post(views), post(views[:-1])
    spill = float(p_sat @ (mu_core_views - pi))      # what the style views alone imply (near zero by design)
    total = float(p_sat @ (mu - pi))
    return {"cal": cal, "cov": cov, "var": var, "pi": pi, "mu": mu, "w_mkt": w_mkt, "p_sat": p_sat,
            "style": {groups[i].etf: float(x) for i, x in zip(idx, b)},
            "views": views, "alpha_prior": view["alpha"], "alpha_post": total - spill, "alpha_spillover": spill,
            "tracking_error": float(np.sqrt(p_sat @ cov @ p_sat)),
            "beta_vs_market": float(cov[K] @ w_mkt / (w_mkt @ cov @ w_mkt))}


def style_weights(cov: np.ndarray, idx: list[int], k: int) -> np.ndarray:
    """Long-only weights on the style ETFs that best track asset k (Sharpe 1992 style analysis)."""
    from scipy.optimize import minimize

    c, s = cov[np.ix_(idx, idx)], cov[idx, k]
    f = lambda b: cov[k, k] - 2 * b @ s + b @ c @ b
    res = minimize(f, np.full(len(idx), 1 / len(idx)), method="SLSQP", bounds=[(0, 1)] * len(idx),
                   constraints=[{"type": "eq", "fun": lambda b: b.sum() - 1}])
    return res.x


def carve(w_core: np.ndarray, share: float, groups=CORE) -> np.ndarray:
    """Equity weights with `share` moved from VUG/VTV (pro rata) into the satellite."""
    w = np.r_[w_core, 0.0]
    idx = [i for i, g in enumerate(groups) if g.key in FUNDING]
    w[idx] -= share * w[idx] / w[idx].sum()
    w[-1] = share
    return w


def whole_shares(w: pd.Series, price: pd.Series, budget: float) -> pd.Series:
    """Whole-share counts closest to target dollars without exceeding the budget: round to nearest,
    then trim the most overweight names until it fits, then add to the most underweight that fit."""
    target = w * budget
    n = (target / price).round()
    while (n * price).sum() > budget:
        over = (n * price - target).where(n > 0)
        n[over.idxmax()] -= 1
    while True:
        cash = budget - (n * price).sum()
        gap = (target - n * price).where(price <= cash)
        if gap.dropna().empty or gap.max() <= 0.5 * price[gap.idxmax()]:
            return n.astype(int)
        n[gap.idxmax()] += 1

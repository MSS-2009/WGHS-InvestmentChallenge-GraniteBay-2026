"""Build the ETF core: market weights, Black-Litterman views from published CMAs, and a
constrained optimisation. All figures annual."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..calibrate import calibrate_assets
from . import black_litterman as bl
from .lookthrough import market_weights_and_exposures
from .universe import CORE

CFG = Path(__file__).resolve().parents[3] / "config" / "cma.yaml"


def _view_stats(diffs: list[float], cfg: dict) -> tuple[float, float]:
    q = float(np.median(diffs))
    s = cfg["single_source_std"] if len(diffs) == 1 else max(float(np.std(diffs, ddof=1)), cfg["view_std_floor"])
    return q, s


def build_views(groups, w_mkt, cfg: dict):
    """Relative views (geometric return differences) with their uncertainty."""
    idx = {g.key: i for i, g in enumerate(groups)}
    n = len(groups)

    def basket(keys):
        v = np.zeros(n)
        tot = sum(w_mkt[idx[k]] for k in keys)
        for k in keys:
            v[idx[k]] = w_mkt[idx[k]] / tot
        return v

    us = basket(["us_growth", "us_value", "us_small"])
    us_large = basket(["us_growth", "us_value"])
    dev = basket(["europe", "japan", "pacific", "canada"])
    em = basket(["em_xchina", "china"])
    firms = cfg["firms"]
    views = []
    q, s = _view_stats([f["intl_dev"] - f["us"] for f in firms.values()], cfg)
    views.append(("International developed minus US", dev - us, q, s, len(firms)))
    q, s = _view_stats([f["em"] - f["intl_dev"] for f in firms.values()], cfg)
    views.append(("Emerging minus international developed", em - dev, q, s, len(firms)))
    vals = list(cfg["us_value_minus_growth"].values())
    q, s = _view_stats(vals, cfg)
    e = np.zeros(n); e[idx["us_value"]], e[idx["us_growth"]] = 1, -1
    views.append(("US value minus US growth", e, q, s, len(vals)))
    vals = list(cfg["us_small_minus_large"].values())
    q, s = _view_stats(vals, cfg)
    e = np.zeros(n); e[idx["us_small"]] = 1
    views.append(("US small minus US large", e - us_large, q, s, len(vals)))
    return views


def build_core(groups=CORE) -> dict:
    cfg = yaml.safe_load(CFG.read_text())
    mw = market_weights_and_exposures(groups)
    w_mkt = mw["w_mkt"]
    cal = calibrate_assets([g.history for g in groups])
    K = len(groups)
    cov = cal["cov"][:K, :K] * 12
    var = np.diag(cov)
    firms = cfg["firms"]
    # Consensus market return: median firm forecasts weighted by ACWI region weights
    us_w = sum(w_mkt[i] for i, g in enumerate(groups) if g.region == "US")
    em_w = sum(w_mkt[i] for i, g in enumerate(groups) if g.region in ("EMxChina", "China"))
    dev_w = 1 - us_w - em_w
    med = {k: float(np.median([f[k] for f in firms.values()])) for k in ("us", "intl_dev", "em")}
    mkt_geo = us_w * med["us"] + dev_w * med["intl_dev"] + em_w * med["em"]
    mkt_var = float(w_mkt @ cov @ w_mkt)
    mkt_excess = mkt_geo + 0.5 * mkt_var - cfg["cash_long_run"]
    delta = bl.risk_aversion(cov, w_mkt, mkt_excess)
    pi = bl.implied_returns(cov, w_mkt, delta)
    views = build_views(groups, w_mkt, cfg)
    P = np.array([v[1] for v in views])
    Q_geo = np.array([v[2] for v in views])
    Q = Q_geo + 0.5 * P @ var                      # geometric -> arithmetic differences
    omega = np.diag([v[3] ** 2 for v in views])
    mu, cov_post = bl.posterior(cov, pi, P, Q, omega, cfg["tau"])
    # Constraints: stay within [0.5x, 2x] of market weight (+10pp cap); no look-through overweight
    # in tech/communication or in China+Taiwan (client background check, Section V).
    lb = 0.5 * w_mkt
    ub = np.minimum(2.0 * w_mkt, w_mkt + 0.10)
    ineq = [(mw["tech"], float(w_mkt @ mw["tech"])), (mw["china_taiwan"], float(w_mkt @ mw["china_taiwan"]))]
    w_bl = bl.optimise(mu, cov_post, delta, lb, ub, ineq, w0=w_mkt)
    w_unc = bl.optimise(mu, cov_post, delta, np.zeros(K), np.ones(K), None, w0=w_mkt)
    table = pd.DataFrame({
        "group": [g.name for g in groups], "etf": [g.etf for g in groups],
        "w_mkt": w_mkt, "vol": np.sqrt(var), "pi_excess": pi, "bl_excess": mu,
        "bl_geo_total": mu + cfg["cash_long_run"] - 0.5 * var,
        "w_bl": w_bl, "w_bl_unconstrained": w_unc, "tech_share": mw["tech"], "china_taiwan_share": mw["china_taiwan"],
    })
    return {"table": table, "delta": delta, "mkt_excess": mkt_excess, "mkt_geo": mkt_geo, "views": views,
            "Q_arith": Q, "cal": cal, "cfg": cfg, "w_mkt": w_mkt, "w_bl": w_bl, "mu": mu, "cov": cov,
            "exposures": mw}

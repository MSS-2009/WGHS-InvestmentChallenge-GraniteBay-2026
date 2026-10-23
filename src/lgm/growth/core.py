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


def _view_stats(diffs: list[float], cfg: dict, forecasters: int | None = None) -> tuple[float, float]:
    """Size = median of all sources; uncertainty = their spread, unless only one source is a forecast
    (long-run averages do not count), in which case the single-source uncertainty applies."""
    q = float(np.median(diffs))
    n = len(diffs) if forecasters is None else forecasters
    s = cfg["single_source_std"] if n <= 1 else max(float(np.std(diffs, ddof=1)), cfg["view_std_floor"])
    return q, s


def _sources(block: dict) -> tuple[list[float], int]:
    return list(block.values()), sum(1 for k in block if not str(k).startswith("History"))


def to_arithmetic(P: np.ndarray, Q_geo: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Geometric -> arithmetic for relative views on baskets: each leg gains half its own basket
    variance, p'Sigma p, not the weighted sum of its members' variances."""
    pos, neg = np.clip(P, 0, None), np.clip(-P, 0, None)
    return Q_geo + 0.5 * (np.einsum("vi,ij,vj->v", pos, cov, pos) - np.einsum("vi,ij,vj->v", neg, cov, neg))


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
    vals, n_fc = _sources(cfg["us_value_minus_growth"])
    q, s = _view_stats(vals, cfg, n_fc)
    e = np.zeros(n); e[idx["us_value"]], e[idx["us_growth"]] = 1, -1
    views.append(("US value minus US growth", e, q, s, len(vals)))
    vals, n_fc = _sources(cfg["us_small_minus_large"])
    q, s = _view_stats(vals, cfg, n_fc)
    e = np.zeros(n); e[idx["us_small"]] = 1
    views.append(("US small minus US large", e - us_large, q, s, len(vals)))
    return views


def build_core(groups=CORE, cfg: dict | None = None, cal: dict | None = None) -> dict:
    """`cfg` overrides config/cma.yaml and `cal` reuses a calibration (for sensitivity runs)."""
    cfg = cfg or yaml.safe_load(CFG.read_text())
    mw = market_weights_and_exposures(groups)
    w_mkt = mw["w_mkt"]
    cal = cal or calibrate_assets([g.history for g in groups])
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
    # The firms forecast each region's geometric return; the market's arithmetic return is the
    # weighted sum of the regions' arithmetic returns (each region's own basket variance).
    def region_basket(keys):
        b = np.array([w_mkt[i] if g.region in keys else 0.0 for i, g in enumerate(groups)])
        return b / b.sum()
    mkt_arith = 0.0
    for keys, wt, k in ((("US",), us_w, "us"), (("EMxChina", "China"), em_w, "em"),
                        (tuple({g.region for g in groups} - {"US", "EMxChina", "China"}), dev_w, "intl_dev")):
        b = region_basket(keys)
        mkt_arith += wt * (med[k] + 0.5 * float(b @ cov @ b))
    mkt_excess = mkt_arith - cfg["cash_long_run"]
    delta = bl.risk_aversion(cov, w_mkt, mkt_excess)
    pi = bl.implied_returns(cov, w_mkt, delta)
    views = build_views(groups, w_mkt, cfg)
    P = np.array([v[1] for v in views])
    Q_geo = np.array([v[2] for v in views])
    Q = to_arithmetic(P, Q_geo, cov)
    omega = np.diag([v[3] ** 2 for v in views])
    mu, cov_post = bl.posterior(cov, pi, P, Q, omega, cfg["tau"])
    if cfg.get("anchor_market_to_consensus", True):
        mu = bl.anchor_to_prior(mu, pi, w_mkt)
    mu_cov = cov_post - cov                         # uncertainty of the posterior mean
    # Constraints: stay within [0.5x, 2x] of market weight (+10pp cap); no look-through overweight
    # in tech/communication or in China+Taiwan (client background check, Section V).
    lb = 0.5 * w_mkt
    ub = np.minimum(2.0 * w_mkt, w_mkt + 0.10)
    ineq = [(mw["tech"], float(w_mkt @ mw["tech"])), (mw["china_taiwan"], float(w_mkt @ mw["china_taiwan"]))]
    # Risk in the optimiser is the prior covariance: with no views it then returns the market
    # exactly, and the uncertainty of the means enters once, through the resampling draws.
    w_point = bl.optimise(mu, cov, delta, lb, ub, ineq, w0=w_mkt)
    w_bl, w_sd = bl.resampled_optimise(mu, mu_cov, cov, delta, lb, ub, ineq, n=cfg.get("resample_draws", 500), w0=w_mkt)
    w_unc = bl.optimise(mu, cov, delta, np.zeros(K), np.ones(K), None, w0=w_mkt)
    table = pd.DataFrame({
        "group": [g.name for g in groups], "etf": [g.etf for g in groups],
        "w_mkt": w_mkt, "vol": np.sqrt(var), "pi_excess": pi, "bl_excess": mu,
        "bl_geo_total": mu + cfg["cash_long_run"] - 0.5 * var,
        "w_bl": w_bl, "w_bl_draw_std": w_sd, "w_bl_point": w_point, "w_bl_unconstrained": w_unc, "tech_share": mw["tech"], "china_taiwan_share": mw["china_taiwan"],
    })
    return {"table": table, "delta": delta, "mkt_excess": mkt_excess, "mkt_geo": mkt_geo, "views": views,
            "Q_arith": Q, "cal": cal, "cfg": cfg, "w_mkt": w_mkt, "w_bl": w_bl, "mu": mu, "cov": cov,
            "exposures": mw}

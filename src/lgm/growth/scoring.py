"""Score candidate growth sleeves with the Part 1 Monte Carlo against Laura's goals.

Every candidate is expressed as weights on the same K core groups and run under the same
scenarios, so differences come only from the portfolio. Beliefs (expected returns) are a
parameter: score under Black-Litterman and under market-implied equilibrium returns to see
whether a tilt only pays off if its views are right.
"""
from __future__ import annotations

import dataclasses as dc

import numpy as np

from .. import engine
from ..asof import CURVE_DATE, DATA_END
from ..curve import bootstrap
from ..data.treasury import par_curve
from ..esg import ESGParams, initial_state, simulate
from ..strategies import IPS


def market_inflation(curve_date: str, tenor: float = 7.0) -> float:
    """Breakeven inflation (nominal minus TIPS par yield) at the tenor nearest Laura's horizon."""
    from ..data.treasury import breakevens

    year = int(curve_date[:4])
    return float(breakevens(start=year - 1, end=year)[tenor].loc[:curve_date].dropna().iloc[-1])


def latest_inflation(month_end: str = DATA_END) -> float:
    """US CPI inflation, year over year, for the last month of data (FRED CPIAUCNS)."""
    from ..data import fred

    cpi = fred.cpi()["CPIAUCNS"]
    return float((cpi / cpi.shift(12) - 1).dropna().loc[:month_end].iloc[-1])


def taiwan_cost_params(drift_key: str = "full_sample_35y") -> dict:
    """ESGParams fields for the fitted monthly AR(2) Taiwan building-cost process (config/taiwan.yaml,
    docs/loop/r3_taiwan_findings.md), started from the Aug and Sep 2026 DGBAS readings."""
    import yaml

    from ..asof import CFG

    tw = yaml.safe_load((CFG.parent / "taiwan.yaml").read_text())["fitted_monthly"]
    return {"tw_cost_growth": tw["drifts"][drift_key], "tw_cost_phi": tuple(tw["tw_cost_phi"]),
            "tw_cost_sig_eps": tw["tw_cost_sig_eps"], "tw_cost_state0": tuple(tw["tw_cost_state0_today"]),
            "tw_cost_fx_corr": tw["usd_twd_innovation_corr"]}


def esg_params(cal: dict, eq_geo: np.ndarray, curve_date: str = CURVE_DATE, infl_phi: float = 0.966,
               phi: np.ndarray | None = None, infl_mu: float | None = None) -> ESGParams:
    """Inflation starts at the latest CPI reading and reverts toward market breakeven inflation unless
    `infl_mu` is given. Rate-factor persistence is bias-corrected (`calibrate.kendall_corrected`); rate
    shocks are Gaussian while equities keep Student-t(5) tails (docs/loop/r4_rates_findings.md); Taiwan
    building costs follow the fitted AR(2)."""
    from ..profiles import _cal

    zc = bootstrap(par_curve(curve_date))
    beta0, resid = initial_state(zc)
    if phi is None:
        # Rate factors: OLS persistence corrected for its small-sample bias, so the 74-month spread of
        # rate changes comes closer to history's (5-year rate sd: 1.26 -> 1.61 points; history 1.84)
        from ..calibrate import kendall_corrected

        cal_ = _cal()
        phi = kendall_corrected(cal_.phi, cal_.notes["months_rates"])
    return ESGParams(months=engine.M_2033, beta0=beta0, resid=resid, beta_mu=beta0.copy(), phi=phi,
                     cov=cal["cov"], eq_geo=np.asarray(eq_geo), infl0=latest_inflation(),
                     infl_mu=market_inflation(curve_date) if infl_mu is None else infl_mu,
                     infl_phi=_cal().infl_phi, t_dof=5.0, rate_dof="gaussian", **taiwan_cost_params())


def score(weights: dict[str, np.ndarray], ers: dict[str, np.ndarray], params: ESGParams, n: int = 20_000,
          seed: int = 11, strategy=IPS, with_2031: bool = True,
          engine_kw: dict[str, dict] | None = None) -> dict[str, dict]:
    """`engine_kw` sets per-candidate EngineConfig fields (e.g. the satellite's extra trades)."""
    sc = simulate(params, n=n, seed=seed)
    out = {}
    for name, w in weights.items():
        st = dc.replace(strategy, region_weights=tuple(np.asarray(w) / np.sum(w)))
        cfg = engine.EngineConfig(eq_er=tuple(ers[name]), **(engine_kw or {}).get(name, {}))
        r = engine.run(st, sc, cfg, snapshot_2031=with_2031)
        s = engine.summarize(r)
        if with_2031:
            c = engine.conditional_2031_band(st, sc, r, params, cfg=cfg, n_inner=3000)
            s.update({"floor_2031": c["floor"], "range80_lo": c["p10"], "range80_hi": c["p90"]})
        s["contribution_median"] = float(np.median(r["contribution"]))
        out[name] = s
    return out

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
from ..curve import bootstrap
from ..data.treasury import par_curve
from ..esg import ESGParams, initial_state, simulate
from ..strategies import IPS


def market_inflation(curve_date: str, tenor: float = 7.0) -> float:
    """Breakeven inflation (nominal minus TIPS par yield) at the tenor nearest Laura's horizon."""
    from ..data.treasury import breakevens

    year = int(curve_date[:4])
    return float(breakevens(start=year - 1, end=year)[tenor].loc[:curve_date].dropna().iloc[-1])


def esg_params(cal: dict, eq_geo: np.ndarray, curve_date: str = "2026-10-20", infl_phi: float = 0.966,
               phi: np.ndarray | None = None, infl_mu: float | None = None) -> ESGParams:
    """Inflation reverts from September's 3.7% toward market breakeven inflation unless `infl_mu` is given."""
    from ..profiles import _cal

    zc = bootstrap(par_curve(curve_date))
    beta0, resid = initial_state(zc)
    phi = _cal().phi if phi is None else phi
    return ESGParams(months=engine.M_2033, beta0=beta0, resid=resid, beta_mu=beta0.copy(), phi=phi,
                     cov=cal["cov"], eq_geo=np.asarray(eq_geo), infl0=0.0374,
                     infl_mu=market_inflation(curve_date) if infl_mu is None else infl_mu,
                     infl_phi=_cal().infl_phi, t_dof=5.0)


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
            c = engine.conditional_2031(st, sc, r, params, cfg=cfg, n_inner=3000)
            s.update({"floor_2031": c["floor"], "range80_lo": c["p10"], "range80_hi": c["p90"]})
        s["contribution_median"] = float(np.median(r["contribution"]))
        out[name] = s
    return out

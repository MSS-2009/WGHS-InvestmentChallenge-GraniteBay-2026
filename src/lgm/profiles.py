"""Assemble scenario-generator parameters for an assumption profile."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .asof import CURVE_DATE
from .calibrate import calibrate
from .curve import bootstrap
from .data.treasury import par_curve
from .esg import ESGParams, initial_state
from .engine import M_2033


@lru_cache(maxsize=1)
def _cal():
    return calibrate()


def sleeve_vol(cov: np.ndarray, w=(0.6, 0.3, 0.1)) -> float:
    w = np.asarray(w)
    return float(np.sqrt(w @ cov[:3, :3] @ w * 12))


def region_drifts_for_sleeve(sleeve_geo: float, cov_m: np.ndarray, w=(0.6, 0.3, 0.1)) -> np.ndarray:
    """Equal per-region median returns such that the annually rebalanced sleeve compounds at
    `sleeve_geo`. Rebalancing adds 0.5*(sum w_i s_i^2 - s_p^2) (the diversification return)."""
    w = np.asarray(w)
    c = cov_m[:3, :3] * 12
    bonus = 0.5 * (w @ np.diag(c) - w @ c @ w)
    return np.full(3, np.expm1(np.log1p(sleeve_geo) - bonus))


def cs_team(curve_date: str = CURVE_DATE, months: int = M_2033, t_dof: float | None = 5.0) -> ESGParams:
    """The former CS team's documented inputs: equity 6.06%/yr net of fees for the 60/30/10
    sleeve, 16.5% volatility, rates unchanged on average (their 'expected path')."""
    cal = _cal()
    zc = bootstrap(par_curve(curve_date))
    beta0, resid = initial_state(zc)
    scale = 0.165 / sleeve_vol(cal.cov)
    gross = region_drifts_for_sleeve(0.0606, cal.cov * scale ** 2) + np.array([0.0003, 0.0003, 0.0006])
    return ESGParams(months=months, beta0=beta0, resid=resid, beta_mu=beta0.copy(), phi=cal.phi,
                     cov=cal.cov, eq_geo=gross, eq_vol_scale=scale, infl0=0.0374, infl_mu=0.03,
                     infl_phi=cal.infl_phi, t_dof=t_dof)

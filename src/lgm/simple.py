"""Exact re-implementation of the former CS team's guide, Steps 1-7.

These are the hand-checkable building blocks. The full model (engine.py) replaces the
flat-rate and lognormal shortcuts, but every number here must match the guide exactly so the
guide can be trusted as a teaching document.
"""
from __future__ import annotations

import numpy as np

from .curve import ParCurve, pv_par_as_zero

PMT, N_PAY = 50_000.0, 10
DEP1, DEP2 = 300_000.0, 150_000.0


def reserve_pv(rate: float, n: int = N_PAY, pmt: float = PMT) -> float:
    """Step 1: value in Jan 2033 of ten start-of-year payments (annuity due)."""
    return float(sum(pmt / (1 + rate) ** k for k in range(n)))


def portfolio_2033(g: float) -> float:
    """Step 2: both deposits grown at a constant annual return to Jan 2033."""
    return DEP1 * (1 + g) ** 6 + DEP2 * (1 + g) ** 5


def facility(g: float, rate: float) -> float:
    """Step 3: what is left for the facility after setting aside the reserve."""
    return portfolio_2033(g) - reserve_pv(rate)


def lock_cost_flat(rate: float) -> float:
    """Step 4A: cost in Jan 2027 of locking all ten payments at one flat rate."""
    return reserve_pv(rate) / (1 + rate) ** 6


def lock_cost_par_as_zero(par: ParCurve) -> float:
    """Step 4B: each payment discounted at the par yield for its maturity (guide shortcut)."""
    return pv_par_as_zero(par, [(float(t), PMT) for t in range(6, 16)])


def strategy_g(stock_return: float, rate_2033: float, bond: float = 0.05, w: float = 0.6) -> float:
    """Step 5, strategy G: 60/40 until 2033, buy the reserve then."""
    return facility(w * stock_return + (1 - w) * bond, rate_2033)


def strategy_l(stock_return: float, sixty_forty: bool, bond: float = 0.05, w: float = 0.6) -> float:
    """Step 5, strategy L: $300k buys the ladder; $150k grows 2028-2033."""
    g = w * stock_return + (1 - w) * bond if sixty_forty else stock_return
    return DEP2 * (1 + g) ** 5


def floor_2031(g: float = 0.06, lock_share: float = 0.6, two_year: float = 0.0474) -> dict[str, float]:
    """Step 6: lock part of the growth money into a 2-year Treasury in Jan 2031."""
    growth_2031 = DEP2 * (1 + g) ** 3
    locked = growth_2031 * lock_share
    floor = locked * (1 + two_year) ** 2
    rest = growth_2031 * (1 - lock_share) * (1 + g) ** 2
    return {"growth_2031": growth_2031, "locked": locked, "floor": floor, "rest": rest, "total": floor + rest}


def simple_monte_carlo(n: int = 200_000, seed: int = 7, mu_geo: float = 0.06, vol: float = 0.165,
                       reserve: float | None = None, random_rate: bool = False) -> dict[str, np.ndarray]:
    """Step 7: the guide's spreadsheet Monte Carlo (lognormal stocks, bonds at 5%)."""
    rng = np.random.default_rng(seed)
    r = np.exp(np.log(1 + mu_geo) + vol * rng.standard_normal((n, 6))) - 1  # 2027..2032
    port = 0.6 * r + 0.02
    v = DEP1 * (1 + port[:, 0])
    v = (v + DEP2) * np.prod(1 + port[:, 1:], axis=1)
    if random_rate:
        rate = np.maximum(0.01, 0.045 + 0.01 * rng.standard_normal(n))
        res = np.array([reserve_pv(x) for x in rate])
    else:
        res = np.full(n, reserve_pv(0.045) if reserve is None else reserve)
    return {
        "g_value": v,
        "g_funded": v >= res,
        "g_facility": np.maximum(0.0, v - res),
        "l100": DEP2 * np.prod(1 + r[:, 1:], axis=1),
        "l6040": DEP2 * np.prod(1 + port[:, 1:], axis=1),
        "reserve": res,
    }

"""US Treasury yield curve.

Treasury publishes *par* yields (bond-equivalent, semiannual compounding). A par yield is
the coupon a bond would need to price at 100, so it mixes the rates for every coupon date.
To value a single future payment we need the *zero-coupon* (spot) rate for that date, which
we get by bootstrapping: solve for discount factors maturity by maturity on a semiannual grid.

Conventions
- Par yields between published tenors are interpolated linearly (or with PCHIP, optional).
- Discount factors are interpolated log-linearly (piecewise-flat forward rates).
- `zero(t)` returns annually compounded rates so they line up with the case's annual flows.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np

from .dates import as_date

# Column names used by Treasury's daily par yield curve CSV, mapped to years.
TREASURY_TENORS: dict[str, float] = {
    "1 Mo": 1 / 12, "1.5 Month": 1.5 / 12, "2 Mo": 2 / 12, "3 Mo": 3 / 12, "4 Mo": 4 / 12,
    "6 Mo": 0.5, "1 Yr": 1.0, "2 Yr": 2.0, "3 Yr": 3.0, "5 Yr": 5.0, "7 Yr": 7.0,
    "10 Yr": 10.0, "20 Yr": 20.0, "30 Yr": 30.0,
}


@dataclass(frozen=True)
class ParCurve:
    """Published par yields for one date. `par` is in decimals (0.0512 = 5.12%)."""

    date: dt.date
    tenors: np.ndarray
    par: np.ndarray

    @classmethod
    def from_points(cls, date: dt.date | str, points: dict[float, float]) -> "ParCurve":
        """Build from {tenor_years: yield_in_percent}."""
        t = np.array(sorted(points), dtype=float)
        y = np.array([points[k] for k in sorted(points)], dtype=float) / 100.0
        return cls(as_date(date), t, y)

    def par_at(self, t: float | np.ndarray, method: str = "linear") -> np.ndarray:
        t = np.asarray(t, dtype=float)
        if method == "linear":
            return np.interp(t, self.tenors, self.par)
        if method == "pchip":
            from scipy.interpolate import PchipInterpolator

            f = PchipInterpolator(self.tenors, self.par, extrapolate=False)
            out = f(np.clip(t, self.tenors[0], self.tenors[-1]))
            return np.asarray(out)
        raise ValueError(f"unknown interpolation method {method!r}")

    def shifted(self, bp: float) -> "ParCurve":
        return ParCurve(self.date, self.tenors, self.par + bp / 1e4)


@dataclass(frozen=True)
class ZeroCurve:
    """Discount curve on knot times (years from `date`)."""

    date: dt.date
    knots: np.ndarray
    log_df: np.ndarray

    def df(self, t: float | np.ndarray) -> np.ndarray:
        t = np.asarray(t, dtype=float)
        if np.any(t < 0):
            raise ValueError("discount factor requested for a past date")
        last_fwd = -(self.log_df[-1] - self.log_df[-2]) / (self.knots[-1] - self.knots[-2])
        inside = np.interp(t, self.knots, self.log_df)
        beyond = self.log_df[-1] - last_fwd * (t - self.knots[-1])
        return np.exp(np.where(t <= self.knots[-1], inside, beyond))

    def zero(self, t: float | np.ndarray) -> np.ndarray:
        """Annually compounded zero-coupon rate for maturity t (years)."""
        t = np.maximum(np.asarray(t, dtype=float), 1e-9)
        return self.df(t) ** (-1.0 / t) - 1.0

    def df_date(self, d: dt.date | str) -> float:
        from .dates import year_frac

        return float(self.df(year_frac(self.date, d)))

    def shifted(self, bp: float) -> "ZeroCurve":
        """Parallel shift of continuously compounded zero rates by `bp` basis points."""
        return ZeroCurve(self.date, self.knots, self.log_df - (bp / 1e4) * self.knots)


def bootstrap(par: ParCurve, method: str = "linear", max_t: float = 30.0) -> ZeroCurve:
    """Bootstrap discount factors from par yields on a semiannual grid.

    For maturity n (in half-years) a par bond with coupon c = y/2 per period satisfies
        1 = c * sum_{i<=n} DF_i + DF_n   =>   DF_n = (1 - c * sum_{i<n} DF_i) / (1 + c).
    The 6-month point is a bill: DF = 1 / (1 + y/2).
    """
    grid = np.arange(0.5, max_t + 1e-9, 0.5)
    ys = par.par_at(grid, method=method)
    dfs: list[float] = []
    running = 0.0
    for y in ys:
        c = y / 2.0
        df = (1.0 - c * running) / (1.0 + c)
        dfs.append(df)
        running += df
    # Short end: anchor 1-month and 3-month bills so the first half-year is not flat.
    short_t = [t for t in par.tenors if t < 0.5]
    short_df = [1.0 / (1.0 + float(par.par_at(t)) * t) for t in short_t]
    knots = np.concatenate([[0.0], short_t, grid])
    log_df = np.concatenate([[0.0], np.log(short_df), np.log(dfs)])
    return ZeroCurve(par.date, knots, log_df)


def pv_par_as_zero(par: ParCurve, flows: list[tuple[float, float]]) -> float:
    """Discount each flow at the *par* yield for its maturity, annually compounded.

    This is the shortcut used in the former CS team's guide (Step 4, Version B). It is kept
    only so their figures can be reproduced; `bootstrap` is the correct method.
    """
    return float(sum(cf / (1.0 + float(par.par_at(t))) ** t for t, cf in flows))

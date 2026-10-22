"""Instruments allowed for the operating reserve under WInS rules.

- `TreasuryBond`: an individual Treasury note or bond (semiannual coupons).
- `TermFund`: an iShares iBonds term Treasury ETF. It holds Treasuries maturing in one
  calendar year and liquidates around December 15 of that year. We model it as a single
  payment at termination that grows at its yield less the expense ratio. Monthly income
  distributions are assumed reinvested in the fund (the fund's total return).
TIPS and STRIPS are not permitted, so they are not modelled.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from .curve import ZeroCurve
from .dates import add_months, as_date, year_frac


@dataclass(frozen=True)
class TreasuryBond:
    cusip: str
    coupon: float          # decimal, e.g. 0.05
    maturity: dt.date
    label: str = ""

    def coupon_dates(self, after: dt.date) -> list[dt.date]:
        """Each date counts back from maturity in whole half-years, so month-end maturities keep their
        day (Aug 31 -> Feb 28 -> Aug 31, not Aug 28)."""
        out, k = [], 0
        while (d := add_months(self.maturity, -6 * k)) > after:
            out.append(d)
            k += 1
        return sorted(out)

    def cashflows(self, settle: dt.date | str) -> list[tuple[dt.date, float]]:
        """Cash flows per 100 face strictly after `settle`."""
        settle = as_date(settle)
        flows = [(d, 100 * self.coupon / 2) for d in self.coupon_dates(settle)]
        flows[-1] = (flows[-1][0], flows[-1][1] + 100.0)
        return flows

    def accrued(self, settle: dt.date | str) -> float:
        settle = as_date(settle)
        nxt = self.coupon_dates(settle)[0]
        prev = add_months(nxt, -6)
        return 100 * self.coupon / 2 * (settle - prev).days / (nxt - prev).days

    def dirty_price(self, curve: ZeroCurve) -> float:
        return float(sum(cf * curve.df(year_frac(curve.date, d)) for d, cf in self.cashflows(curve.date)))

    def clean_price(self, curve: ZeroCurve) -> float:
        return self.dirty_price(curve) - self.accrued(curve.date)

    def ytm(self, dirty: float, settle: dt.date | str) -> float:
        """Semiannual bond-equivalent yield for a dirty price."""
        flows = self.cashflows(settle)
        ts = np.array([year_frac(settle, d) for d, _ in flows])
        cfs = np.array([cf for _, cf in flows])
        f = lambda y: float(np.sum(cfs / (1 + y / 2) ** (2 * ts))) - dirty
        return brentq(f, -0.05, 0.5)

    def mod_duration(self, curve: ZeroCurve) -> float:
        p0 = self.dirty_price(curve)
        up, dn = self.dirty_price(curve.shifted(1)), self.dirty_price(curve.shifted(-1))
        return (dn - up) / (2 * p0 * 1e-4)


@dataclass(frozen=True)
class TermFund:
    ticker: str
    termination: dt.date
    expense_ratio: float = 0.0007
    ytm: float | None = None   # fund-reported yield (annual); None = price off the curve

    def growth_factor(self, curve: ZeroCurve) -> float:
        """Value at termination of $1 invested on the curve date."""
        t = year_frac(curve.date, self.termination)
        y = float(curve.zero(t)) if self.ytm is None else self.ytm
        return (1 + y - self.expense_ratio) ** t

    def cashflows(self, settle: dt.date | str, curve: ZeroCurve) -> list[tuple[dt.date, float]]:
        return [(self.termination, self.growth_factor(curve))]


IBONDS_TREASURY = {  # ticker: termination year (iShares iBonds Dec 20XX Term Treasury ETFs)
    "IBTK": 2030, "IBTL": 2031, "IBTM": 2032, "IBTO": 2033, "IBTP": 2034, "IBTQ": 2035, "IBTR": 2036,
}


def ibonds_fund(ticker: str, expense_ratio: float = 0.0007, ytm: float | None = None) -> TermFund:
    return TermFund(ticker, dt.date(IBONDS_TREASURY[ticker], 12, 15), expense_ratio, ytm)


PLANS_V2_BONDS = [  # verified on TreasuryDirect, Oct 21, 2026. NB: 912810PU6 is NOT listed in WInS.
    TreasuryBond("912810PU6", 0.05000, dt.date(2037, 5, 15), "UST 5.000% May-2037"),
    TreasuryBond("912810PX0", 0.04500, dt.date(2038, 5, 15), "UST 4.500% May-2038"),
    TreasuryBond("912810QD3", 0.04375, dt.date(2039, 11, 15), "UST 4.375% Nov-2039"),
    TreasuryBond("912810QL5", 0.04250, dt.date(2040, 11, 15), "UST 4.250% Nov-2040"),
    TreasuryBond("912810QT8", 0.03125, dt.date(2041, 11, 15), "UST 3.125% Nov-2041"),
]


def wins_treasury_bonds(min_year: int = 2032, max_year: int = 2042) -> list[TreasuryBond]:
    """US Treasury bonds listed in WInS (data/wins/treasury_bonds.csv, read Oct 21, 2026)."""
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "wins" / "treasury_bonds.csv"
    out = []
    with open(path) as f:
        for r in csv.DictReader(f):
            mat = dt.date.fromisoformat(r["maturity"])
            if min_year <= mat.year <= max_year:
                c = float(r["coupon_pct"])
                out.append(TreasuryBond(r["wins_symbol"], c / 100, mat, f"T-BOND {c:.3f}% {mat:%b-%Y}"))
    return out

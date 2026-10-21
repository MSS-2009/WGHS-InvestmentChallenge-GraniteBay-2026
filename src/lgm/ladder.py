"""Cash-flow-matched operating reserve (dedicated bond portfolio) as a linear program.

Choose holdings x_j >= 0 to minimise cost sum_j p_j x_j such that every payment is met.
Cash received before a payment (coupons, maturities, fund terminations) is reinvested at a
conservative rate r until that payment; any surplus after a payment rolls to the next one:

    s_k = s_{k-1} * (1+r)^(T_k - T_{k-1}) + sum_j A_kj x_j - L_k,   s_k >= 0

where A_kj is instrument j's cash arriving in (T_{k-1}, T_k], grown at r to T_k.
Solved with HiGHS (scipy.optimize.linprog). Only WInS-permitted instruments are used.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog

from .curve import ZeroCurve
from .dates import as_date, year_frac
from .instruments import TermFund, TreasuryBond


@dataclass
class LadderResult:
    cost: float
    holdings: dict[str, float]          # label -> dollars invested
    units: dict[str, float]             # label -> face (bonds) or dollars (funds)
    surplus: list[float] = field(default_factory=list)
    status: str = ""


def payment_schedule(first: str = "2033-01-01", n: int = 10, amount: float = 50_000.0) -> list[tuple[dt.date, float]]:
    d0 = as_date(first)
    return [(dt.date(d0.year + k, d0.month, d0.day), amount) for k in range(n)]


def _flows(inst, curve: ZeroCurve, settle: dt.date):
    if isinstance(inst, TreasuryBond):
        return inst.cashflows(settle), inst.dirty_price(curve) / 100.0, inst.label or inst.cusip, 100.0
    if isinstance(inst, TermFund):
        return inst.cashflows(settle, curve), 1.0, inst.ticker, 1.0
    raise TypeError(inst)


def build_matrix(instruments, payments, curve: ZeroCurve, reinvest: float):
    settle = curve.date
    pay_dates = [as_date(d) for d, _ in payments]
    A = np.zeros((len(payments), len(instruments)))
    prices, labels, scale = [], [], []
    for j, inst in enumerate(instruments):
        flows, price, label, unit = _flows(inst, curve, settle)
        prices.append(price)
        labels.append(label)
        scale.append(unit)
        for d, cf in flows:
            k = next((i for i, pd in enumerate(pay_dates) if d <= pd), None)
            if k is None:
                continue  # arrives after the last payment: no credit (conservative)
            A[k, j] += (cf / unit) * (1 + reinvest) ** year_frac(d, pay_dates[k])
    return A, np.array(prices), labels, scale


def solve(instruments, payments, curve: ZeroCurve, reinvest: float = 0.03,
          fixed: dict[str, float] | None = None, minimum: dict[str, float] | None = None) -> LadderResult:
    """Cheapest cash-flow-matched portfolio. `fixed` pins dollar amounts by label; `minimum`
    sets dollar floors (e.g. to force one rung per payment for a simpler ladder)."""
    A, p, labels, _ = build_matrix(instruments, payments, curve, reinvest)
    K, J = A.shape
    L = np.array([a for _, a in payments])
    pay_dates = [as_date(d) for d, _ in payments]
    g = [0.0] + [(1 + reinvest) ** year_frac(pay_dates[k - 1], pay_dates[k]) for k in range(1, K)]
    # variables: x (J) dollars-of-price units, s (K) surplus
    c = np.concatenate([p, np.zeros(K)])
    Aeq = np.zeros((K, J + K))
    for k in range(K):
        Aeq[k, :J] = A[k]
        Aeq[k, J + k] = -1.0
        if k > 0:
            Aeq[k, J + k - 1] = g[k]
    bounds = [(0, None)] * (J + K)
    if fixed:
        for j, lab in enumerate(labels):
            if lab in fixed:
                units = fixed[lab] / p[j]
                bounds[j] = (units, units)
    if minimum:
        for j, lab in enumerate(labels):
            if lab in minimum:
                bounds[j] = (minimum[lab] / p[j], None)
    res = linprog(c, A_eq=Aeq, b_eq=L, bounds=bounds, method="highs")
    if not res.success:
        return LadderResult(float("nan"), {}, {}, [], res.message)
    x = res.x[:J]
    hold = {lab: float(xj * pj) for lab, xj, pj in zip(labels, x, p) if xj * pj > 0.5}
    units = {lab: float(xj) for lab, xj in zip(labels, x) if xj > 1e-9}   # bonds: face $; funds: $
    return LadderResult(float(res.fun), hold, units, list(res.x[J:]), "optimal")


def check_coverage(instruments, dollars: dict[str, float], payments, curve: ZeroCurve, reinvest: float = 0.03):
    """Given fixed dollar holdings, return the surplus after each payment (negative = shortfall)."""
    A, p, labels, _ = build_matrix(instruments, payments, curve, reinvest)
    x = np.array([dollars.get(lab, 0.0) / pj for lab, pj in zip(labels, p)])
    pay_dates = [as_date(d) for d, _ in payments]
    s, out = 0.0, []
    for k, (_, amt) in enumerate(payments):
        if k > 0:
            s *= (1 + reinvest) ** year_frac(pay_dates[k - 1], pay_dates[k])
        s += float(A[k] @ x) - amt
        out.append(s)
    return out


def zero_coupon_cost(curve: ZeroCurve, payments, as_of: dt.date | str | None = None) -> float:
    """Value of the payments on the zero curve. `as_of` re-bases times (guide convention)."""
    base = as_date(as_of) if as_of else curve.date
    return float(sum(a * curve.df(year_frac(base, d)) for d, a in payments))

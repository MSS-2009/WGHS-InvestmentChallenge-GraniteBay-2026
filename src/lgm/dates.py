"""Date helpers. All year fractions use ACT/365.25, which is accurate to well under a basis
point over the horizons in this model and keeps every calculation reproducible by hand."""
from __future__ import annotations

import datetime as dt

DAYS_PER_YEAR = 365.25


def as_date(x: dt.date | str) -> dt.date:
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x))


def year_frac(start: dt.date | str, end: dt.date | str) -> float:
    return (as_date(end) - as_date(start)).days / DAYS_PER_YEAR


def add_months(d: dt.date, months: int) -> dt.date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(y, m, day)

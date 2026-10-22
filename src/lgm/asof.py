"""Run dates from config/asof.yaml, and the engine's month timeline derived from them.

Month 0 is the first day of the month after the curve date (Nov 1, 2026 for an Oct 20 curve), so a
refreshed curve moves every event to the right month without editing the engine.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parents[2] / "config" / "asof.yaml"
_cfg = yaml.safe_load(CFG.read_text())

CURVE_DATE: str = str(_cfg["curve_date"])
DATA_END: str = str(_cfg["data_end"])
PRICE_DATE: str = str(_cfg["price_date"])

_curve = dt.date.fromisoformat(CURVE_DATE)
if _curve >= dt.date(2027, 1, 1):
    raise ValueError(f"curve_date {CURVE_DATE} is on or after the first deposit (Jan 1, 2027)")
START = dt.date(_curve.year + _curve.month // 12, _curve.month % 12 + 1, 1)


def month_of(year: int, month: int = 1) -> int:
    """Engine month index of the first day of (year, month)."""
    return (year - START.year) * 12 + month - START.month

"""ETF core universe: one fund per group, all listed in WInS (checked Oct 21, 2026).

`history` is the ticker used for return history when the traded fund is young (same index
family, longer record). Expense ratios are from the fund sponsors' pages.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    key: str
    name: str
    etf: str
    history: str
    expense_ratio: float
    region: str          # look-through bucket in ACWI holdings
    style: str = ""      # US style for look-through (growth/value/small)


CORE = [
    Group("us_growth", "US large-cap growth", "VUG", "VUG", 0.0004, "US", "growth"),
    Group("us_value", "US large-cap value", "VTV", "VTV", 0.0004, "US", "value"),
    Group("us_small", "US small-cap", "VB", "VB", 0.0005, "US", "small"),
    Group("europe", "Developed Europe", "VGK", "VGK", 0.0006, "Europe"),
    Group("japan", "Japan", "BBJP", "EWJ", 0.0019, "Japan"),
    Group("pacific", "Pacific ex-Japan", "EPP", "EPP", 0.0047, "PacificXJ"),
    Group("canada", "Canada", "BBCA", "EWC", 0.0019, "Canada"),
    Group("em_xchina", "Emerging markets ex-China", "EMXC", "EMXC", 0.0025, "EMxChina"),
    Group("china", "China", "MCHI", "MCHI", 0.0059, "China"),
]
BOND = Group("treasury_2032", "Treasuries maturing Dec 2032", "IBTM", "IBTM", 0.0007, "Bonds")

# Baseline sleeve in the exemplar IPS: VTI / VEA / VWO = 60 / 30 / 10 of equities.
BASELINE_FUNDS = {"US": 0.60, "DEV": 0.30, "EM": 0.10}

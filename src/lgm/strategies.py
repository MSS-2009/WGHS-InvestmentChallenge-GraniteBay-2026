"""Strategy rules. Each strategy is data, so new ones can be tested without new code.

Lock targets are the fraction of *every* payment that is cash-flow matched after that date.
If money runs short, the longest payments are locked first: they carry the most interest-rate
risk, so they are the most expensive to leave open.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Strategy:
    name: str
    lock_2027: float = 0.0
    lock_2028: float = 0.0
    lock_2031: float = 0.0
    equity_share: float = 0.6           # of the growth (non-reserve, non-floor) assets
    bond_vehicle: str = "VGIT"          # "VGIT" (constant maturity) or "IBTM" (matures Dec 2032)
    region_weights: tuple = (0.6, 0.3, 0.1)
    band: float = 0.05                  # rebalance when equity share drifts more than this
    floor_share_2031: float = 0.0       # share of growth assets moved into IBTM in Jan 2031
    contribution_share: float = 1.0     # share of the facility fund committed in Jan 2033
    note: str = ""


# The former CS team's five plans (Plans v2), as their rules describe them.
S1 = Strategy("S1 Index-first, all equity", equity_share=1.0, note="Plans v2 P1")
S2 = Strategy("S2 Index-first, static 60/40", equity_share=0.6, note="Plans v2 P2")
S8 = Strategy("S8 Hybrid, half-hedged", lock_2027=0.5, lock_2028=0.75, lock_2031=1.0,
              equity_share=0.8, floor_share_2031=0.6, note="Plans v2 P3")
S6 = Strategy("S6 Bond-first, equity surplus", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
              equity_share=1.0, note="Plans v2 P4")
S9 = Strategy("S9 Bond-first, 60/40 surplus, 60% floor", lock_2027=1.0, lock_2028=1.0, lock_2031=1.0,
              equity_share=0.6, floor_share_2031=0.6, note="Plans v2 P5")
# This IPS: S9 with the growth sleeve's bonds in IBTM (matures with the facility date)
# and 85% of the facility fund committed, 15% kept for flexibility.
IPS = replace(S9, name="IPS: lock, 60/40 with IBTM, 60% floor, 85% contribution",
              bond_vehicle="IBTM", contribution_share=0.85, note="Exemplar IPS")

PLANS_V2 = [S1, S2, S8, S6, S9]

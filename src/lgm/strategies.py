"""Strategy rules. Each strategy is data, so new ones can be tested without new code.

Lock targets are the fraction of *every* payment that is cash-flow matched after that date.
If money runs short, the longest payments are locked first: they carry the most interest-rate
risk, so they are the most expensive to leave open.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import fsum, isclose, isfinite
from numbers import Integral, Real


def _value_text(value) -> str:
    try:
        return repr(value)
    except (ValueError, OverflowError):
        return f"<{type(value).__name__}>"


def _fraction(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite fraction in [0, 1], got {_value_text(value)}")
    try:
        x = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite fraction in [0, 1], got {_value_text(value)}") from exc
    if not isfinite(x) or not 0.0 <= x <= 1.0:
        raise ValueError(f"{name} must be a finite fraction in [0, 1], got {_value_text(value)}")


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
    # Dynamic rules (opt-in; defaults reproduce legacy behavior exactly)
    equity_share_end: float | None = None
    floor_year: int = 2031
    floor_share: float | None = None
    ratchet_trigger: float | None = None
    ratchet_share: float = 0.0

    def __post_init__(self) -> None:
        for name in ("lock_2027", "lock_2028", "lock_2031", "equity_share", "band",
                     "floor_share_2031", "contribution_share", "ratchet_share"):
            _fraction(name, getattr(self, name))
        for name in ("equity_share_end", "floor_share"):
            value = getattr(self, name)
            if value is not None:
                _fraction(name, value)

        try:
            raw_weights = tuple(self.region_weights)
        except TypeError as exc:
            raise ValueError("region_weights must be a nonempty finite nonnegative vector summing to one") from exc
        if not raw_weights or any(isinstance(w, bool) or not isinstance(w, Real) for w in raw_weights):
            raise ValueError("region_weights must be a nonempty finite nonnegative vector summing to one")
        try:
            weights = tuple(float(w) for w in raw_weights)
            total = fsum(weights)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("region_weights must be a nonempty finite nonnegative vector summing to one") from exc
        if (not all(isfinite(w) and w >= 0.0 for w in weights)
                or not isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-8)):
            raise ValueError("region_weights must be a nonempty finite nonnegative vector summing to one")
        object.__setattr__(self, "region_weights", tuple(w / total for w in weights))

        if not isinstance(self.bond_vehicle, str) or self.bond_vehicle not in {"VGIT", "IBTM"}:
            raise ValueError(f"bond_vehicle must be 'VGIT' or 'IBTM', got {_value_text(self.bond_vehicle)}")
        if (isinstance(self.floor_year, bool) or not isinstance(self.floor_year, Integral)
                or self.floor_year not in (2029, 2030, 2031, 2032)):
            raise ValueError("floor_year must be one of 2029, 2030, 2031, or 2032")
        if self.ratchet_trigger is not None:
            try:
                trigger = float(self.ratchet_trigger)
            except (OverflowError, TypeError, ValueError) as exc:
                raise ValueError("ratchet_trigger must be a finite nonnegative value") from exc
            if (isinstance(self.ratchet_trigger, bool) or not isinstance(self.ratchet_trigger, Real)
                    or not isfinite(trigger) or trigger < 0):
                raise ValueError("ratchet_trigger must be a finite nonnegative value")

    @property
    def effective_floor_share(self) -> float:
        return self.floor_share if self.floor_share is not None else self.floor_share_2031


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

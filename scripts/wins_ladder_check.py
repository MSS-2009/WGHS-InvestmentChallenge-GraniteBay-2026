"""Matching test for the reserve ladder actually held in WInS (Trading Notes, Grader notes).

Usage: python scripts/wins_ladder_check.py
Holdings are the October 21, 2026 fills; payments are at the IPS's two-thirds WInS scale.
"""
import numpy as np

from lgm.curve import bootstrap
from lgm.data.treasury import par_curve
from lgm.instruments import ibonds_fund, wins_treasury_bonds
from lgm.ladder import build_matrix, payment_schedule

SCALE = 2 / 3
BONDS = {"T-BOND 4.750% Feb-2037": 28_000, "T-BOND 4.500% May-2038": 29_000, "T-BOND 4.375% Nov-2039": 30_000,
         "T-BOND 4.250% Nov-2040": 31_000, "T-BOND 3.125% Nov-2041": 33_000}          # face value
FUNDS = {"IBTO": 604 * 23.20, "IBTP": 752 * 24.32, "IBTQ": 726 * 23.94, "IBTR": 695 * 23.75}   # dollars


def main(reinvest: float = 0.03):
    zc = bootstrap(par_curve("2026-10-20"))
    by_label = {b.label: b for b in wins_treasury_bonds(2036, 2042)}
    inst = [by_label[k] for k in BONDS] + [ibonds_fund(t) for t in FUNDS]
    x = np.array(list(BONDS.values()) + list(FUNDS.values()))
    pays = payment_schedule(amount=50_000 * SCALE)
    A, _, _, _ = build_matrix(inst, pays, zc, reinvest)
    cash, s = A @ x, 0.0
    print(f"{'payment':>8} {'cash arriving':>14} {'surplus after':>14}")
    for k, (d, amt) in enumerate(pays):
        s = s * (1 + reinvest) + cash[k] - amt
        print(f"{d.year:>8} {cash[k]:>14,.0f} {s:>14,.0f}")
    print("every payment covered" if s >= 0 else "SHORTFALL")


if __name__ == "__main__":
    main()

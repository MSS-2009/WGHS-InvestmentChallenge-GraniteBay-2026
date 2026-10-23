"""Matching test for the reserve ladder actually held in WInS (Trading Notes, Grader notes).

Usage: python scripts/wins_ladder_check.py [reinvest_rate]
Holdings are read from config/wins_account.yaml; payments are at the IPS's two-thirds WInS scale.
Cash waiting for a payment earns WInS's interest on cash (0%, config/wins_rules.yaml) unless a rate is
given. Every payment must be met, not just the last one; if one is not, the script prints the cheapest
top-up that fixes it and exits with status 1.
"""
import sys
from pathlib import Path

import numpy as np
import yaml

from lgm.asof import CURVE_DATE
from lgm.curve import bootstrap
from lgm.data.treasury import par_curve
from lgm.instruments import ibonds_fund, wins_treasury_bonds
from lgm.ladder import build_matrix, payment_schedule, solve

CFG = Path(__file__).resolve().parents[1] / "config"


def coverage(reinvest: float, account: dict | None = None):
    """Holdings, payments and the surplus after each payment (negative = shortfall)."""
    acct = (account or yaml.safe_load((CFG / "wins_account.yaml").read_text()))["ladder"]
    zc = bootstrap(par_curve(CURVE_DATE))
    by_label = {b.label: b for b in wins_treasury_bonds(2036, 2042)}
    bonds = [by_label[k] for k in acct["bonds_face"]]
    funds = [ibonds_fund(t) for t in acct["funds"]]
    x = np.array(list(acct["bonds_face"].values()) + [f["shares"] * f["price"] for f in acct["funds"].values()])
    pays = payment_schedule(amount=50_000 * acct["scale"])
    A, prices, labels, _ = build_matrix(bonds + funds, pays, zc, reinvest)
    cash, s, surplus = A @ x, 0.0, []
    for k, (_, amt) in enumerate(pays):
        s = s * (1 + reinvest) + cash[k] - amt
        surplus.append(s)
    return {"instruments": bonds + funds, "labels": labels, "units": x, "prices": prices, "payments": pays,
            "cash": cash, "surplus": surplus, "curve": zc}


def top_up(c: dict, reinvest: float) -> dict[str, float]:
    """Cheapest extra dollars per instrument that make every payment, keeping what is held."""
    held = {lab: u * p for lab, u, p in zip(c["labels"], c["units"], c["prices"])}
    res = solve(c["instruments"], c["payments"], c["curve"], reinvest, minimum=held)
    return {lab: res.holdings.get(lab, 0.0) - held[lab] for lab in held if res.holdings.get(lab, 0.0) - held[lab] > 0.5}


def main(reinvest: float | None = None, account: dict | None = None) -> int:
    if reinvest is None:
        reinvest = float(yaml.safe_load((CFG / "wins_rules.yaml").read_text())["interest_on_cash"])
    account = account or yaml.safe_load((CFG / "wins_account.yaml").read_text())
    c = coverage(reinvest, account)
    print(f"cash waiting for a payment earns {reinvest:.1%}")
    print(f"{'payment':>8} {'cash arriving':>14} {'surplus after':>14}")
    for (d, _), cash, s in zip(c["payments"], c["cash"], c["surplus"]):
        print(f"{d.year:>8} {cash:>14,.0f} {s:>14,.0f}{'  SHORT' if s < -0.005 else ''}")
    short = [d.year for (d, _), s in zip(c["payments"], c["surplus"]) if s < -0.005]
    if not short:
        print("every payment covered")
        return 0
    print(f"SHORTFALL in {', '.join(map(str, short))}; cheapest top-up:")
    funds = account["ladder"]["funds"]
    for lab, extra in top_up(c, reinvest).items():
        n = f" ({int(np.ceil(extra / funds[lab]['price']))} shares)" if lab in funds else ""
        print(f"  add ${extra:,.0f} of {lab}{n}")
    return 1


if __name__ == "__main__":
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else None))

"""Ladder scorecard: every WInS-listed Treasury security scored for the reserve ladder.

Usage: python scripts/ladder_scorecard.py [reinvest_rate]
Writes reports/ladder_scorecard.csv. The ladder is the quantitative model's cheapest cash-flow-matched
portfolio (src/lgm/ladder.py) for the ten payments at the IPS's two-thirds WInS scale, on the Oct 20,
2026 curve, with cash waiting for a payment earning WInS's 0% unless a rate is given.

1. Value per $100 (ladder index): the payment value $100 of the security buys, priced with the
   optimiser's own cost of a dollar on each payment date (the LP's shadow prices). The securities the
   optimiser buys score 100; anything below 100 costs more than the optimal ladder for what it delivers.
2. Saving: how much more the cheapest ladder costs if the security is removed from the universe; the
   team's WInS holdings are ranked by it.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import linprog

from lgm.asof import CURVE_DATE
from lgm.curve import bootstrap
from lgm.data.treasury import par_curve
from lgm.instruments import TermFund, ibonds_fund, wins_treasury_bonds
from lgm.ladder import build_matrix, payment_schedule, solve

ROOT = Path(__file__).resolve().parents[1]
FUNDS = ("IBTL", "IBTM", "IBTO", "IBTP", "IBTQ", "IBTR")   # iBonds Treasury funds listed in WInS (VALIDATION.md)


def label(inst) -> str:
    return inst.ticker if isinstance(inst, TermFund) else inst.label


def shadow_prices(A: np.ndarray, p: np.ndarray, L: np.ndarray) -> tuple[np.ndarray, float]:
    """The ladder LP at 0% carry (as ladder.solve) solved for its duals: today's cost of $1 on each payment date."""
    K, J = A.shape
    Aeq = np.zeros((K, J + K))
    for k in range(K):
        Aeq[k, :J], Aeq[k, J + k] = A[k], -1.0
        if k:
            Aeq[k, J + k - 1] = 1.0
    res = linprog(np.concatenate([p, np.zeros(K)]), A_eq=Aeq, b_eq=L, bounds=[(0, None)] * (J + K), method="highs")
    return res.eqlin.marginals, float(res.fun)


def main(reinvest: float = 0.0):
    acct = yaml.safe_load((ROOT / "config" / "wins_account.yaml").read_text())["ladder"]
    zc = bootstrap(par_curve(CURVE_DATE))
    universe = wins_treasury_bonds(2026, 2048) + [ibonds_fund(t) for t in FUNDS]
    pays = payment_schedule(amount=50_000 * acct["scale"])
    A, p, labels, _ = build_matrix(universe, pays, zc, reinvest)
    if reinvest:
        raise SystemExit("shadow prices are computed for 0% carry only (WInS pays no interest on cash)")
    y, cost = shadow_prices(A, p, np.array([a for _, a in pays]))
    lp = solve(universe, pays, zc, 0.0)
    assert abs(lp.cost - cost) < 1e-6 * cost
    held = {**acct["bonds_face"], **acct["funds"]}
    rows = []
    for j, inst in enumerate(universe):
        lab = labels[j]
        mat = inst.termination if isinstance(inst, TermFund) else inst.maturity
        rows.append({"security": lab, "matures": mat, "value_per_100": 100 * float(y @ A[:, j]) / p[j],
                     "model_dollars": lp.holdings.get(lab, 0.0), "held_in_wins": lab in held})
    df = pd.DataFrame(rows)
    df["value_rank"] = df["value_per_100"].round(2).rank(ascending=False, method="min").astype(int)
    saving = {}
    for lab in df.loc[df["held_in_wins"] | (df["model_dollars"] > 0), "security"]:
        rest = [u for u in universe if label(u) != lab]
        alt = solve(rest, pays, zc, 0.0)
        saving[lab] = alt.cost - lp.cost
    df["saving_if_removed"] = df["security"].map(saving)
    h = df["held_in_wins"]
    df.loc[h, "holding_rank"] = df.loc[h, "saving_if_removed"].rank(ascending=False, method="min")
    df = df.sort_values(["value_per_100", "matures"], ascending=[False, True])
    df.round(4).to_csv(ROOT / "reports" / "ladder_scorecard.csv", index=False)
    print(f"Ladder scorecard: {len(df)} WInS Treasury securities, Oct 20 curve, cash at 0%; "
          f"cheapest ladder ${lp.cost:,.0f} at two-thirds scale")
    print("cost today of $1 on each payment date:", ", ".join(f"{d.year} {v:.4f}" for (d, _), v in zip(pays, y)))
    print(df.head(20).round(2).to_string(index=False))
    print(df[df["held_in_wins"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0)

"""Build the ETF core with Black-Litterman and score it with the Monte Carlo.

Usage: python scripts/build_core.py [n_scenarios]
Writes reports/core_bl.csv (weights and returns) and reports/core_scoring.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params, score
from lgm.growth.universe import CORE

OUT = Path(__file__).resolve().parents[1] / "reports"
BASELINE_FUNDS = ((0, 1, 2), (3, 4, 5, 6), (7, 8))   # VTI, VEA, VWO over the nine CORE groups


def main(n: int = 20_000):
    r = build_core()
    t, w_mkt, w_bl = r["table"], r["w_mkt"], r["w_bl"]
    var, rf = np.diag(r["cov"]), r["cfg"]["cash_long_run"]
    t.round(5).to_csv(OUT / "core_bl.csv", index=False)
    idx = {g.key: i for i, g in enumerate(CORE)}

    def basket(keys, total):
        v = np.zeros(len(CORE))
        s = sum(w_mkt[idx[k]] for k in keys)
        for k in keys:
            v[idx[k]] = total * w_mkt[idx[k]] / s
        return v

    base = basket(["us_growth", "us_value", "us_small"], 0.6) + basket(["europe", "japan", "pacific", "canada"], 0.3) \
        + basket(["em_xchina", "china"], 0.1)
    core_er = np.array([g.expense_ratio for g in CORE])
    base_er = np.array([0.0003] * 7 + [0.0006] * 2)
    weights = {"Baseline VTI/VEA/VWO 60/30/10": base, "Market-cap ETF core": w_mkt, "Black-Litterman ETF core": w_bl}
    ers = {"Baseline VTI/VEA/VWO 60/30/10": base_er, "Market-cap ETF core": core_er, "Black-Litterman ETF core": core_er}
    beliefs = {"Black-Litterman posterior": t["bl_geo_total"].values,
               "Equilibrium (no views)": t["pi_excess"].values + rf - 0.5 * var}
    # The baseline is three funds (VTI, VEA, VWO) spread over the nine groups: 3 tickets, 3 drift checks
    kw = {"Baseline VTI/VEA/VWO 60/30/10": {"fund_groups": BASELINE_FUNDS}}
    rows = []
    for bname, geo in beliefs.items():
        for k, v in score(weights, ers, esg_params(r["cal"], geo), n=n, engine_kw=kw).items():
            rows.append({"beliefs": bname, "sleeve": k, **v})
    df = pd.DataFrame(rows)
    df.round(2).to_csv(OUT / "core_scoring.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(t.round(4).to_string(index=False))
        print(df[["beliefs", "sleeve", "funded", "p5", "median", "p95", "cvar5", "range80_lo", "range80_hi"]].round(0).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

"""Reproduce the former CS team's Plans v2 results with the rebuilt engine.

Usage: python scripts/validate_plans_v2.py [n_scenarios]
Writes reports/plans_v2_validation.csv and plans_v2_rate_stress.json and prints a comparison table.
"""
import dataclasses as dc
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.esg import simulate
from lgm.profiles import cs_team
from lgm.strategies import IPS, PLANS_V2, S9

TARGETS = {  # Plans v2, page 1 and plan pages (facility money in $k)
    "S1": dict(funded=0.868, p5=0.0, median=212.8, p95=759.3, floor=None, r10=None, r90=None),
    "S2": dict(funded=0.964, p5=16.2, median=208.0, p95=508.3, floor=0.0, r10=120.7, r90=332.4),
    "S8": dict(funded=1.000, p5=94.2, median=194.9, p95=355.3, floor=124.3, r10=191.9, r90=230.2),
    "S6": dict(funded=1.000, p5=106.2, median=197.7, p95=365.5, floor=0.0, r10=150.2, r90=261.7),
    "S9": dict(funded=1.000, p5=137.9, median=193.5, p95=273.2, floor=114.6, r10=181.4, r90=208.6),
}


def main(n: int = 20_000):
    p = cs_team()
    sc = simulate(p, n=n, seed=1)
    rows = []
    for st in PLANS_V2 + [IPS]:
        r = engine.run(st, sc, snapshot_2031=True)
        s = engine.summarize(r)
        key = st.name.split()[0][:3].rstrip(":")
        c = engine.conditional_2031(st, sc, r, p) if st.name[:2] != "S1" else None
        t = TARGETS.get(key, {})
        rows.append({"strategy": st.name, "funded": s["funded"], "p5_k": s["p5"] / 1e3, "median_k": s["median"] / 1e3,
                     "p95_k": s["p95"] / 1e3, "floor_2031_k": c["floor"] / 1e3 if c else np.nan,
                     "range80_lo_k": c["p10"] / 1e3 if c else np.nan, "range80_hi_k": c["p90"] / 1e3 if c else np.nan,
                     "v2_funded": t.get("funded"), "v2_p5_k": t.get("p5"), "v2_median_k": t.get("median"),
                     "v2_p95_k": t.get("p95"), "v2_floor_k": t.get("floor"), "v2_r10_k": t.get("r10"), "v2_r90_k": t.get("r90")})
    df = pd.DataFrame(rows)
    out = Path(__file__).resolve().parents[1] / "reports"
    df.round(4).to_csv(out / "plans_v2_validation.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(df.round(1).to_string(index=False))
    stress = rate_stress(p, n)
    (out / "plans_v2_rate_stress.json").write_text(json.dumps(stress, indent=2))
    print(f"S9 median, rates 0.75 pts lower at the lock (Plans v2: $192k -> $159k): "
          f"${stress['base_median'] / 1e3:.1f}k -> ${stress['minus_75bp_median'] / 1e3:.1f}k ({stress['change_pct']:+.0%})")
    return df


def rate_stress(p, n: int) -> dict:
    """S9 with the whole curve 0.75 points lower before the January 2027 lock, permanently (the long-run
    level moves too, matching the model's "rates unchanged on average" expectation)."""
    d = np.array([-0.0075, 0.0, 0.0])
    start = {"beta": np.tile(p.beta0, (n, 1)), "infl": np.full(n, p.infl0), "fx_log": np.zeros(n),
             "tw_cost_log": np.zeros(n), "beta_shift": d}
    base = float(np.median(engine.run(S9, simulate(p, n=n, seed=1))["facility"]))
    low = float(np.median(engine.run(S9, simulate(dc.replace(p, beta_mu=p.beta_mu + d), n=n, seed=1, start=start))["facility"]))
    return {"strategy": S9.name, "base_median": round(base, 1), "minus_75bp_median": round(low, 1),
            "change_pct": round(low / base - 1, 4)}


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

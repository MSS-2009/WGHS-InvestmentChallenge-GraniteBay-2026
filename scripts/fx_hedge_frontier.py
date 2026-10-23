"""How much of the Taiwan-dollar risk to hedge: a frontier for the client's decision.

Usage: python scripts/fx_hedge_frontier.py [n_scenarios]
Headline scenarios and the IPS, under two beliefs about USD/TWD: the headline's random walk (no drift;
the forward is a biased forecast, docs/loop/r4_fx_findings.md) and the forward as an unbiased forecast
(spot drifts at the forward premium). In January 2027 a share h of the expected facility
(h x the median facility, in USD) is sold forward for Taiwan dollars, delivered in January 2033, at
today's actual forward premium (CBC 180-day, -2.28% a year, from reports/fx_forward_check.csv; rolling
six-month forwards cost the same premium in expectation). Taiwan-dollar proceeds:
facility x S_2033 + N x (F - S_2033), measured in January 2027 building costs like the headline's
real values. A fixed notional over-hedges in the scenarios where the facility comes in below it; the
table shows what that does to the tail. Writes reports/fx_hedge_frontier.csv.
"""
import dataclasses as dc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "fx_hedge_frontier.csv"
YEARS = (engine.M_2033 - engine.M_2027) / 12


def main(n: int = 20_000, seed: int = 11):
    fwd = float(pd.read_csv(ROOT / "reports" / "fx_forward_check.csv").set_index("check")
                .loc["cip_vs_forward", "latest_forward_premium"])
    r = build_core()
    st = dc.replace(IPS, region_weights=tuple(r["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    base = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
    f_ratio = np.exp(fwd * YEARS)                                                      # F / S_2027
    rows = []
    for belief, drift in (("random walk (headline)", 0.0), ("forward unbiased", fwd)):
        sc = simulate(dc.replace(base, fx_drift=drift), n=n, seed=seed)
        fac = engine.run(st, sc, cfg)["facility"]
        s_ratio = np.exp(sc.fx_log[:, engine.M_2033] - sc.fx_log[:, engine.M_2027])     # S_2033 / S_2027
        cost = np.exp(sc.tw_cost_log[:, engine.M_2033] - sc.tw_cost_log[:, engine.M_2027])
        notional0 = float(np.median(fac))
        for h in (0.0, 0.25, 0.5, 0.75, 1.0):
            twd = fac * s_ratio + h * notional0 * (f_ratio - s_ratio)                     # in units of S_2027 TWD
            real = twd / cost
            rows.append({"belief": belief, "hedge_ratio": h, "notional_usd": h * notional0, "forward_premium": fwd,
                         "real_p5": float(np.percentile(real, 5)), "real_p25": float(np.percentile(real, 25)),
                         "real_median": float(np.median(real)), "real_p75": float(np.percentile(real, 75)),
                         "real_p95": float(np.percentile(real, 95)), "real_sd": float(real.std()),
                         "prob_real_below_120k": float((real < 120_000).mean())})
            x = rows[-1]
            print(f"{belief:22s} hedge {h:4.0%}: real p5 ${x['real_p5']:,.0f}  median ${x['real_median']:,.0f}  p95 ${x['real_p95']:,.0f}  "
                  f"sd ${x['real_sd']:,.0f}  P(<$120k) {x['prob_real_below_120k']:.1%}")
    pd.DataFrame(rows).round(4).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

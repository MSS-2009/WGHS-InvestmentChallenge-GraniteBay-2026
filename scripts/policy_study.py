"""Test the plan's judgment calls instead of asserting them.

Usage: python scripts/policy_study.py [n_scenarios]
1. Floor frontier: the share of the growth sleeve moved into IBTM in January 2031 (the IPS uses 60%),
   scored by percentiles, the 2031 quote, and certainty equivalents for a range of risk aversion.
2. Contribution share: what 75-95% of the facility fund means for the contribution and what Laura keeps.
3. Range calibration on history: on every real six-year path since 2005, quote the 80% range from
   that path's own January 2031 position, then check where its January 2033 result actually landed.
4. Reverse stress test: what the worst futures have in common.
Writes reports/policy_study.json.
"""
import dataclasses as dc
import json
import sys
from pathlib import Path

import numpy as np

from lgm import engine
from lgm.backtest import history_paths
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports"
FLOORS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
GAMMAS = (2, 4, 8)


def certainty_equivalent(x: np.ndarray, gamma: float) -> float:
    x = np.maximum(x, 1.0)
    return float(np.mean(x ** (1 - gamma)) ** (1 / (1 - gamma)))


def main(n: int = 20_000):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=n, seed=11)
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    base = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    out = {"n_scenarios": n}

    # 1. Floor frontier
    frontier = []
    for f in FLOORS:
        st = dc.replace(base, floor_share_2031=f)
        r = engine.run(st, sc, cfg, snapshot_2031=True)
        fac = r["facility"]
        typical = int(np.argsort(r["growth_2031"])[int(0.5 * (n - 1))])     # same world as report_numbers.py
        c = engine.conditional_2031(st, sc, r, p, i=typical, n_inner=3000, cfg=cfg)
        frontier.append({"floor_share": f, "median": round(float(np.median(fac))), "p5": round(float(np.percentile(fac, 5))),
                         "p95": round(float(np.percentile(fac, 95))),
                         "secured_2031_typical": round(0.85 * c["floor"]),
                         "range_2031_typical": [round(0.85 * c["p10"], -2), round(0.85 * c["p90"], -2)],
                         **{f"ce_gamma{g}": round(certainty_equivalent(fac, g)) for g in GAMMAS}})
    out["floor_frontier"] = frontier
    out["best_floor_by_gamma"] = {g: max(frontier, key=lambda row: row[f"ce_gamma{g}"])["floor_share"] for g in GAMMAS}

    # 2. Contribution share
    r = engine.run(base, sc, cfg)
    fac = r["facility"]
    out["contribution_share"] = [{"share": c, "contribution_median": round(c * float(np.median(fac))),
                                  "contribution_p5": round(c * float(np.percentile(fac, 5))),
                                  "kept_median": round((1 - c) * float(np.median(fac))),
                                  "kept_p5": round((1 - c) * float(np.percentile(fac, 5)))} for c in (0.75, 0.85, 0.95)]

    # 3. Range calibration on real history (returns re-centred on the model's expectations, and as they happened)
    calib = {}
    for label, rec in (("recentred", core["table"]["bl_geo_total"].values), ("as_happened", None)):
        hs, starts = history_paths([g.history for g in CORE], recentre=rec)
        hr = engine.run(base, hs, cfg, snapshot_2031=True)
        inside = below = above = 0
        for i in range(hs.n):
            c = engine.conditional_2031(base, hs, hr, p, i=i, n_inner=1500, cfg=cfg)
            real = float(hr["facility"][i])
            below += real < c["p10"]
            above += real > c["p90"]
            inside += c["p10"] <= real <= c["p90"]
        calib[label] = {"paths": hs.n, "inside_80pct_range": round(inside / hs.n, 3), "below_range": round(below / hs.n, 3),
                        "above_range": round(above / hs.n, 3), "first_start": str(starts[0].date()), "last_start": str(starts[-1].date())}
    out["range_calibration_history"] = calib

    # 4. Reverse stress test: what the worst 1% and 5% of futures have in common
    w = np.asarray(core["w_bl"])
    log_eq = (sc.eq_log[:, engine.M_2028:engine.M_2033, :] * w).sum(2)          # weight-averaged log return a month
    cum_eq = np.expm1(log_eq.sum(1))
    worst_year = np.array([np.expm1(np.convolve(row, np.ones(12), "valid")).min() for row in log_eq])
    y5 = lambda m: np.expm1(sc.zero_cc(m, [5.0])[:, 0])
    d5_2031, d5_2033 = y5(engine.M_2031) - y5(0), y5(engine.M_2033) - y5(0)
    stress = {}
    for label, q in (("worst_1pct", 1), ("worst_5pct", 5), ("all", 100)):
        sel = fac <= np.percentile(fac, q)
        stress[label] = {"facility_mean": round(float(fac[sel].mean())), "stocks_cum_return_2028_2033": round(float(cum_eq[sel].mean()), 3),
                         "worst_12_months": round(float(worst_year[sel].mean()), 3),
                         "five_year_yield_change_by_2031": round(float(d5_2031[sel].mean()), 4),
                         "five_year_yield_change_by_2033": round(float(d5_2033[sel].mean()), 4)}
    stress["prob_facility_below"] = {k: round(float((fac < k).mean()), 4) for k in (100_000, 120_000, 140_000)}
    out["reverse_stress"] = stress
    (OUT / "policy_study.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

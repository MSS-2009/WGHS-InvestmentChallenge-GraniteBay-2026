"""Compare operating reserve costs and facility outcomes across bond universes and reinvestment rates.

Usage: python scripts/strips_reserve.py [n_scenarios]
Writes reports/strips_reserve.csv.
"""
from __future__ import annotations

import csv
import dataclasses as dc
import json
import sys
from pathlib import Path

import numpy as np

from lgm import engine, ladder
from lgm.asof import CURVE_DATE
from lgm.curve import bootstrap
from lgm.data.strips import (
    strips_plus_december_universe,
    strips_universe,
)
from lgm.data.treasury import par_curve
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def main(n: int = 20_000):
    # 1. Curve and zero-coupon baseline
    zc = bootstrap(par_curve(CURVE_DATE))
    pays = ladder.payment_schedule()
    zc_cost = ladder.zero_coupon_cost(zc, pays)

    # 2. Monte Carlo environment (matching scripts/report_numbers.py)
    r = build_core()
    t, w = r["table"], r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    beliefs = t["bl_geo_total"].values
    p = esg_params(r["cal"], beliefs)
    sc = simulate(p, n=n, seed=11)
    st = dc.replace(IPS, region_weights=tuple(w))
    cfg_base = engine.EngineConfig(eq_er=tuple(er))

    # Baseline run (default kappa0 = 0.018, corresponding to WInS ladder at ~3%)
    res_base = engine.run(st, sc, cfg_base)
    base_median = float(np.median(res_base["facility"]))

    # WInS ladder at 0% benchmark
    k_wins_0 = ladder.premium(zc, 0.0)
    res_wins_0 = engine.run(st, sc, dc.replace(cfg_base, kappa0=k_wins_0))
    wins_0_median = float(np.median(res_wins_0["facility"]))

    universes = [
        ("STRIPS (market quotes)", strips_universe(use_market_quotes=True)),
        ("STRIPS (ask quotes)", strips_universe(use_market_quotes=True, side="ask")),
        ("STRIPS (curve implied)", strips_universe(use_market_quotes=False)),
        ("STRIPS + Dec Note (market quotes)", strips_plus_december_universe(use_market_quotes=True)),
        ("STRIPS + Dec Note (ask quotes)", strips_plus_december_universe(use_market_quotes=True, side="ask")),
        ("STRIPS + Dec Note (curve implied)", strips_plus_december_universe(use_market_quotes=False)),
        ("WInS universe", ladder.wins_reserve_universe()),
    ]

    rows = []
    print(f"Zero-coupon value of 10 Jan 1 payments: ${zc_cost:,.2f}")
    print(f"Baseline (WInS ladder at ~3% reinvestment): median facility = ${base_median:,.1f}")
    print(f"WInS ladder at 0% reinvestment: median facility = ${wins_0_median:,.1f} (change = ${wins_0_median - base_median:+,.1f})\n")

    header = f"{'Universe':<36} {'Reinvest':<9} {'Cost ($)':<12} {'Prem (%)':<9} {'Idle Days':<10} {'Median Fac ($)':<15} {'vs WInS 3%':<12} {'vs WInS 0%':<12}"
    print(header)
    print("-" * len(header))

    for uname, u in universes:
        for r_rate in (0.00, 0.03):
            lp = ladder.solve(u, pays, zc, reinvest=r_rate)
            k0 = lp.cost / zc_cost - 1.0
            idle = ladder.idle_cash_days(u, lp.units, pays, zc, reinvest=r_rate)
            rr = engine.run(st, sc, dc.replace(cfg_base, kappa0=k0))
            med = float(np.median(rr["facility"]))
            diff_wins_3 = med - base_median
            diff_wins_0 = med - wins_0_median

            row = {
                "universe": uname,
                "reinvestment_rate": r_rate,
                "cost": round(lp.cost, 2),
                "zero_coupon_value": round(zc_cost, 2),
                "cost_over_zero": round(lp.cost - zc_cost, 2),
                "premium_kappa0": round(k0, 6),
                "idle_cash_dollar_days": round(idle["total_dollar_days"], 1),
                "idle_cash_weighted_days": round(idle["weighted_avg_days"], 1),
                "median_facility": round(med, 1),
                "median_change_vs_wins_3pct": round(diff_wins_3, 1),
                "median_change_vs_wins_0pct": round(diff_wins_0, 1),
                "holdings_json": json.dumps({k: round(v, 2) for k, v in lp.holdings.items()}),
            }
            rows.append(row)

            print(
                f"{uname:<36} {r_rate*100:>7.1f}% {lp.cost:>12,.2f} {k0*100:>8.3f}% "
                f"{idle['weighted_avg_days']:>9.1f}d {med:>15,.1f} {diff_wins_3:>+11,.1f} {diff_wins_0:>+11,.1f}"
            )

    csv_path = REPORTS_DIR / "strips_reserve.csv"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {csv_path} ({len(rows)} rows).")


if __name__ == "__main__":
    n_scen = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    main(n_scen)

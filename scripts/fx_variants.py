"""What the USD/TWD drift assumption does to the facility in Taiwan building-cost terms.

Usage: python scripts/fx_variants.py [n_scenarios]
Headline parameters exactly as scripts/report_numbers.py builds them (IPS, Black-Litterman core, $25
commissions, one seed), with the Taiwan building-cost process set to the fitted monthly AR(2) from
config/taiwan.yaml (full-sample drift 2.85%, started from the Aug and Sep 2026 readings). In the first four rows only
`fx_drift` (annual log drift of USD/TWD) changes between rows:
  random_walk      0 (today's assumption; the better forecast in scripts/fx_drift_study.py)
  half_forward     half the latest actual 180-day forward premium
  cip_latest       the latest interest differential (TW 90-day CP vs US 3-month)
  forward_latest   the latest actual 180-day forward premium (CBC Table 31.C)
  random_walk_no_cost_fx_corr  as random_walk, with building-cost growth independent of USD/TWD
                   (the headline uses -0.25, scripts/taiwan_fx_corr.py)
  random_walk_tw_drift_10y     as random_walk, with the last ten years' building-cost drift (3.78%)
                   instead of 1991-2026's (2.85%; scripts/taiwan_drift_study.py)
Writes reports/fx_variants.csv.
"""
import dataclasses as dc
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "fx_variants.csv"


def main(n: int = 20_000, seed: int = 11):
    fwd = pd.read_csv(ROOT / "reports" / "fx_forward_check.csv").set_index("check")
    forward_latest = float(fwd.loc["cip_vs_forward", "latest_forward_premium"])
    cip_latest = float(fwd.loc["cip_vs_forward", "latest_cip_drift"])
    tw = yaml.safe_load((ROOT / "config" / "taiwan.yaml").read_text())["fitted_monthly"]

    r = build_core()
    st = dc.replace(IPS, region_weights=tuple(r["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), commissions=True)
    base = dc.replace(esg_params(r["cal"], r["table"]["bl_geo_total"].values),
                      tw_cost_growth=tw["drifts"]["full_sample_35y"], tw_cost_phi=tuple(tw["tw_cost_phi"]),
                      tw_cost_sig_eps=tw["tw_cost_sig_eps"], tw_cost_state0=tuple(tw["tw_cost_state0_today"]))
    variants = {"random_walk": (0.0, {}), "half_forward": (forward_latest / 2, {}), "cip_latest": (cip_latest, {}),
                "forward_latest": (forward_latest, {}), "random_walk_no_cost_fx_corr": (0.0, {"tw_cost_fx_corr": 0.0}),
                "random_walk_tw_drift_10y": (0.0, {"tw_cost_growth": tw["drifts"]["last_10y"]})}
    rows = []
    for name, (drift, kw) in variants.items():
        sc = simulate(dc.replace(base, fx_drift=drift, **kw), n=n, seed=seed)
        res = engine.run(st, sc, cfg)
        real = res["facility_real_tw2027"]
        fx = np.expm1(sc.fx_log[:, engine.M_2033] - sc.fx_log[:, engine.M_2027])
        rows.append({"variant": name, "fx_drift": round(drift, 6),
                     "nominal_median": round(float(np.median(res["facility"])), 1),
                     "real_p5": round(float(np.percentile(real, 5)), 1),
                     "real_median": round(float(np.median(real)), 1),
                     "real_p95": round(float(np.percentile(real, 95)), 1),
                     "usd_twd_change_p5": round(float(np.percentile(fx, 5)), 4),
                     "usd_twd_change_p50": round(float(np.median(fx)), 4),
                     "usd_twd_change_p95": round(float(np.percentile(fx, 95)), 4)})
        x = rows[-1]
        print(f"{name:15s} drift {drift*100:+.2f}%/yr  nominal median ${x['nominal_median']:,.0f}  real median "
              f"${x['real_median']:,.0f} (p5 ${x['real_p5']:,.0f}, p95 ${x['real_p95']:,.0f})  USD/TWD 2027-33 "
              f"{x['usd_twd_change_p50']*100:+.1f}% [{x['usd_twd_change_p5']*100:+.1f}%, {x['usd_twd_change_p95']*100:+.1f}%]")
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

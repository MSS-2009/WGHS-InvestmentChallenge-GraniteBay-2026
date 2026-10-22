"""Evaluate ESG variants: expected-return uncertainty, volatility clustering, both, and scaling.

Compares six variants under IPS strategy with Black-Litterman core and WInS commissions:
1. baseline: i.i.d. Student-t shocks, constant drift
2. drift_unc_0.5x: 0.5x calibrated CMA cross-firm covariance
3. drift_unc: 1.0x calibrated CMA cross-firm covariance
4. drift_unc_2x: 2.0x calibrated CMA cross-firm covariance
5. vol_cluster: GARCH(1,1) volatility clustering calibrated on VTI (2001-2026)
6. both: 1.0x drift uncertainty + GARCH(1,1) volatility clustering

Writes reports/esg_variants.csv.
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from lgm import engine
from lgm.backtest import history_paths
from lgm.calibrate import calibrate_cma_dispersion, calibrate_equity_garch
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"


def basket(w_mkt: np.ndarray, keys: list[str], total: float) -> np.ndarray:
    idx = {g.key: i for i, g in enumerate(CORE)}
    v = np.zeros(len(CORE))
    s = sum(w_mkt[idx[k]] for k in keys)
    for k in keys:
        v[idx[k]] = total * w_mkt[idx[k]] / s
    return v


def run_variants(n: int = 20_000) -> pd.DataFrame:
    core = build_core()
    w = np.asarray(core["w_bl"])
    w_mkt = core["w_mkt"]
    er = tuple(g.expense_ratio for g in CORE)
    cfg = engine.EngineConfig(eq_er=er)
    st = dc.replace(IPS, region_weights=tuple(w))

    base_sleeve = basket(w_mkt, ["us_growth", "us_value", "us_small"], 0.6) + \
                  basket(w_mkt, ["europe", "japan", "pacific", "canada"], 0.3) + \
                  basket(w_mkt, ["em_xchina", "china"], 0.1)

    cma_cov = calibrate_cma_dispersion()
    garch_cal = calibrate_equity_garch()
    garch_params = (garch_cal["alpha"], garch_cal["beta"], 1.0)

    variants = {
        "baseline": {"eq_mu_cov": None, "eq_garch": None},
        "drift_unc_0.5x": {"eq_mu_cov": 0.5 * cma_cov, "eq_garch": None},
        "drift_unc": {"eq_mu_cov": cma_cov, "eq_garch": None},
        "drift_unc_2x": {"eq_mu_cov": 2.0 * cma_cov, "eq_garch": None},
        "vol_cluster": {"eq_mu_cov": None, "eq_garch": garch_params},
        "both": {"eq_mu_cov": cma_cov, "eq_garch": garch_params},
    }

    rows = []
    for name, kwargs in variants.items():
        print(f"Running variant: {name} ...", flush=True)
        p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
        p.eq_mu_cov = kwargs["eq_mu_cov"]
        p.eq_garch = kwargs["eq_garch"]

        sc = simulate(p, n=n, seed=11)
        res = engine.run(st, sc, cfg, snapshot_2031=True)

        f = res["facility"]
        tail = f[f <= np.percentile(f, 5)]

        # 74-month cumulative return percentiles of 60/30/10 sleeve
        r_simple = np.expm1(sc.eq_log) @ base_sleeve
        cum_sleeve = np.prod(1 + r_simple, axis=1) - 1
        s_p5, s_p50, s_p95 = np.percentile(cum_sleeve, [5, 50, 95])

        # 2031 conditional range at median 2031 scenario
        order = np.argsort(res["growth_2031"])
        i_med = int(order[int(0.50 * (len(order) - 1))])
        c = engine.conditional_2031(st, sc, res, p, i=i_med, n_inner=3000, cfg=cfg)
        inner = c["inner"]
        c_p10, c_p90 = np.percentile(inner, [10, 90])
        c_p20, c_p80 = np.percentile(inner, [20, 80])

        # History calibration: 184 historical paths
        hist_stats = {}
        for label, rec in [("recentred", core["table"]["bl_geo_total"].values), ("as_happened", None)]:
            hs, _ = history_paths([g.history for g in CORE], recentre=rec)
            hr = engine.run(st, hs, cfg, snapshot_2031=True)
            u = np.array([float((engine.conditional_2031(st, hs, hr, p, i=i, n_inner=1500, cfg=cfg)["inner"]
                                 <= hr["facility"][i]).mean()) for i in range(hs.n)])
            hist_stats[label] = {
                "cov10_90": float(((u >= 0.10) & (u <= 0.90)).mean()),
                "below10": float((u < 0.10).mean()),
                "cov20_80": float(((u >= 0.20) & (u <= 0.80)).mean()),
                "below20": float((u < 0.20).mean()),
            }

        row = {
            "variant": name,
            "funded_share": float(res["funded"].mean()),
            "facility_p5": float(np.percentile(f, 5)),
            "facility_p10": float(np.percentile(f, 10)),
            "facility_median": float(np.median(f)),
            "facility_p90": float(np.percentile(f, 90)),
            "facility_p95": float(np.percentile(f, 95)),
            "facility_cvar5": float(tail.mean()) if tail.size else 0.0,
            "sleeve_cum_ret_p5": float(s_p5),
            "sleeve_cum_ret_p50": float(s_p50),
            "sleeve_cum_ret_p95": float(s_p95),
            "cond2031_p10": float(c_p10),
            "cond2031_p90": float(c_p90),
            "cond2031_p20": float(c_p20),
            "cond2031_p80": float(c_p80),
            "hist_as_happened_cov10_90": hist_stats["as_happened"]["cov10_90"],
            "hist_as_happened_below10": hist_stats["as_happened"]["below10"],
            "hist_as_happened_cov20_80": hist_stats["as_happened"]["cov20_80"],
            "hist_as_happened_below20": hist_stats["as_happened"]["below20"],
            "hist_recentred_cov10_90": hist_stats["recentred"]["cov10_90"],
            "hist_recentred_below10": hist_stats["recentred"]["below10"],
            "hist_recentred_cov20_80": hist_stats["recentred"]["cov20_80"],
            "hist_recentred_below20": hist_stats["recentred"]["below20"],
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "esg_variants.csv", index=False)
    print(f"Wrote {OUT / 'esg_variants.csv'}")
    return df


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    df = run_variants(n)
    print(df.round(4).to_string(index=False))

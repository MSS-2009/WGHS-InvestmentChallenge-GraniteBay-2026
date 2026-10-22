"""Fair test of GARCH volatility clustering: conditional on the filtered 2031 variance state.

Evaluates 184 historical 6-year paths (both as-happened and re-centred) across three variants:
  (a) baseline (no GARCH, i.i.d. Student-t)
  (b) garch_unconditional (GARCH started from h0 = 1.0)
  (c) garch_filtered (GARCH started from that path's own filtered 2031 variance state)

Reports coverage and band width overall and by tercile of 2031 variance (calm, normal, turbulent).
Also computes headline IPS numbers started from today's filtered state (Sep 2026).

Writes:
  reports/esg_garch_conditional.csv
  reports/esg_garch_headline.csv
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from lgm import engine
from lgm.backtest import history_paths
from lgm.calibrate import calibrate_equity_garch, filter_equity_garch
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


def run_conditional_study(n_inner: int = 1500, n_headline: int = 20_000) -> tuple[pd.DataFrame, pd.DataFrame]:
    core = build_core()
    w = np.asarray(core["w_bl"])
    w_mkt = core["w_mkt"]
    er = tuple(g.expense_ratio for g in CORE)
    cfg = engine.EngineConfig(eq_er=er)
    st = dc.replace(IPS, region_weights=tuple(w))

    gcal = calibrate_equity_garch()
    alpha, beta = gcal["alpha"], gcal["beta"]
    var_uncond = gcal["uncond_vol_ann"] ** 2 / 12.0
    h0_today = gcal["h0_today"]

    p_base = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_garch = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_garch.eq_garch = (alpha, beta, 1.0)

    # -------------------------------------------------------------
    # 1. Historical Path Evaluation (Overall & Terciles)
    # -------------------------------------------------------------
    hist_rows = []

    for history_type, rec in [("recentred", core["table"]["bl_geo_total"].values), ("as_happened", None)]:
        print(f"Evaluating 184 historical paths ({history_type}) ...", flush=True)
        hs, starts = history_paths([g.history for g in CORE], recentre=rec)
        hr = engine.run(st, hs, cfg, snapshot_2031=True)

        mu0 = np.log1p(rec[0]) / 12.0 if rec is not None else float(hs.eq_log[:, :, 0].mean())
        h_all = filter_equity_garch(hs.eq_log[:, :, 0], alpha=alpha, beta=beta, mu=mu0,
                                    var_uncond=var_uncond, h0=1.0)
        h_2031 = h_all[:, engine.M_2031]
        terciles = pd.qcut(h_2031, 3, labels=["calm", "normal", "turbulent"])

        # Attach filtered h to hs so conditional_2031 propagates it via start["garch_h"]
        hs_filt = dc.replace(hs, garch_h=h_all)

        variants = [
            ("baseline", p_base, hs),
            ("garch_unconditional", p_garch, hs),
            ("garch_filtered", p_garch, hs_filt),
        ]

        var_results = {}
        for vname, p_var, hs_obj in variants:
            u_list, w10_list, w20_list = [], [], []
            for i in range(hs.n):
                c = engine.conditional_2031(st, hs_obj, hr, p_var, i=i, n_inner=n_inner, cfg=cfg)
                actual = hr["facility"][i]
                inner = c["inner"]
                u_list.append(float((inner <= actual).mean()))
                w10_list.append(float(np.percentile(inner, 90) - np.percentile(inner, 10)))
                w20_list.append(float(np.percentile(inner, 80) - np.percentile(inner, 20)))

            var_results[vname] = {
                "u": np.array(u_list),
                "w10": np.array(w10_list),
                "w20": np.array(w20_list),
            }

        # Summarize for all paths and per tercile
        subsets = [("all", np.ones(hs.n, dtype=bool))] + [
            (terc, np.asarray(terciles == terc)) for terc in ["calm", "normal", "turbulent"]
        ]

        for subset_name, mask in subsets:
            n_sub = int(mask.sum())
            mean_h = float(h_2031[mask].mean())
            for vname, _, _ in variants:
                u = var_results[vname]["u"][mask]
                w10 = var_results[vname]["w10"][mask]
                w20 = var_results[vname]["w20"][mask]

                cov10 = float(((u >= 0.10) & (u <= 0.90)).mean())
                below10 = float((u < 0.10).mean())
                above90 = float((u > 0.90).mean())
                cov20 = float(((u >= 0.20) & (u <= 0.80)).mean())
                below20 = float((u < 0.20).mean())
                above80 = float((u > 0.80).mean())

                hist_rows.append({
                    "history_type": history_type,
                    "tercile": subset_name,
                    "variant": vname,
                    "n_paths": n_sub,
                    "mean_h_2031": mean_h,
                    "cov_10_90": cov10,
                    "below_10": below10,
                    "above_90": above90,
                    "cov_20_80": cov20,
                    "below_20": below20,
                    "above_80": above80,
                    "mean_width_10_90": float(w10.mean()),
                    "mean_width_20_80": float(w20.mean()),
                })

    df_hist = pd.DataFrame(hist_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df_hist.to_csv(OUT / "esg_garch_conditional.csv", index=False)
    print(f"Wrote {OUT / 'esg_garch_conditional.csv'}")

    # -------------------------------------------------------------
    # 2. Headline Numbers from Today's State
    # -------------------------------------------------------------
    print("Computing headline IPS comparisons from today's curve ...", flush=True)
    base_sleeve = basket(w_mkt, ["us_growth", "us_value", "us_small"], 0.6) + \
                  basket(w_mkt, ["europe", "japan", "pacific", "canada"], 0.3) + \
                  basket(w_mkt, ["em_xchina", "china"], 0.1)

    p_today = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_today.eq_garch = (alpha, beta, h0_today)

    headline_variants = [
        ("baseline", p_base),
        ("garch_unconditional_h1", p_garch),
        ("garch_today_filtered", p_today),
    ]

    head_rows = []
    for label, p_run in headline_variants:
        sc = simulate(p_run, n=n_headline, seed=11)
        res = engine.run(st, sc, cfg, snapshot_2031=True)
        f = res["facility"]
        tail = f[f <= np.percentile(f, 5)]

        r_simple = np.expm1(sc.eq_log) @ base_sleeve
        cum_sleeve = np.prod(1 + r_simple, axis=1) - 1
        s_p5, s_p50, s_p95 = np.percentile(cum_sleeve, [5, 50, 95])

        order = np.argsort(res["growth_2031"])
        i_med = int(order[int(0.50 * (len(order) - 1))])
        c = engine.conditional_2031(st, sc, res, p_run, i=i_med, n_inner=3000, cfg=cfg)
        inner = c["inner"]

        head_rows.append({
            "variant": label,
            "h0_start": 1.0 if label != "garch_today_filtered" else h0_today,
            "funded_share": float(res["funded"].mean()),
            "facility_p5": float(np.percentile(f, 5)),
            "facility_p10": float(np.percentile(f, 10)),
            "facility_median": float(np.median(f)),
            "facility_p90": float(np.percentile(f, 90)),
            "facility_p95": float(np.percentile(f, 95)),
            "facility_cvar5": float(tail.mean()),
            "sleeve_cum_ret_p5": float(s_p5),
            "sleeve_cum_ret_p50": float(s_p50),
            "sleeve_cum_ret_p95": float(s_p95),
            "cond2031_p10": float(np.percentile(inner, 10)),
            "cond2031_p90": float(np.percentile(inner, 90)),
            "cond2031_p20": float(np.percentile(inner, 20)),
            "cond2031_p80": float(np.percentile(inner, 80)),
        })

    df_head = pd.DataFrame(head_rows)
    df_head.to_csv(OUT / "esg_garch_headline.csv", index=False)
    print(f"Wrote {OUT / 'esg_garch_headline.csv'}")

    return df_hist, df_head


if __name__ == "__main__":
    t0 = time.time()
    df_hist, df_head = run_conditional_study()
    print("\n=== Conditional History Results ===")
    print(df_hist.round(4).to_string(index=False))
    print("\n=== Headline Results ===")
    print(df_head.round(2).to_string(index=False))
    print(f"\nCompleted in {time.time() - t0:.2f}s")

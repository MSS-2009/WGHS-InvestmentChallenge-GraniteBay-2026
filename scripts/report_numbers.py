"""Headline numbers for the IPS and the Final Report, in one reproducible place.

Usage: python scripts/report_numbers.py [n_scenarios]
Writes reports/report_numbers.json.
"""
import dataclasses as dc
import json
import sys
from pathlib import Path

import numpy as np

from lgm import engine, ladder
from lgm.asof import CURVE_DATE
from lgm.curve import bootstrap
from lgm.data.treasury import par_curve
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports"
BASELINE_FUNDS = ((0, 1, 2), (3, 4, 5, 6), (7, 8))


def basket(w_mkt, keys, total):
    idx = {g.key: i for i, g in enumerate(CORE)}
    v = np.zeros(len(CORE))
    s = sum(w_mkt[idx[k]] for k in keys)
    for k in keys:
        v[idx[k]] = total * w_mkt[idx[k]] / s
    return v


def main(n: int = 20_000):
    r = build_core()
    t, cov, w, w_mkt = r["table"], r["cov"], r["w_bl"], r["w_mkt"]
    rf, mw = r["cfg"]["cash_long_run"], r["exposures"]
    er = np.array([g.expense_ratio for g in CORE])
    out = {"n_scenarios": n}

    # 1. The core: weights, expected return, risk, fee, concentration, dollar targets
    arith = float(w @ (t["bl_excess"].values + rf))
    vol = float(np.sqrt(w @ cov @ w))
    out["core"] = {
        "weights": {g.etf: round(float(x), 4) for g, x in zip(CORE, w)},
        "regions": {"US": round(float(w[:3].sum()), 4), "developed": round(float(w[3:7].sum()), 4), "emerging": round(float(w[7:].sum()), 4)},
        "expected_geometric_net": round(arith - 0.5 * vol ** 2 - float(w @ er), 4),
        "market_expected_geometric_net": round(float(w_mkt @ (t["pi_excess"].values + rf)) - 0.5 * float(w_mkt @ cov @ w_mkt) - float(w_mkt @ er), 4),
        "volatility": round(vol, 4), "fee": round(float(w @ er), 5),
        "tracking_error": round(float(np.sqrt((w - w_mkt) @ cov @ (w - w_mkt))), 4),
        "tech_comm": round(float(w @ mw["tech"]), 4), "tech_comm_market": round(float(w_mkt @ mw["tech"]), 4),
        "china_taiwan": round(float(w @ mw["china_taiwan"]), 4), "china_taiwan_market": round(float(w_mkt @ mw["china_taiwan"]), 4),
        "delta": round(float(r["delta"]), 3),
        "market_geometric_prior": round(float(r["mkt_geo"]), 4),   # what delta is set to make the market earn
        "views": {name: round(float(q), 4) for name, _, q, *_ in r["views"]},   # geometric, before conversion
        "dollars_laura_90k": {g.etf: int(round(90_000 * x, -2)) for g, x in zip(CORE, w)},
        "dollars_wins_60k": {g.etf: int(round(60_000 * x, -2)) for g, x in zip(CORE, w)},
    }

    # 2. Sleeves with and without WInS commissions, under BL and equilibrium beliefs
    var = np.diag(cov)
    base = basket(w_mkt, ["us_growth", "us_value", "us_small"], 0.6) + basket(w_mkt, ["europe", "japan", "pacific", "canada"], 0.3) \
        + basket(w_mkt, ["em_xchina", "china"], 0.1)
    base_er = np.array([0.0003] * 7 + [0.0006] * 2)
    sleeves = {"VTI/VEA/VWO 60/30/10": (base, base_er, BASELINE_FUNDS), "Black-Litterman core": (w, er, None)}
    beliefs = {"bl": t["bl_geo_total"].values, "equilibrium": t["pi_excess"].values + rf - 0.5 * var}
    out["sleeves"] = {}
    for bname, geo in beliefs.items():
        sc = simulate(esg_params(r["cal"], geo), n=n, seed=11)
        for cname, comm in (("wins_commissions", True), ("no_commissions", False)):
            for sname, (sw, ser, groups) in sleeves.items():
                cfg = engine.EngineConfig(eq_er=tuple(ser), commissions=comm, fund_groups=groups)
                s = engine.summarize(engine.run(dc.replace(IPS, region_weights=tuple(sw)), sc, cfg))
                out["sleeves"][f"{bname}|{cname}|{sname}"] = {k: round(v, 1) for k, v in s.items()}

    # 3. The plan: BL core, BL beliefs, WInS commissions; 2031 quotes in bad, median and good worlds
    p = esg_params(r["cal"], beliefs["bl"])
    sc = simulate(p, n=n, seed=11)
    st = dc.replace(IPS, region_weights=tuple(w))
    share = st.contribution_share
    cfg = engine.EngineConfig(eq_er=tuple(er))
    res = engine.run(st, sc, cfg, snapshot_2031=True)
    out["plan"] = {k: round(v, 1) for k, v in engine.summarize(res).items()}
    out["plan"]["contribution_median"] = round(float(np.median(res["contribution"])), 1)
    out["plan"]["contribution_p5"] = round(float(np.percentile(res["contribution"], 5)), 1)
    out["plan"]["kept_by_laura_median"] = round(float(np.median(res["facility"] - res["contribution"])), 1)
    out["plan"]["lock_cost_2027_median"] = round(float(np.median(res["lock_cost_2027"])), 1)
    # The model's 10th-90th percentile range held ~98% of real outcomes on history; the band that held 80%
    # comes from scripts/policy_study.py (run it first).
    policy = OUT / "policy_study.json"
    lo, hi = (json.loads(policy.read_text())["range_calibration_history"]["calibrated_band"]["percentiles"]
              if policy.exists() else (20.0, 80.0))
    quotes = {"calibrated_band_percentiles": [lo, hi]}
    for label, q in (("bad_p10", 0.10), ("median", 0.50), ("good_p90", 0.90)):
        # Each world is a band of 21 scenarios around percentile q (engine.conditional_2031_band)
        c = engine.conditional_2031_band(st, sc, res, p, q=q, n_inner=3000, cfg=cfg,
                                         percentiles=sorted({5, 10, 50, 90, 95, lo, hi}))
        quotes[label] = {"growth_2031": round(c["growth_2031"], 1), "floor_dec_2032": round(c["floor"], 1),
                         "floor_dec_2032_band": [round(x, 1) for x in c["floor_range"]],
                         "guaranteed_contribution": round(share * c["floor"], 1),
                         "facility_p10": round(c["p10"], 1), "facility_p90": round(c["p90"], 1),
                         "contribution_range": [round(share * c["p10"], -2), round(share * c["p90"], -2)],
                         "contribution_range_calibrated": [round(share * c[f"p{lo:g}"], -2),
                                                           round(share * c[f"p{hi:g}"], -2)]}
    out["quotes_2031"] = quotes

    # 4. Stress tests
    stress = {}
    for label, shift in (("rates_minus_75bp_at_lock", -0.0075), ("rates_plus_75bp_at_lock", 0.0075)):
        # The shift is permanent: rates are expected to stay where they moved to (the model's "unchanged"
        # expectation), so the long-run level moves with today's level instead of pulling it back.
        d = np.array([shift, 0.0, 0.0])
        start = {"beta": np.tile(p.beta0, (n, 1)), "infl": np.full(n, p.infl0), "fx_log": np.zeros(n),
                 "tw_cost_log": np.zeros(n), "beta_shift": d}
        s2 = simulate(dc.replace(p, beta_mu=p.beta_mu + d), n=n, seed=11, start=start)
        rr = engine.run(st, s2, cfg)
        stress[label] = {"funded": float(rr["funded"].mean()), "median": round(float(np.median(rr["facility"])), 1),
                         "lock_cost_2027_median": round(float(np.median(rr["lock_cost_2027"])), 1)}
    # Reinvestment: the ladder premium assumes cash awaiting a payment earns 3%. Pricing the reserve so it
    # is certain even at 0% shows what that assumption is worth.
    zc = bootstrap(par_curve(CURVE_DATE))
    k0 = ladder.premium(zc, 0.0)
    rr = engine.run(st, sc, dc.replace(cfg, kappa0=k0))
    stress["reserve_certain_at_0pct_reinvestment"] = {
        "ladder_premium": round(k0, 4), "ladder_premium_at_3pct": round(ladder.premium(zc, 0.03), 4),
        "median": round(float(np.median(rr["facility"])), 1),
        "median_change": round(float(np.median(rr["facility"]) - np.median(res["facility"])), 1),
        "lock_cost_2027_median": round(float(np.median(rr["lock_cost_2027"])), 1)}
    eq_only = np.argsort((sc.eq_log * np.asarray(w)).sum((1, 2)))[: n // 20]     # worst core-weighted stock paths
    stress["worst_5pct_stock_paths_median"] = round(float(np.median(res["facility"][eq_only])), 1)
    stress["inflation_4pct_buying_power_change"] = round((1.03 / 1.04) ** 6 - 1, 4)   # 4% vs 3% a year, 6 years (arithmetic)
    out["stress"] = stress
    (OUT / "report_numbers.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)

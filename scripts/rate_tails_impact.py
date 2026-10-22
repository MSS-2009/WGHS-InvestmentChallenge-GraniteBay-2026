"""Evaluate the impact of rate tail treatments on headline numbers and policy robustness.

Generates reports/rate_tails_impact.csv containing:
1. Headline IPS numbers under today's model vs candidate rate tail options.
2. Re-run of policy_robust shortlist under tails_tdof3 and tails_gaussian with rate tails applied.
"""
from __future__ import annotations

import dataclasses as dc
import sys
from pathlib import Path

# Add project root to sys.path so scripts can be imported cleanly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from lgm import engine
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS
from lgm.esg import simulate
import scripts.policy_robust as pr

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_CSV = REPORTS_DIR / "rate_tails_impact.csv"


def certainty_equivalent(x: np.ndarray, gamma: float) -> float:
    x = np.maximum(x, 1.0)
    return float(np.mean(x ** (1.0 - gamma)) ** (1.0 / (1.0 - gamma)))


def run_impact(n: int = 20_000, seed: int = 11) -> pd.DataFrame:
    core = build_core()
    base_params = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    base_strategy = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), commissions=True)

    rows = []

    # 1. Headline IPS numbers across rate tail treatments
    headline_candidates = [
        ("today_t5", dc.replace(base_params, rate_dof=None, rate_shared=0.0)),
        ("rate_gaussian (recommended)", dc.replace(base_params, rate_dof="gaussian", rate_shared=0.0)),
        ("rate_indep_t14", dc.replace(base_params, rate_dof=14.0, rate_shared=0.0)),
        ("rate_shared_0.10", dc.replace(base_params, rate_dof="gaussian", rate_shared=0.10)),
    ]

    for treat_name, p in headline_candidates:
        sc = simulate(p, n=n, seed=seed)
        res = engine.run(base_strategy, sc, cfg)
        fac = res["facility"]
        p5 = float(np.percentile(fac, 5))
        tail = fac[fac <= p5]
        cvar5 = float(np.mean(tail)) if tail.size else 0.0

        rows.append({
            "section": "headline_ips",
            "policy": "IPS",
            "shift": "base",
            "rate_treatment": treat_name,
            "funded": round(float(res["funded"].mean()), 5),
            "min": round(float(fac.min()), 1),
            "p1": round(float(np.percentile(fac, 1)), 1),
            "p5": round(p5, 1),
            "cvar5": round(cvar5, 1),
            "median": round(float(np.median(fac)), 1),
            "ce_gamma2": round(certainty_equivalent(fac, 2.0), 1),
            "ce_gamma4": round(certainty_equivalent(fac, 4.0), 1),
            "ce_gamma8": round(certainty_equivalent(fac, 8.0), 1),
            "secured_2031_median": round(float(np.median(res["floor_2033"])), 1),
        })

    # 2. Shortlisted policies across assumption shifts (tails_tdof3, tails_gaussian, base)
    shift_configs = [
        ("base", "today_t5", dc.replace(base_params, t_dof=5.0, rate_dof=None)),
        ("base", "rate_gaussian (recommended)", dc.replace(base_params, t_dof=5.0, rate_dof="gaussian")),
        ("tails_tdof3", "today_common_t3", dc.replace(base_params, t_dof=3.0, rate_dof=None)),
        ("tails_tdof3", "rate_gaussian (recommended)", dc.replace(base_params, t_dof=3.0, rate_dof="gaussian")),
        ("tails_tdof3", "rate_indep_t14", dc.replace(base_params, t_dof=3.0, rate_dof=14.0)),
        ("tails_gaussian", "today_gaussian", dc.replace(base_params, t_dof=None, rate_dof=None)),
        ("tails_gaussian", "rate_gaussian (recommended)", dc.replace(base_params, t_dof=None, rate_dof="gaussian")),
    ]

    for shift_name, treat_name, p in shift_configs:
        sc = simulate(p, n=n, seed=seed)
        for p_dict in pr.SHORTLIST:
            st = dc.replace(
                base_strategy,
                name=p_dict["name"],
                lock_2027=p_dict["lock_2027"],
                lock_2028=p_dict["lock_2028"],
                lock_2031=p_dict["lock_2031"],
                equity_share=p_dict["equity_share"],
                equity_share_end=p_dict["equity_share_end"],
                floor_share=p_dict["floor_share"],
                floor_year=p_dict["floor_year"],
                ratchet_trigger=p_dict["ratchet_trigger"],
                ratchet_share=p_dict["ratchet_share"],
            )
            r = engine.run(st, sc, cfg)
            fac = r["facility"]
            p5 = float(np.percentile(fac, 5))
            tail = fac[fac <= p5]
            cvar5 = float(np.mean(tail)) if tail.size else 0.0

            rows.append({
                "section": "policy_robust_shortlist",
                "policy": p_dict["name"],
                "shift": shift_name,
                "rate_treatment": treat_name,
                "funded": round(float(np.mean(r["funded"])), 5),
                "min": round(float(fac.min()), 1),
                "p1": round(float(np.percentile(fac, 1)), 1),
                "p5": round(p5, 1),
                "cvar5": round(cvar5, 1),
                "median": round(float(np.median(fac)), 1),
                "ce_gamma2": round(certainty_equivalent(fac, 2.0), 1),
                "ce_gamma4": round(certainty_equivalent(fac, 4.0), 1),
                "ce_gamma8": round(certainty_equivalent(fac, 8.0), 1),
                "secured_2031_median": round(float(np.median(r["floor_2033"])), 1),
            })

    df = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    return df


if __name__ == "__main__":
    df = run_impact()
    print(f"Wrote {len(df)} rows to {OUTPUT_CSV}")
    print("\n=== Headline IPS Numbers (Base) ===")
    head = df[df["section"] == "headline_ips"]
    print(head[["rate_treatment", "funded", "min", "p1", "p5", "cvar5", "median", "ce_gamma4"]].to_string(index=False))

    print("\n=== Policy Robust Shortlist: tails_tdof3 Comparison ===")
    t3 = df[(df["section"] == "policy_robust_shortlist") & (df["shift"] == "tails_tdof3")]
    print(t3[["policy", "rate_treatment", "funded", "min", "p5", "median", "ce_gamma4"]].to_string(index=False))

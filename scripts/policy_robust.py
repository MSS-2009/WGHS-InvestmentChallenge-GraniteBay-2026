"""Evaluate policy robustness across 11 assumption shifts for shortlisted policies.

Usage:
  python scripts/policy_robust.py [--summary] [--n-scenarios N]
Writes reports/policy_robust.csv.
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_CSV = REPORTS_DIR / "policy_robust.csv"

OBJECTIVES = [
    "median",
    "p5",
    "cvar5",
    "ce_gamma2",
    "ce_gamma4",
    "ce_gamma8",
    "secured_2031_median",
]

SHORTLIST = [
    {
        "policy_id": 2721,
        "name": "IPS",
        "lock_2027": 1.0,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.6,
        "equity_share_end": 0.6,
        "floor_share": 0.6,
        "floor_year": 2031,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 2361,
        "name": "P2361",
        "lock_2027": 1.0,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.4,
        "equity_share_end": 0.4,
        "floor_share": 1.0,
        "floor_year": 2031,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 2485,
        "name": "P2485",
        "lock_2027": 1.0,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.4,
        "equity_share_end": 0.0,
        "floor_share": 1.0,
        "floor_year": 2030,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 2305,
        "name": "P2305",
        "lock_2027": 1.0,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.4,
        "equity_share_end": 0.4,
        "floor_share": 0.0,
        "floor_year": 2031,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 2333,
        "name": "P2333",
        "lock_2027": 1.0,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.4,
        "equity_share_end": 0.4,
        "floor_share": 0.6,
        "floor_year": 2030,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 1729,
        "name": "P1729",
        "lock_2027": 0.75,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 0.7,
        "equity_share_end": 0.7,
        "floor_share": 0.0,
        "floor_year": 2031,
        "ratchet_trigger": None,
        "ratchet_share": 0.0,
    },
    {
        "policy_id": 964,
        "name": "P0964",
        "lock_2027": 0.5,
        "lock_2028": 1.0,
        "lock_2031": 1.0,
        "equity_share": 1.0,
        "equity_share_end": 1.0,
        "floor_share": 0.0,
        "floor_year": 2031,
        "ratchet_trigger": 1.2,
        "ratchet_share": 1.0,
    },
]


def certainty_equivalent(x: np.ndarray, gamma: float) -> float:
    x = np.maximum(x, 1.0)
    return float(np.mean(x ** (1.0 - gamma)) ** (1.0 / (1.0 - gamma)))


def evaluate_policy(
    p_dict: dict,
    scenarios,
    cfg: engine.EngineConfig,
    base_strategy,
) -> dict:
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
    r = engine.run(st, scenarios, cfg)
    fac = r["facility"]
    p5 = float(np.percentile(fac, 5))
    tail = fac[fac <= p5]
    cvar5 = float(np.mean(tail)) if tail.size else 0.0
    return {
        "funded": round(float(np.mean(r["funded"])), 4),
        "median": round(float(np.median(fac)), 1),
        "p5": round(p5, 1),
        "cvar5": round(cvar5, 1),
        "ce_gamma2": round(certainty_equivalent(fac, 2.0), 1),
        "ce_gamma4": round(certainty_equivalent(fac, 4.0), 1),
        "ce_gamma8": round(certainty_equivalent(fac, 8.0), 1),
        "secured_2031_median": round(float(np.median(r["floor_2033"])), 1),
    }


def define_shifts(base_params, n_scenarios: int):
    """Return list of (shift_name, sim_callable, ibtm_expense_ratio)."""
    p = base_params
    n = n_scenarios

    def sim_base():
        return simulate(p, n=n, seed=11)

    def sim_eq_p25():
        # PGIM / Vanguard forecast 5.2% vs 13-firm median 5.9% -> -0.70%
        return simulate(dc.replace(p, eq_geo=p.eq_geo - 0.0070), n=n, seed=11)

    def sim_eq_lowest():
        # Research Affiliates forecast 3.1% vs 13-firm median 5.9% -> -2.80%
        return simulate(dc.replace(p, eq_geo=p.eq_geo - 0.0280), n=n, seed=11)

    def sim_eq_highest():
        # BlackRock forecast 9.0% vs 13-firm median 5.9% -> +3.10%
        return simulate(dc.replace(p, eq_geo=p.eq_geo + 0.0310), n=n, seed=11)

    def sim_vol_08():
        return simulate(dc.replace(p, eq_vol_scale=0.8), n=n, seed=11)

    def sim_vol_12():
        return simulate(dc.replace(p, eq_vol_scale=1.2), n=n, seed=11)

    def sim_tdof3():
        return simulate(dc.replace(p, t_dof=3.0), n=n, seed=11)

    def sim_gaussian():
        return simulate(dc.replace(p, t_dof=None), n=n, seed=11)

    def sim_rates_down():
        d = np.array([-0.0075, 0.0, 0.0])
        start = {
            "beta": np.tile(p.beta0, (n, 1)),
            "infl": np.full(n, p.infl0),
            "fx_log": np.zeros(n),
            "tw_cost_log": np.zeros(n),
            "beta_shift": d,
        }
        return simulate(dc.replace(p, beta_mu=p.beta_mu + d), n=n, seed=11, start=start)

    def sim_rates_up():
        d = np.array([0.0075, 0.0, 0.0])
        start = {
            "beta": np.tile(p.beta0, (n, 1)),
            "infl": np.full(n, p.infl0),
            "fx_log": np.zeros(n),
            "tw_cost_log": np.zeros(n),
            "beta_shift": d,
        }
        return simulate(dc.replace(p, beta_mu=p.beta_mu + d), n=n, seed=11, start=start)

    def sim_bond_er():
        return simulate(p, n=n, seed=11)

    return [
        ("base", sim_base, 0.0007),
        ("eq_cma_p25", sim_eq_p25, 0.0007),
        ("eq_cma_lowest", sim_eq_lowest, 0.0007),
        ("eq_cma_highest", sim_eq_highest, 0.0007),
        ("eq_vol_0.8", sim_vol_08, 0.0007),
        ("eq_vol_1.2", sim_vol_12, 0.0007),
        ("tails_tdof3", sim_tdof3, 0.0007),
        ("tails_gaussian", sim_gaussian, 0.0007),
        ("rates_minus_75bp", sim_rates_down, 0.0007),
        ("rates_plus_75bp", sim_rates_up, 0.0007),
        ("bond_er_doubled", sim_bond_er, 0.0014),
    ]


def run_robustness(n_scenarios: int = 20_000) -> pd.DataFrame:
    core = build_core()
    base_params = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    base_strategy = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), commissions=True)

    shifts = define_shifts(base_params, n_scenarios)
    orig_ibtm_er = engine.ER["IBTM"]

    all_rows = []
    t_start = time.perf_counter()

    try:
        for s_idx, (s_name, sim_fn, ibtm_er) in enumerate(shifts, 1):
            t_s0 = time.perf_counter()
            engine.ER["IBTM"] = ibtm_er
            sc = sim_fn()

            shift_rows = []
            for pol in SHORTLIST:
                metrics = evaluate_policy(pol, sc, cfg, base_strategy)
                shift_rows.append({
                    "shift": s_name,
                    "policy_id": pol["policy_id"],
                    "name": pol["name"],
                    "lock_2027": pol["lock_2027"],
                    "equity_share": pol["equity_share"],
                    "equity_share_end": pol["equity_share_end"],
                    "floor_share": pol["floor_share"],
                    "floor_year": pol["floor_year"],
                    "ratchet_trigger": pol["ratchet_trigger"],
                    "ratchet_share": pol["ratchet_share"],
                    **metrics,
                })

            # Free scenario array memory immediately
            del sc

            # Compute regret for each objective within this shift
            for obj in OBJECTIVES:
                best_val = max(r[obj] for r in shift_rows)
                for r in shift_rows:
                    r[f"regret_{obj}"] = round(best_val - r[obj], 1)

            all_rows.extend(shift_rows)
            t_s = time.perf_counter() - t_s0
            print(f"[{s_idx:2d}/{len(shifts):2d}] Shift '{s_name}' evaluated in {t_s:.2f} s")

    finally:
        engine.ER["IBTM"] = orig_ibtm_er

    df = pd.DataFrame(all_rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    t_total = time.perf_counter() - t_start
    print(f"\nAll {len(shifts)} shifts x {len(SHORTLIST)} policies evaluated in {t_total:.2f} s.")
    print(f"Saved: {OUTPUT_CSV}")
    return df


def print_summary(df: pd.DataFrame | None = None):
    if df is None:
        if not OUTPUT_CSV.exists():
            print(f"File not found: {OUTPUT_CSV}. Running evaluation first...")
            df = run_robustness()
        else:
            df = pd.read_csv(OUTPUT_CSV)

    print("\n" + "=" * 90)
    print("                      ROBUSTNESS ANALYSIS: PER-SHIFT WINNERS")
    print("=" * 90)

    for s_name in df["shift"].unique():
        sub = df[df["shift"] == s_name]
        print(f"\n>>> Shift: {s_name}")
        for obj in OBJECTIVES:
            best_row = sub.sort_values(obj, ascending=False).iloc[0]
            val = best_row[obj]
            pname = best_row["name"]
            print(f"  {obj:20s}: {pname:10s} (${val:,.1f})")

    print("\n" + "=" * 90)
    print("             MAX-REGRET TABLE PER POLICY ACROSS ALL 11 SHIFTS ($)")
    print("=" * 90)

    regret_cols = [f"regret_{obj}" for obj in OBJECTIVES]
    max_reg = df.groupby(["policy_id", "name"])[regret_cols].max()
    # Rename columns for presentation
    renames = {f"regret_{obj}": f"max_reg_{obj}" for obj in OBJECTIVES}
    disp = max_reg.rename(columns=renames)
    print(disp.to_string())

    print("\n" + "=" * 90)
    print("             DETAILED REGRET COMPARISON: IPS vs P2361 vs P2485")
    print("=" * 90)

    comp_policies = ["IPS", "P2361", "P2485"]
    sub_comp = df[df["name"].isin(comp_policies)]
    for obj in OBJECTIVES:
        pivot = sub_comp.pivot(index="shift", columns="name", values=f"regret_{obj}")
        print(f"\n--- Regret on {obj} ($) ---")
        print(pivot[comp_policies].to_string())


def main():
    parser = argparse.ArgumentParser(description="Evaluate policy robustness across 11 assumption shifts.")
    parser.add_argument("--summary", action="store_true", help="Print summary of winners and max-regret table.")
    parser.add_argument("--n-scenarios", type=int, default=20_000, help="Number of scenarios per shift.")
    args = parser.parse_args()

    if args.summary:
        if not OUTPUT_CSV.exists():
            df = run_robustness(args.n_scenarios)
        else:
            df = pd.read_csv(OUTPUT_CSV)
        print_summary(df)
    else:
        df = run_robustness(args.n_scenarios)
        print_summary(df)


if __name__ == "__main__":
    main()

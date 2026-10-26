"""Task 1 measurements: baseline engine timing, LP solve timing, and distinct optimal bases.

Usage: python scripts/topup_measure.py [n_scenarios]
"""
from __future__ import annotations

import dataclasses as dc
import sys
import time

import numpy as np
from scipy.optimize import linprog

from lgm import engine, ladder
from lgm.asof import month_of
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS
from topup_2033 import get_held_ladder_data, roll_cash_to_2033, solve_topup_lp


def measure_engine(st, n: int = 20_000, runs: int = 5, topup_2033: bool = True) -> dict[str, float]:
    core = build_core()
    w = core["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=n, seed=11)
    st_run = dc.replace(st, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er), topup_2033=topup_2033)

    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        _ = engine.run(st_run, sc, cfg)
        t1 = time.perf_counter()
        times.append(t1 - t0)

    med = float(np.median(times))
    return {"runs": times, "median_s": med}


def measure_engine_today(n: int = 20_000, runs: int = 5) -> dict[str, float]:
    return measure_engine(IPS, n=n, runs=runs, topup_2033=False)


def measure_lp_and_bases(n: int = 20_000) -> dict:
    lad = get_held_ladder_data()
    pays = lad["pays"]
    settle_2033 = lad["pay_dates"][0]
    flow_by_m = lad["flow_by_m"]
    held_cash_by_bucket = lad["held_cash_by_bucket"]
    active_2033 = [inst for inst in lad["universe"] if ladder._flows(inst, lad["curve_2026"], settle_2033)[0]]

    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    m_2033 = month_of(2033, 1)
    sc = simulate(p, n=n, seed=11)

    r_list = [-np.log(sc.df(m, 1/12)[:, 0]) * 12.0 for m in range(2, m_2033)]
    r_sim = np.maximum(np.column_stack(r_list), 0.0)
    cash_2033 = roll_cash_to_2033(flow_by_m, r_sim, start_m=2, end_m=m_2033)

    # Solve exact LP for each path and record basis
    t0 = time.perf_counter()
    bases_count: dict[tuple[int, ...], int] = {}
    topup_costs = np.zeros(n)

    for i in range(n):
        c_curve = sc.curve(i, m_2033, settle_2033)
        sol = solve_topup_lp(c_curve, cash_2033[i], active_2033, pays, held_cash_by_bucket)
        topup_costs[i] = sol["cost"]

        # To find the exact LP basis:
        # In linprog, basic variables have marginals == 0
        # Let's extract the basis from linprog
        # We can reconstruct the basic column indices
        A, p_vec, labels, scale = ladder.build_matrix(active_2033, pays, c_curve, reinvest=0.0)
        K = len(pays)
        J = len(active_2033)
        c_obj = np.concatenate([p_vec, [1.0], np.zeros(K)])
        A_eq = np.zeros((K, J + 1 + K))
        b_eq = np.zeros(K)
        A_eq[0, :J] = A[0, :J]
        A_eq[0, J] = 1.0
        A_eq[0, J + 1 + 0] = -1.0
        b_eq[0] = lad["L"][0] - (cash_2033[i] + held_cash_by_bucket[0])
        for k in range(1, K):
            A_eq[k, :J] = A[k, :J]
            A_eq[k, J + 1 + k - 1] = 1.0
            A_eq[k, J + 1 + k] = -1.0
            b_eq[k] = lad["L"][k] - held_cash_by_bucket[k]

        res = linprog(c_obj, A_eq=A_eq, b_eq=b_eq, bounds=[(0, None)] * (J + 1 + K), method="highs")
        basic = tuple(sorted(int(idx) for idx in np.where(res.lower.marginals < 1e-6)[0]))
        bases_count[basic] = bases_count.get(basic, 0) + 1

    t1 = time.perf_counter()
    total_lp_s = t1 - t0
    per_path_ms = (total_lp_s / n) * 1000.0

    return {
        "n_paths": n,
        "total_lp_s": total_lp_s,
        "per_path_ms": per_path_ms,
        "distinct_bases_count": len(bases_count),
        "bases_distribution": bases_count,
        "zero_topup_share": float((topup_costs < 1e-4).mean()),
    }


def main():
    from lgm.strategies import S1
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    print("=" * 70)
    print("Task 1: Measurement Script (scripts/topup_measure.py)")
    print("=" * 70)

    # 1. Measure engine.run for IPS and S1
    print(f"\n1. Measuring engine.run on {n:,} headline scenarios (5 runs each)...")
    ips_false = measure_engine(IPS, n=n, runs=5, topup_2033=False)
    ips_true = measure_engine(IPS, n=n, runs=5, topup_2033=True)
    s1_false = measure_engine(S1, n=n, runs=5, topup_2033=False)
    s1_true = measure_engine(S1, n=n, runs=5, topup_2033=True)

    delta_ips = ips_true["median_s"] - ips_false["median_s"]
    delta_s1 = s1_true["median_s"] - s1_false["median_s"]

    print(f"IPS topup_2033=False median: {ips_false['median_s']:.4f} s")
    print(f"IPS topup_2033=True  median: {ips_true['median_s']:.4f} s (Delta: {delta_ips:+.4f} s, budget <= +0.50 s)")
    print(f"S1  topup_2033=False median: {s1_false['median_s']:.4f} s")
    print(f"S1  topup_2033=True  median: {s1_true['median_s']:.4f} s (Delta: {delta_s1:+.4f} s, budget <= +0.50 s)")

    # 2. Measure LP timing and distinct optimal bases
    print(f"\n2. Measuring exact LP per path and counting distinct optimal bases ({n:,} paths)...")
    lp_res = measure_lp_and_bases(n=n)
    print(f"Total LP runtime: {lp_res['total_lp_s']:.2f} s")
    print(f"Exact LP time per path: {lp_res['per_path_ms']:.3f} ms")
    print(f"Number of distinct optimal bases: {lp_res['distinct_bases_count']}")
    print(f"Share of paths needing zero top-up: {lp_res['zero_topup_share']:.2%}")

    print("\nTop bases by path count:")
    sorted_bases = sorted(lp_res["bases_distribution"].items(), key=lambda x: -x[1])
    for b, count in sorted_bases[:15]:
        print(f"  Basis {b}: {count} paths ({count / n:.2%})")


if __name__ == "__main__":
    main()

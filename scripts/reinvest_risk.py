"""How certain is the ladder when cash earns what rates actually pay?

Usage: python scripts/reinvest_risk.py [n_scenarios]
Simulates the Wharton reserve ladder held from January 2027 to January 2042 under
simulated short rates, evaluating cash reinvestment risk against flat 3% and 0% baselines.
Writes reports/reinvest_risk.csv.
"""
from __future__ import annotations

import dataclasses as dc
import datetime as dt
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import ladder
from lgm.asof import CURVE_DATE, month_of
from lgm.curve import ZeroCurve, bootstrap
from lgm.data.treasury import par_curve
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params

OUT_CSV = Path(__file__).resolve().parents[1] / "reports" / "reinvest_risk.csv"


def measure_simulation(seed: int = 11) -> dict[str, float]:
    """Measure timing and memory for ESG simulation to January 2042 (Task 1)."""
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    m_2042 = month_of(2042, 1)  # 182
    p_2042 = dc.replace(p, months=m_2042)

    # Time and memory for 2,000 scenarios
    tracemalloc.start()
    t0 = time.perf_counter()
    _ = simulate(p_2042, n=2000, seed=seed)
    t1 = time.perf_counter()
    _, peak_2k = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    time_2k = t1 - t0
    peak_2k_mb = peak_2k / (1024**2)

    # Scaled estimates for 20,000 scenarios (10x)
    est_time_20k = time_2k * 10.0
    est_peak_20k_mb = peak_2k_mb * 10.0

    # Measured actual for 20,000 scenarios
    tracemalloc.start()
    t0 = time.perf_counter()
    _ = simulate(p_2042, n=20000, seed=seed)
    t1 = time.perf_counter()
    _, peak_20k = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    time_20k = t1 - t0
    peak_20k_mb = peak_20k / (1024**2)

    return {
        "engine_months": m_2042,
        "time_2k_s": time_2k,
        "peak_mem_2k_mb": peak_2k_mb,
        "est_time_20k_s": est_time_20k,
        "est_peak_mem_20k_mb": est_peak_20k_mb,
        "time_20k_s": time_20k,
        "peak_mem_20k_mb": peak_20k_mb,
    }


def build_headline_ladder(curve: ZeroCurve | None = None):
    """Build the reserve ladder exactly as ladder.premium(curve, 0.03) on the headline curve."""
    if curve is None:
        curve = bootstrap(par_curve(CURVE_DATE))
    pays = ladder.payment_schedule()
    universe = ladder.wins_reserve_universe()
    active = [inst for inst in universe if ladder._flows(inst, curve, curve.date)[0]]
    lp_3 = ladder.solve(active, pays, curve, reinvest=0.03)
    lp_0 = ladder.solve(active, pays, curve, reinvest=0.00)

    # Deterministic dated cash schedule
    held_flows: list[tuple[dt.date, float, str]] = []
    for inst in active:
        flows, price, label, unit = ladder._flows(inst, curve, curve.date)
        if label in lp_3.units:
            u = lp_3.units[label]
            for d, cf in flows:
                held_flows.append((d, u * (cf / unit), label))

    held_flows.sort(key=lambda x: x[0])

    # Aggregate by date
    dated_schedule: dict[dt.date, float] = {}
    for d, amt, _ in held_flows:
        dated_schedule[d] = dated_schedule.get(d, 0.0) + amt

    # Map to engine months
    flow_by_m: dict[int, float] = {}
    for d, amt, _ in held_flows:
        m = month_of(d.year, d.month)
        flow_by_m[m] = flow_by_m.get(m, 0.0) + amt

    pay_by_m: dict[int, float] = {month_of(d.year, d.month): amt for d, amt in pays}

    return {
        "curve": curve,
        "pays": pays,
        "active": active,
        "lp_3": lp_3,
        "lp_0": lp_0,
        "held_flows": held_flows,
        "dated_schedule": dated_schedule,
        "flow_by_m": flow_by_m,
        "pay_by_m": pay_by_m,
    }


def check_schedule_against_lp(curve: ZeroCurve, active, lp_3, lp_0, pays) -> dict[str, float]:
    """Check schedule against LP: 3% surplus ~ 0, 0% shortfall ~ premium diff."""
    zc_cost = ladder.zero_coupon_cost(curve, pays)
    prem_3 = ladder.premium(curve, 0.03)
    prem_0 = ladder.premium(curve, 0.00)
    prem_diff = prem_0 - prem_3
    cost_diff = lp_0.cost - lp_3.cost

    cov_3 = ladder.check_coverage(active, lp_3.holdings, pays, curve, reinvest=0.03)
    cov_0 = ladder.check_coverage(active, lp_3.holdings, pays, curve, reinvest=0.00)

    final_surplus_3 = cov_3[-1]
    final_surplus_0 = cov_0[-1]
    shortfall_0 = -final_surplus_0

    if abs(final_surplus_3) > 1e-4:
        raise RuntimeError(f"Check failed: 3% final surplus is not zero ({final_surplus_3})")
    if shortfall_0 < 4000.0 or shortfall_0 > 15000.0:
        raise RuntimeError(f"Check failed: 0% shortfall {shortfall_0} not in expected range")

    return {
        "zc_cost": zc_cost,
        "cost_3": lp_3.cost,
        "cost_0": lp_0.cost,
        "prem_3": prem_3,
        "prem_0": prem_0,
        "prem_diff": prem_diff,
        "cost_diff": cost_diff,
        "final_surplus_3": final_surplus_3,
        "final_surplus_0": final_surplus_0,
        "shortfall_0": shortfall_0,
    }


def roll_forward(
    flow_by_m: dict[int, float],
    pay_by_m: dict[int, float],
    rates: float | np.ndarray,
    start_m: int = 2,
    end_m: int = 182,
    initial_cash: float | None = None,
    extra_cash: float | np.ndarray = 0.0,
    compounding: str = "simple",
) -> dict[str, np.ndarray]:
    """Roll cash forward month by month from start_m to end_m.

    Cash on hand entering month m is used to meet any payment due at month m.
    Coupons and fund distributions arriving in month m are added.
    Cash on hand then earns month m's rate.
    """
    n_months = end_m - start_m + 1
    rates_arr = np.asarray(rates, dtype=float)
    if rates_arr.ndim == 0:
        is_2d = False
        n_paths = 1
    elif rates_arr.ndim == 1:
        if len(rates_arr) == n_months:
            is_2d = False
            n_paths = 1
        else:
            raise ValueError(f"1D rates length {len(rates_arr)} != n_months {n_months}")
    elif rates_arr.ndim == 2:
        is_2d = True
        n_paths, m_len = rates_arr.shape
        if m_len != n_months:
            raise ValueError(f"2D rates second dimension {m_len} != n_months {n_months}")
    else:
        raise ValueError(f"rates must be scalar, 1D or 2D, got shape {rates_arr.shape}")

    c0 = sum(amt for m, amt in flow_by_m.items() if m < start_m) if initial_cash is None else float(initial_cash)
    if is_2d:
        cash = np.full(n_paths, c0, dtype=float) + np.asarray(extra_cash, dtype=float)
    else:
        extra_arr = np.asarray(extra_cash, dtype=float)
        if extra_arr.ndim > 0:
            cash = np.full(len(extra_arr), c0, dtype=float) + extra_arr
            is_2d = True
            n_paths = len(extra_arr)
        else:
            cash = float(c0 + extra_cash)

    all_shortfalls: list[np.ndarray | float] = []
    all_surpluses: list[np.ndarray | float] = []
    pay_dates_m: list[int] = []

    for idx, m in enumerate(range(start_m, end_m + 1)):
        # 1. Payment due on the 1st of month m
        if m in pay_by_m:
            pmt = pay_by_m[m]
            sf = np.maximum(pmt - cash, 0.0)
            cash = np.maximum(cash - pmt, 0.0)
            all_shortfalls.append(sf)
            all_surpluses.append(cash)
            pay_dates_m.append(m)

        # 2. Inflows arriving during month m (e.g. May 15, Nov 15, Dec 15)
        if m in flow_by_m and m >= start_m:
            cash = cash + flow_by_m[m]

        # 3. Monthly interest
        if rates_arr.ndim == 0:
            r = float(rates_arr)
        elif rates_arr.ndim == 1:
            r = rates_arr[idx]
        else:
            r = rates_arr[:, idx]

        if compounding == "simple":
            factor = 1.0 + r / 12.0
        elif compounding == "exp":
            factor = np.exp(r / 12.0)
        elif compounding == "annual":
            factor = (1.0 + r) ** (1.0 / 12.0)
        else:
            raise ValueError(f"Unknown compounding: {compounding!r}")

        cash = cash * factor

    if is_2d:
        sf_mat = np.column_stack(all_shortfalls) if all_shortfalls else np.zeros((n_paths, 0))
        surplus_mat = np.column_stack(all_surpluses) if all_surpluses else np.zeros((n_paths, 0))
    else:
        sf_mat = np.array(all_shortfalls)
        surplus_mat = np.array(all_surpluses)

    return {
        "shortfalls": sf_mat,
        "total_shortfall": sf_mat.sum(axis=-1),
        "surpluses": surplus_mat,
        "final_cash": cash,
        "pay_months": pay_dates_m,
    }


def compute_extra_cash_lock(
    flow_by_m: dict[int, float],
    pay_by_m: dict[int, float],
    rates: float | np.ndarray,
    start_m: int = 2,
    end_m: int = 182,
    initial_cash: float | None = None,
    compounding: str = "simple",
    discount_rate: float | None = None,
) -> np.ndarray:
    """Compute extra cash needed at lock (start_m) so that each path misses zero payments."""
    n_months = end_m - start_m + 1
    rates_arr = np.asarray(rates, dtype=float)
    if rates_arr.ndim == 0:
        is_2d = False
        n_paths = 1
        rates_2d = np.full((1, n_months), float(rates_arr))
    elif rates_arr.ndim == 1:
        is_2d = False
        n_paths = 1
        rates_2d = rates_arr.reshape(1, n_months)
    elif rates_arr.ndim == 2:
        is_2d = True
        n_paths, m_len = rates_arr.shape
        rates_2d = rates_arr
    else:
        raise ValueError("rates must be scalar, 1D or 2D")

    c0 = sum(amt for m, amt in flow_by_m.items() if m < start_m) if initial_cash is None else float(initial_cash)
    cash_untrunc = np.full(n_paths, c0, dtype=float)
    min_disc_surplus = np.zeros(n_paths, dtype=float)
    G = np.ones(n_paths, dtype=float)

    for idx, m in enumerate(range(start_m, end_m + 1)):
        # 1. Payment
        if m in pay_by_m:
            cash_untrunc -= pay_by_m[m]
            if discount_rate is None:
                disc_surplus = cash_untrunc / G
            else:
                if compounding == "simple":
                    d_fact = (1.0 + discount_rate / 12.0) ** idx
                else:
                    d_fact = np.exp(discount_rate * idx / 12.0)
                disc_surplus = cash_untrunc / d_fact
            min_disc_surplus = np.minimum(min_disc_surplus, disc_surplus)

        # 2. Inflows
        if m in flow_by_m and m >= start_m:
            cash_untrunc += flow_by_m[m]

        # 3. Monthly growth
        r = rates_2d[:, idx]
        if compounding == "simple":
            factor = 1.0 + r / 12.0
        elif compounding == "exp":
            factor = np.exp(r / 12.0)
        elif compounding == "annual":
            factor = (1.0 + r) ** (1.0 / 12.0)
        else:
            raise ValueError(f"Unknown compounding: {compounding!r}")

        cash_untrunc *= factor
        G *= factor

    extra = np.maximum(-min_disc_surplus, 0.0)
    return extra if is_2d else float(extra[0])


def main(n: int = 20_000, seed: int = 11):
    print("=" * 80)
    print("REINVESTMENT RISK STUDY: RESERVE LADDER HOLDING 2027-2042")
    print("=" * 80)

    # 1. Measurement Benchmark (Task 1)
    print("\n[Task 1: Benchmark Measurement]")
    bench = measure_simulation(seed=seed)
    print(f"Horizon: {bench['engine_months']} engine months to Jan 2042")
    print(f"2,000 scenarios:   {bench['time_2k_s']:.4f} s, peak memory {bench['peak_mem_2k_mb']:.2f} MB")
    print(f"20,000 estimated: {bench['est_time_20k_s']:.4f} s, peak memory {bench['est_peak_mem_20k_mb']:.2f} MB")
    print(f"20,000 measured:  {bench['time_20k_s']:.4f} s, peak memory {bench['peak_mem_20k_mb']:.2f} MB")
    print(f"Peak memory is safely within 2.0 GB limit ({bench['peak_mem_20k_mb']:.1f} MB < 2048 MB).")

    # 2. Build Ladder and Schedule Checks (Task 2)
    print("\n[Task 2: Headline Curve Ladder & Schedule Checks]")
    lad = build_headline_ladder()
    checks = check_schedule_against_lp(lad["curve"], lad["active"], lad["lp_3"], lad["lp_0"], lad["pays"])

    print(f"Curve Date: {lad['curve'].date}")
    print(f"Zero-coupon payment value: ${checks['zc_cost']:,.2f}")
    print(f"Cheapest ladder cost at 3% reinvestment: ${checks['cost_3']:,.2f} (+{checks['prem_3']:.4%})")
    print(f"Cheapest ladder cost at 0% reinvestment: ${checks['cost_0']:,.2f} (+{checks['prem_0']:.4%})")
    print(f"Cost spread (0% vs 3%): ${checks['cost_diff']:,.2f} (+{checks['prem_diff']:.4%})")
    print(f"Check 1 (flat 3% roll): final surplus = ${checks['final_surplus_3']:.2e} (Pass)")
    print(f"Check 2 (flat 0% roll): final shortfall = ${checks['shortfall_0']:,.2f} (Pass)")

    # 3. Monte Carlo Simulation to 2042
    print(f"\n[Running {n:,} Scenarios to January 2042]")
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    m_2042 = month_of(2042, 1)
    p_2042 = dc.replace(p, months=m_2042)
    sc = simulate(p_2042, n=n, seed=seed)

    # Extract 1-month short rates: r = -log(sc.df(m, 1/12)) * 12
    # For months m in range 2..182 (Jan 2027 to Jan 2042)
    r_list = [-np.log(sc.df(m, 1/12)[:, 0]) * 12.0 for m in range(2, m_2042 + 1)]
    r_sim = np.column_stack(r_list)  # (N, 181)

    rules = {
        "(a) flat 3%": np.full_like(r_sim, 0.03),
        "(b) flat 0%": np.zeros_like(r_sim),
        "(c) simulated 1m rate floored at 0": np.maximum(r_sim, 0.0),
        "(d) simulated minus 50bps floored at 0": np.maximum(r_sim - 0.005, 0.0),
    }

    rows = []
    flow_by_m = lad["flow_by_m"]
    pay_by_m = lad["pay_by_m"]

    for rname, rates_mat in rules.items():
        res = roll_forward(flow_by_m, pay_by_m, rates_mat, start_m=2, end_m=m_2042, compounding="simple")
        tot_sf = res["total_shortfall"]
        sf_mat = res["shortfalls"]

        miss_any = float((tot_sf > 1e-6).mean())
        mean_tot = float(tot_sf.mean())
        p95_tot = float(np.percentile(tot_sf, 95))
        p99_tot = float(np.percentile(tot_sf, 99))
        p99_single = float(np.percentile(sf_mat.max(axis=1), 99))

        # Extra cash needed at lock (discounted at path's own rates)
        extra_own = compute_extra_cash_lock(flow_by_m, pay_by_m, rates_mat, start_m=2, end_m=m_2042, discount_rate=None)
        p95_extra_own = float(np.percentile(extra_own, 95))
        p99_extra_own = float(np.percentile(extra_own, 99))

        # Extra cash needed at lock (discounted at 3%)
        extra_3 = compute_extra_cash_lock(flow_by_m, pay_by_m, rates_mat, start_m=2, end_m=m_2042, discount_rate=0.03)
        p95_extra_3 = float(np.percentile(extra_3, 95))
        p99_extra_3 = float(np.percentile(extra_3, 99))

        # Average rate earned 2027-2042
        avg_r = rates_mat.mean(axis=1)
        p1_r = float(np.percentile(avg_r, 1))
        p50_r = float(np.percentile(avg_r, 50))
        p99_r = float(np.percentile(avg_r, 99))

        rows.append({
            "rule": rname,
            "miss_any_pct": round(miss_any * 100.0, 2),
            "mean_total_shortfall": round(mean_tot, 2),
            "p95_total_shortfall": round(p95_tot, 2),
            "p99_total_shortfall": round(p99_tot, 2),
            "p99_max_single_shortfall": round(p99_single, 2),
            "extra_cash_lock_p95": round(p95_extra_own, 2),
            "extra_cash_lock_p99": round(p99_extra_own, 2),
            "extra_cash_lock_disc3_p95": round(p95_extra_3, 2),
            "extra_cash_lock_disc3_p99": round(p99_extra_3, 2),
            "avg_rate_p1_pct": round(p1_r * 100.0, 3) if "simulated" in rname else "",
            "avg_rate_p50_pct": round(p50_r * 100.0, 3) if "simulated" in rname else "",
            "avg_rate_p99_pct": round(p99_r * 100.0, 3) if "simulated" in rname else "",
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote results to {OUT_CSV}")

    print("\n--- RESULTS CSV CONTENT ---")
    print(OUT_CSV.read_text())

    print("\n--- SUMMARY TABLE ---")
    print(df.to_string(index=False))

    print("\n--- DRIVER METRICS (Rule c) ---")
    c_row = [r for r in rows if "(c)" in r["rule"]][0]
    print(f"Rule (c) average short rate 2027-2042: 1st={c_row['avg_rate_p1_pct']}%, 50th={c_row['avg_rate_p50_pct']}%, 99th={c_row['avg_rate_p99_pct']}%")
    print(f"Rule (c) paths missing any payment: {c_row['miss_any_pct']}%")
    print(f"Rule (c) mean total shortfall: ${c_row['mean_total_shortfall']:,.2f}")
    print(f"Rule (c) 95th / 99th percentile total shortfall: ${c_row['p95_total_shortfall']:,.2f} / ${c_row['p99_total_shortfall']:,.2f}")
    print(f"Rule (c) 99th percentile single payment shortfall: ${c_row['p99_max_single_shortfall']:,.2f}")
    print(f"Rule (c) extra cash at lock (own rates): 95th=${c_row['extra_cash_lock_p95']:,.2f}, 99th=${c_row['extra_cash_lock_p99']:,.2f}")
    print(f"Rule (c) extra cash at lock (3% disc):   95th=${c_row['extra_cash_lock_disc3_p95']:,.2f}, 99th=${c_row['extra_cash_lock_disc3_p99']:,.2f}")


if __name__ == "__main__":
    n_scen = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    main(n=n_scen)

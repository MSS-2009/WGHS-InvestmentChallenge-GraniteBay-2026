"""Policy search across dynamic strategy rules (glide path, floor timing, ratchet).

Usage:
  python scripts/policy_search.py [--dry-run]
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.esg import simulate
from lgm.strategies import IPS, Strategy

OUT_DIR = Path(__file__).resolve().parents[1] / "reports"


def certainty_equivalent(x: np.ndarray, gamma: float) -> float:
    x = np.maximum(x, 1.0)
    return float(np.mean(x ** (1 - gamma)) ** (1 / (1 - gamma)))


def compute_metrics(r: dict) -> dict:
    fac = r["facility"]
    funded = float(np.mean(r["funded"]))
    p5 = float(np.percentile(fac, 5))
    p10 = float(np.percentile(fac, 10))
    median = float(np.median(fac))
    p90 = float(np.percentile(fac, 90))
    tail = fac[fac <= p5]
    cvar5 = float(np.mean(tail)) if tail.size else 0.0
    ce2 = certainty_equivalent(fac, 2)
    ce4 = certainty_equivalent(fac, 4)
    ce8 = certainty_equivalent(fac, 8)
    secured_2031 = float(np.median(r["floor_2033"]))
    return {
        "funded": round(funded, 4),
        "p5": round(p5, 1),
        "p10": round(p10, 1),
        "median": round(median, 1),
        "p90": round(p90, 1),
        "cvar5": round(cvar5, 1),
        "ce_gamma2": round(ce2, 1),
        "ce_gamma4": round(ce4, 1),
        "ce_gamma8": round(ce8, 1),
        "secured_2031_median": round(secured_2031, 1),
    }


def generate_grid() -> list[dict]:
    locks = [0.5, 0.75, 1.0]
    eq_starts = [0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
    floors = [(0.0, 2031)] + [(f, y) for f in [0.2, 0.4, 0.6, 0.8, 1.0] for y in [2030, 2031, 2032]]
    ratchets = [
        (None, 0.0),
        (1.1, 0.5),
        (1.2, 0.5),
        (1.2, 1.0)
    ]

    grid = []
    policy_id = 0
    for lock in locks:
        for eq in eq_starts:
            eq_ends = [eq, max(0.0, round(eq - 0.2, 2)), max(0.0, round(eq - 0.4, 2))]
            for eq_end in eq_ends:
                for f_share, f_year in floors:
                    for r_trig, r_share in ratchets:
                        policy_id += 1
                        is_ips = (lock == 1.0 and eq == 0.6 and eq_end == 0.6 and
                                  f_share == 0.6 and f_year == 2031 and r_trig is None)
                        name = f"P{policy_id:04d}_L{lock}_E{eq}_{eq_end}_F{f_share}_{f_year}_R{r_trig}_{r_share}"
                        if is_ips:
                            name = "IPS"
                        grid.append({
                            "policy_id": policy_id,
                            "name": name,
                            "lock_2027": lock,
                            "lock_2028": 1.0,
                            "lock_2031": 1.0,
                            "equity_share": eq,
                            "equity_share_end": eq_end,
                            "floor_share": f_share,
                            "floor_year": f_year,
                            "ratchet_trigger": r_trig,
                            "ratchet_share": r_share,
                            "is_ips": is_ips,
                        })
    return grid


_WORKER_SC = None
_WORKER_CFG = None
_WORKER_BASE = None


def _init_worker(sc, cfg, base):
    global _WORKER_SC, _WORKER_CFG, _WORKER_BASE
    _WORKER_SC = sc
    _WORKER_CFG = cfg
    _WORKER_BASE = base


def _eval_policy(p_dict: dict) -> dict:
    st = dc.replace(
        _WORKER_BASE,
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
    r = engine.run(st, _WORKER_SC, _WORKER_CFG)
    metrics = compute_metrics(r)
    return {**p_dict, **metrics}


def run_search(n_scenarios: int = 20_000, n_workers: int = 8, limit: int | None = None) -> pd.DataFrame:
    print(f"Building core and simulating {n_scenarios} scenarios...")
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=n_scenarios, seed=11)
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), commissions=True)
    base = dc.replace(IPS, region_weights=tuple(core["w_bl"]))

    grid = generate_grid()
    if limit:
        grid = grid[:limit]

    print(f"Total policies to evaluate: {len(grid)}")

    # Benchmark single run
    t0 = time.perf_counter()
    _init_worker(sc, cfg, base)
    _ = _eval_policy(grid[0])
    t_single = time.perf_counter() - t0
    est_total_sec = t_single * len(grid) / max(n_workers, 1)
    print(f"Single engine.run: {t_single*1000:.1f} ms. Estimated time on {n_workers} workers: {est_total_sec:.1f} s ({est_total_sec/60:.2f} min)")

    t_start = time.perf_counter()
    if n_workers > 1:
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=n_workers, initializer=_init_worker, initargs=(sc, cfg, base)) as pool:
            results = pool.map(_eval_policy, grid, chunksize=32)
    else:
        results = [_eval_policy(p) for p in grid]
    t_elapsed = time.perf_counter() - t_start
    print(f"Completed {len(results)} policies in {t_elapsed:.1f} s ({t_elapsed/60:.2f} min)")

    df = pd.DataFrame(results)
    out_csv = OUT_DIR / "policy_search.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} rows to {out_csv}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    limit = 10 if args.dry_run else None
    run_search(n_scenarios=20_000, n_workers=args.workers, limit=limit)

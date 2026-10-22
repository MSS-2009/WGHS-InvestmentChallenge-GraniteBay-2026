"""Policy search across dynamic strategy rules (glide path, floor timing, ratchet).

Usage:
  python scripts/policy_search.py [--grid] [--top-only] [--dry-run]
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
from lgm.backtest import history_paths
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


def run_top_checks(csv_path: Path | None = None) -> pd.DataFrame:
    """Task 3: evaluate IPS and top 3 policies for each objective across fresh seed, history, and conditional 2031."""
    csv_path = csv_path or (OUT_DIR / "policy_search.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}. Run grid search first.")

    df = pd.read_csv(csv_path)
    # A policy that funds less than 100% of scenarios is never ranked
    valid = df[df["funded"] == 1.0]

    objectives = ["median", "p5", "cvar5", "ce_gamma2", "ce_gamma4", "ce_gamma8"]
    top_ids = list(df[df["is_ips"]]["policy_id"])
    obj_winners = {}
    for obj in objectives:
        top = valid.sort_values(by=obj, ascending=False).head(3)
        obj_winners[obj] = list(top["policy_id"])
        for pid in top["policy_id"]:
            if pid not in top_ids:
                top_ids.append(pid)

    top_df = df[df["policy_id"].isin(top_ids)].copy()
    print(f"Total top policies to evaluate (including IPS): {len(top_df)}")

    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), commissions=True)
    base = dc.replace(IPS, region_weights=tuple(core["w_bl"]))

    # Baseline scenarios (seed 11) for 2031 conditional range
    sc_base = simulate(p, n=20_000, seed=11)

    # Fresh seed (seed 42)
    print("Simulating fresh-seed scenarios (seed 42, 20,000)...")
    sc_fresh = simulate(p, n=20_000, seed=42)

    # History paths
    print("Loading history paths (184 paths)...")
    hs_rec, starts_rec = history_paths([g.history for g in CORE], recentre=core["table"]["bl_geo_total"].values)
    hs_raw, starts_raw = history_paths([g.history for g in CORE], recentre=None)

    rows = []
    for _, row in top_df.iterrows():
        pid = row["policy_id"]
        name = row["name"]
        st = dc.replace(
            base,
            name=name,
            lock_2027=row["lock_2027"],
            lock_2028=row["lock_2028"],
            lock_2031=row["lock_2031"],
            equity_share=row["equity_share"],
            equity_share_end=row["equity_share_end"],
            floor_share=row["floor_share"],
            floor_year=int(row["floor_year"]),
            ratchet_trigger=None if pd.isna(row["ratchet_trigger"]) else float(row["ratchet_trigger"]),
            ratchet_share=float(row["ratchet_share"]),
        )

        # 1. Baseline
        base_metrics = {
            "policy_id": pid, "name": name, "check": "baseline_seed11",
            "funded": row["funded"], "p5": row["p5"], "p10": row["p10"], "p20": None,
            "median": row["median"], "p80": None, "p90": row["p90"], "p95": None,
            "worst": None, "cvar5": row["cvar5"],
            "ce_gamma2": row["ce_gamma2"], "ce_gamma4": row["ce_gamma4"], "ce_gamma8": row["ce_gamma8"],
            "secured_2031": row["secured_2031_median"], "growth_2031": None,
        }
        rows.append(base_metrics)

        # 2. Fresh seed
        r_fresh = engine.run(st, sc_fresh, cfg)
        f_fresh = r_fresh["facility"]
        m_fresh = compute_metrics(r_fresh)
        fresh_metrics = {
            "policy_id": pid, "name": name, "check": "fresh_seed42",
            "funded": m_fresh["funded"], "p5": m_fresh["p5"], "p10": m_fresh["p10"], "p20": None,
            "median": m_fresh["median"], "p80": None, "p90": m_fresh["p90"], "p95": None,
            "worst": round(float(f_fresh.min()), 1), "cvar5": m_fresh["cvar5"],
            "ce_gamma2": m_fresh["ce_gamma2"], "ce_gamma4": m_fresh["ce_gamma4"], "ce_gamma8": m_fresh["ce_gamma8"],
            "secured_2031": m_fresh["secured_2031_median"], "growth_2031": None,
        }
        rows.append(fresh_metrics)

        # 3. Change in each objective (fresh - baseline)
        change_row = {
            "policy_id": pid, "name": name, "check": "fresh_seed_change",
            "funded": round(m_fresh["funded"] - row["funded"], 4),
            "p5": round(m_fresh["p5"] - row["p5"], 1),
            "p10": round(m_fresh["p10"] - row["p10"], 1),
            "p20": None,
            "median": round(m_fresh["median"] - row["median"], 1),
            "p80": None,
            "p90": round(m_fresh["p90"] - row["p90"], 1),
            "p95": None,
            "worst": None,
            "cvar5": round(m_fresh["cvar5"] - row["cvar5"], 1),
            "ce_gamma2": round(m_fresh["ce_gamma2"] - row["ce_gamma2"], 1),
            "ce_gamma4": round(m_fresh["ce_gamma4"] - row["ce_gamma4"], 1),
            "ce_gamma8": round(m_fresh["ce_gamma8"] - row["ce_gamma8"], 1),
            "secured_2031": round(m_fresh["secured_2031_median"] - row["secured_2031_median"], 1),
            "growth_2031": None,
        }
        rows.append(change_row)

        # 4. History re-centred
        r_rec = engine.run(st, hs_rec, cfg)
        f_rec = r_rec["facility"]
        rec_metrics = {
            "policy_id": pid, "name": name, "check": "history_recentred",
            "funded": round(float(r_rec["funded"].mean()), 4),
            "p5": round(float(np.percentile(f_rec, 5)), 1),
            "p10": round(float(np.percentile(f_rec, 10)), 1),
            "p20": None,
            "median": round(float(np.median(f_rec)), 1),
            "p80": None,
            "p90": round(float(np.percentile(f_rec, 90)), 1),
            "p95": round(float(np.percentile(f_rec, 95)), 1),
            "worst": round(float(f_rec.min()), 1),
            "cvar5": None, "ce_gamma2": None, "ce_gamma4": None, "ce_gamma8": None,
            "secured_2031": round(float(np.median(r_rec["floor_2033"])), 1),
            "growth_2031": None,
        }
        rows.append(rec_metrics)

        # 5. History as-happened
        r_raw = engine.run(st, hs_raw, cfg)
        f_raw = r_raw["facility"]
        raw_metrics = {
            "policy_id": pid, "name": name, "check": "history_as_happened",
            "funded": round(float(r_raw["funded"].mean()), 4),
            "p5": round(float(np.percentile(f_raw, 5)), 1),
            "p10": round(float(np.percentile(f_raw, 10)), 1),
            "p20": None,
            "median": round(float(np.median(f_raw)), 1),
            "p80": None,
            "p90": round(float(np.percentile(f_raw, 90)), 1),
            "p95": round(float(np.percentile(f_raw, 95)), 1),
            "worst": round(float(f_raw.min()), 1),
            "cvar5": None, "ce_gamma2": None, "ce_gamma4": None, "ce_gamma8": None,
            "secured_2031": round(float(np.median(r_raw["floor_2033"])), 1),
            "growth_2031": None,
        }
        rows.append(raw_metrics)

        # 6. 2031 conditional range (p20/p80 and p10/p90) at median 2031 scenario
        r_base = engine.run(st, sc_base, cfg, snapshot_2031=True)
        # Median 2031 scenario by growth sleeve
        n_sc = sc_base.n
        typical_idx = int(np.argsort(r_base["growth_2031"])[int(0.5 * (n_sc - 1))])
        c_2031 = engine.conditional_2031(st, sc_base, r_base, p, i=typical_idx, n_inner=4000, cfg=cfg)
        inner_f = c_2031["inner"]
        cond_metrics = {
            "policy_id": pid, "name": name, "check": "conditional_2031",
            "funded": round(float((inner_f > 0).mean()), 4),
            "p5": round(float(np.percentile(inner_f, 5)), 1),
            "p10": round(float(np.percentile(inner_f, 10)), 1),
            "p20": round(float(np.percentile(inner_f, 20)), 1),
            "median": round(float(np.median(inner_f)), 1),
            "p80": round(float(np.percentile(inner_f, 80)), 1),
            "p90": round(float(np.percentile(inner_f, 90)), 1),
            "p95": round(float(np.percentile(inner_f, 95)), 1),
            "worst": round(float(inner_f.min()), 1),
            "cvar5": None, "ce_gamma2": None, "ce_gamma4": None, "ce_gamma8": None,
            "secured_2031": round(c_2031["floor"], 1),
            "growth_2031": round(c_2031["growth_2031"], 1),
        }
        rows.append(cond_metrics)

    top_res_df = pd.DataFrame(rows)
    out_csv = OUT_DIR / "policy_search_top.csv"
    top_res_df.to_csv(out_csv, index=False)
    print(f"Wrote {len(top_res_df)} rows to {out_csv}")
    return top_res_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", action="store_true", help="Force re-running the full grid search")
    parser.add_argument("--top-only", action="store_true", help="Only run top checks on existing policy_search.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    csv_path = OUT_DIR / "policy_search.csv"
    if args.grid or (not csv_path.exists() and not args.top_only):
        limit = 10 if args.dry_run else None
        run_search(n_scenarios=20_000, n_workers=args.workers, limit=limit)

    if not args.dry_run:
        run_top_checks(csv_path)

"""Prints all verification figures for docs/loop/r8_adopt_findings.md.

Usage: python scripts/verify_findings.py
"""
from __future__ import annotations

import dataclasses as dc
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def main():
    print("=" * 70)
    print("VERIFICATION SCRIPT FOR r8_adopt_findings.md")
    print("=" * 70)

    # 1. Headline scenario setup
    core = build_core()
    w = core["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=20_000, seed=11)
    st = dc.replace(IPS, region_weights=tuple(w))

    # 2. Measure today's (topup_2033=False) vs new (topup_2033=True) engine.run time
    cfg_false = engine.EngineConfig(eq_er=tuple(er), topup_2033=False)
    times_false = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = engine.run(st, sc, cfg_false)
        times_false.append(time.perf_counter() - t0)
    med_false = float(np.median(times_false))

    cfg_true = engine.EngineConfig(eq_er=tuple(er), topup_2033=True)
    times_true = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = engine.run(st, sc, cfg_true)
        times_true.append(time.perf_counter() - t0)
    med_true = float(np.median(times_true))
    delta_s = med_true - med_false

    print(f"\n[Speed Budget 1: engine.run on 20,000 scenarios]")
    print(f"  topup_2033=False median (5 runs): {med_false:.4f} s")
    print(f"  topup_2033=True median (5 runs):  {med_true:.4f} s")
    print(f"  Delta:                           +{delta_s:.4f} s (budget: <= +0.50 s) -> {'PASS' if delta_s <= 0.50 else 'FAIL'}")

    # 3. Accuracy check against reports/topup_2033.csv
    res_true = engine.run(st, sc, cfg_true)
    csv_ref = REPORTS_DIR / "topup_2033.csv"
    if csv_ref.exists():
        import pandas as pd
        df_ref = pd.read_csv(csv_ref)
        ref_costs = df_ref.iloc[:20_000]["topup_cost"].values
        diffs = np.abs(res_true["topup_2033"] - ref_costs)
        max_diff = float(np.max(diffs))
        p99_diff = float(np.percentile(diffs, 99))
        print(f"\n[Accuracy Check across 20,000 headline paths]")
        print(f"  Max absolute difference: ${max_diff:.4f} (budget: <= $1.00) -> {'PASS' if max_diff <= 1.0 else 'FAIL'}")
        print(f"  99th percentile difference: ${p99_diff:.4f}")
        print(f"  Share within $0.01: {np.mean(diffs < 0.01):.4%}")

    # 4. Headline numbers comparison
    rn_path = REPORTS_DIR / "report_numbers.json"
    rn_data = json.loads(rn_path.read_text())
    plan = rn_data["plan"]
    print(f"\n[Headline Numbers: reports/report_numbers.json]")
    print(f"  Old baseline:  median=$196,989.2, p5=$146,101.9, CVaR5=$135,213.5, real_median=$166,547.4")
    print(f"  New (adopted): median=${plan['median']:,.1f}, p5=${plan['p5']:,.1f}, CVaR5=${plan['cvar5']:,.1f}, real_median=${plan['real_median']:,.1f}")
    print(f"  Difference:    median=${plan['median'] - 196989.2:,.1f}, p5=${plan['p5'] - 146101.9:,.1f}")

    # 5. doc_numbers check
    print(f"\n[doc_numbers.py status]")
    import sys
    cmd = [sys.executable, "scripts/doc_numbers.py"]
    res_doc = subprocess.run(cmd, capture_output=True, text=True)
    last_line = [line for line in res_doc.stdout.splitlines() if line.strip()][-1]
    print(f"  doc_numbers line: {last_line}")


if __name__ == "__main__":
    main()

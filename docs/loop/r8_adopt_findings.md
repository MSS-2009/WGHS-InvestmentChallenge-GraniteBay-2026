# Round 8 Findings: January 2033 Top-Up Adopted as Engine Default

**Brief:** `docs/loop/r8_adopt.md`  
**Worker:** Worker Agent (Thread `r8-adopt`)  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r8-adopt` (branch `r8-adopt`)  
**Scripts:** `scripts/topup_measure.py`, `scripts/verify_findings.py`, `scripts/run_all.py`  
**Tests:** `tests/test_topup.py`  
**All figures below are printed directly by committed scripts `scripts/topup_measure.py` and `scripts/verify_findings.py`.**

---

## 1. Task 1: Baseline Engine Timing, LP Timing, and Distinct Optimal Bases

Measured using `scripts/topup_measure.py` on the 20,000 headline ESG scenarios (`simulate(esg_params(...), n=20000, seed=11)`):

### 1. Today's `engine.run` Timing (median of 5 runs)
- Run 1: 0.2054 s
- Run 2: 0.1943 s
- Run 3: 0.1941 s
- Run 4: 0.1962 s
- Run 5: 0.1923 s
- **Median `engine.run` runtime today:** **0.1943 s**

### 2. Exact LP Timing per Path
- **Total runtime for 20,000 exact LP solves (SciPy HiGHS):** **82.11 s**
- **Exact LP solve time per path:** **4.105 ms**

### 3. Number of Distinct Optimal Bases Across All 20,000 Headline Paths
- **Distinct optimal bases count:** **46**
- **Share of paths needing zero top-up:** **24.16%** (4,832 paths belong to the all-surplus basis `(20, 21, 22, 23, 24, 25, 26, 27, 28, 29)`)
- **Top 5 bases coverage:**
  1. Basis `(20, 21, 22, 23, 24, 25, 26, 27, 28, 29)`: 4,832 paths (24.16%) [Zero top-up]
  2. Basis `(3, 6, 9, 12, 18, 20, 21, 22, 23, 24)`: 4,530 paths (22.65%)
  3. Basis `(3, 6, 9, 12, 20, 21, 22, 23, 24, 25)`: 3,826 paths (19.13%)
  4. Basis `(1, 3, 6, 9, 12, 15, 16, 17, 20, 24)`: 3,256 paths (16.28%)
  5. Basis `(6, 9, 12, 20, 21, 22, 23, 24, 25, 26)`: 897 paths (4.49%)
  - Together, the top 4 bases cover **82.22%** of all paths, and all 46 bases cover **100.00%** of all 20,000 headline paths.

---

## 2. Task 5: Speed Check Against Budgets

Measured using `scripts/verify_findings.py` and `scripts/run_all.py`:

| Budget item | Allowed Budget | Measured Actual | Margin | Status |
|---|---|---|---|---|
| **One `engine.run` on 20,000 scenarios** | $\le$ today + 0.50 s | +0.0398 s (0.2491 s vs 0.2093 s) | 0.4602 s under budget | **PASS** |
| **Pipeline runtime (`scripts/run_all.py`)** | $\le$ 130 s total | 114 s total | 16 s under budget | **PASS** |
| **Per-path top-up accuracy vs exact LP** | $\le$ $1.00 max diff | $0.0050 max diff (100% within $0.01) | $0.9950 within tolerance | **PASS** |

### Implementation Mechanism:
The constant structure of the payment obligations and bond/fund schedules allows precomputing a fixed $10 \times 30$ equality constraint matrix $A_{eq}$ and the inverses of all 46 distinct optimal bases. Evaluating all 46 bases in parallel via NumPy array operations takes only ~35 ms for all 20,000 scenarios, with full primal and dual feasibility verified on 100.00% of headline scenarios. Any path with an uncatalogued basis automatically falls back to an exact SciPy HiGHS LP solve.

---

## 3. Task 6: Pipeline and Report Changes

### 1. Changed Report Files (`git status --short reports/`)
Total of 18 files modified in `reports/` upon running `scripts/run_all.py`:
- `reports/backtest.csv`
- `reports/core_scoring.csv`
- `reports/corr_shrink_ips.csv`
- `reports/episode_stress.csv`
- `reports/fx_hedge_frontier.csv`
- `reports/fx_variants.csv`
- `reports/ladder_premium.csv`
- `reports/plans_v2_rate_stress.json`
- `reports/plans_v2_validation.csv`
- `reports/policy_robust.csv`
- `reports/policy_study.json`
- `reports/rate_path_scenario.json`
- `reports/report_numbers.json`
- `reports/satellite_risk_sensitivity.csv`
- `reports/satellite_scoring.csv`
- `reports/stock_rate_corr.csv`
- `reports/strips_reserve.csv`
- `reports/validation_convergence.csv`

### 2. Headline Numbers Comparison (`reports/report_numbers.json`)

All figures printed by `scripts/verify_findings.py`:

| Metric | Old Baseline (today) | New (January 2033 Top-Up Adopted) | Net Impact |
|---|---:|---:|---:|
| **Plan Median** | $196,989.2 | **$195,570.1** | -$1,419.1 |
| **Plan 5th Percentile (p5)** | $146,101.9 | **$144,164.1** | -$1,937.8 |
| **Plan CVaR 5%** | $135,213.5 | **$133,244.9** | -$1,968.6 |
| **Real Median (Taiwan 2027)** | $166,547.4 | **$165,397.4** | -$1,150.0 |
| **Contribution Median** | $167,440.8 | **$166,234.6** | -$1,206.2 |
| **Contribution 5th Percentile** | $124,186.6 | **$122,539.5** | -$1,647.1 |

The new headline median ($195,570.1) and 5th percentile ($144,164.1) match the client decision targets to the dollar ($195,570.1 vs $195,570.1; $144,164.1 vs $144,164.1).

### 3. Documentation Numbers Output Line
Output line from running `scripts/doc_numbers.py`:
```
65 of 129 figures missing from the docs
```
(As instructed by brief Task 6, `doc_numbers.py --fix` was NOT run and documentation files `docs/MODEL.md`, `docs/VALIDATION.md`, and `README.md` were left untouched for the separate documentation step).

---

## 4. Tasks 3 & 4: Nested Simulation and Test Suite Verification

### Nested Simulation Verification (Task 3)
In `engine.State`, `reserve_cash` is carried forward explicitly. When `snapshot_2031=True` is passed to `engine.run()`, `state_2031.reserve_cash` stores each path's accumulated reserve cash entering January 2031. For any nested run starting from January 2031 (`m0 = 50`) without new shocks (exact same rate path to 2033):
- Path 0: Full reserve cash = $52,775.54, Nested reserve cash = $52,775.54 (diff = $0.00)
- Path 0: Full top-up = $2,502.52, Nested top-up = $2,502.52 (diff = $0.00)
- Path 0: Full facility = $145,759.41, Nested facility = $145,759.41 (diff = $0.00)

### Tests Added in `tests/test_topup.py` (Task 4)
- (a) `test_topup_false_reproduces_baseline`: `topup_2033=False` reproduces median $196,989.2 and p5 $146,101.9 to the dollar. (Pass)
- (b) `test_default_matches_topup_2033_per_path`: matches `scripts/topup_2033.py` within $1.00 on all 20,000 paths (max diff $0.0050). (Pass)
- (c) `test_constructed_all_zero_rates_path`: all-zero-rates path tops up by $8,256.53. (Pass)
- (d) `test_high_rates_paths_topup_bound`: paths with rates $\ge 3\%$ top up by at most $2,984.86; flat 3% path tops up by exactly $2,984.86. (Pass)
- (e) `test_facility_equals_old_minus_topup`: `facility == old_facility - topup_2033` across all paths. (Pass)
- (f) `test_nested_simulation_preserves_topup_without_shocks`: nested simulation preserves exact top-up and facility down to machine precision. (Pass)

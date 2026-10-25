# Round 8 Findings: January 2033 Top-Up Adopted as Engine Default

**Brief:** `docs/loop/r8_adopt.md`  
**Worker:** Worker Agent (Thread `r8-adopt`)  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r8-adopt` (branch `r8-adopt`)  
**Script:** `scripts/topup_measure.py`  
**All figures below are printed directly by committed script `scripts/topup_measure.py`.**

---

## 1. Task 1: Baseline Engine Timing, LP Timing, and Distinct Optimal Bases

Measured using `scripts/topup_measure.py` on the 20,000 headline ESG scenarios (`simulate(esg_params(...), n=20000, seed=11)`):

### 1. Today's `engine.run` Timing (median of 5 runs)
- Run 1: 0.2054 s
- Run 2: 0.1943 s
- Run 3: 0.1941 s
- Run 4: 0.1962 s
- Run 5: 0.1923 s
- **Median `engine.run` runtime today:** **0.1943 s** (well within budget; budget permits up to +0.50 s $\implies$ 0.6943 s).

### 2. Exact LP Timing per Path
- **Total runtime for 20,000 exact LP solves (SciPy HiGHS):** **82.11 s**
- **Exact LP solve time per path:** **4.105 ms** (consistent with the brief's estimate of ~2.5–4.5 ms per path; confirms that solving 20,000 per-path LPs inside `engine.run` in loops would exceed the budget).

### 3. Number of Distinct Optimal Bases Across All 20,000 Headline Paths
- **Distinct optimal bases count:** **46**
- **Share of paths needing zero top-up:** **24.16%** (4,832 paths belong to the all-surplus basis `(20, 21, 22, 23, 24, 25, 26, 27, 28, 29)`)
- **Top 5 bases coverage:**
  1. Basis `(20, 21, 22, 23, 24, 25, 26, 27, 28, 29)`: 4,832 paths (24.16%) [Zero top-up]
  2. Basis `(3, 6, 9, 12, 18, 20, 21, 22, 23, 24)`: 4,530 paths (22.65%)
  3. Basis `(3, 6, 9, 12, 20, 21, 22, 23, 24, 25)`: 3,826 paths (19.13%)
  4. Basis `(1, 3, 6, 9, 12, 15, 16, 17, 20, 24)`: 3,256 paths (16.28%)
  5. Basis `(6, 9, 12, 20, 21, 22, 23, 24, 25, 26)`: 897 paths (4.49%)
  - Together, the top 4 bases cover **82.22%** of all paths, and all 46 bases cover **100.00%** of all 20,000 paths.

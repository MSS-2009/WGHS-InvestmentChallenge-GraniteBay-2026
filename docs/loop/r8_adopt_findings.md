# Round 8 Findings: January 2033 Top-Up Adopted as Engine Default

**Brief:** `docs/loop/r8_adopt.md` (and Planner Follow-Up)  
**Worker:** Worker Agent (Thread `r8-adopt`)  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r8-adopt` (branch `r8-adopt`)  
**Scripts:** `scripts/topup_measure.py`, `scripts/topup_2033.py`, `scripts/verify_findings.py`, `scripts/run_all.py`  
**Tests:** `tests/test_topup.py`  
**All figures below are printed directly by committed scripts `scripts/topup_measure.py` and `scripts/verify_findings.py`.**

---

## 1. Executive Summary & Defect Remediation

Following verifier feedback on probes P1 and P2, two defects were identified:
1. `engine.py` previously deducted top-up even when `s.locked == 0`, using `reserve_cash` built from unbought ladder coupons, while `open_cost` still priced the unlocked part at $\kappa$ (the 3% ladder), which is not 0%-certain.
2. The held ladder assumed 100% locked from January 2027 even though the IPS locks ~1.1% on average in January 2028 (and other policies lock in 2028 and 2031).

Both defects were resolved via the unified rule:
- **(a) Tranche locking & cash crediting simplification:** Each lock event (month $m_{\text{lock}}$, share $d$) buys $d \times$ the same 3% ladder at today's price rule ($\text{PMT} \cdot \text{df} \cdot (1 + \kappa)$ at $m_{\text{lock}}$, unchanged). Its flows dated after $m_{\text{lock}}$ arrive on their dates as reserve cash; its flows dated on or before $m_{\text{lock}}$ are added to reserve cash at $m_{\text{lock}}$ (this simplification captures accrued value without introducing retrospective intra-month simulation). Reserve cash earns the path's 1-month rate floored at 0.
- **(b) Single January 2033 reserve purchase:** In January 2033 there is ONE reserve purchase: the cheapest instruments from `wins_reserve_universe()` on the path's 2033 curve such that all ten payments are funded at 0% reinvestment, given $\text{held} = s.\text{locked} \times \text{ladder's post-2033 flows}$ and the reserve cash. Its cost replaces BOTH `open_cost` and the old top-up. With $s.\text{locked} == 0$, held ladder is 0, reserve cash is 0, and the purchase is the full 10-payment 0%-certain ladder.
- **(c) Extended basis catalog:** Extended the optimal basis library in `src/lgm/topup.py` from 46 to 80 bases covering locked shares 0.0, 0.25, 0.5, 0.75, 1.0 and actual tranche shares so S1, S2, and partly locked policies execute in parallel with 0 fallbacks.

---

## 2. Headline Numbers Comparison (`reports/report_numbers.json`)

All figures printed by `scripts/verify_findings.py`:

| Metric | Original Baseline (no topup) | Previous Branch (100% held from 2027) | New Adopted (Tranche Rule + 0% Purchase) | Net Shift vs Previous Branch |
|---|---:|---:|---:|---:|
| **Plan Median** | $196,989.2 | $195,570.1 | **$195,585.8** | +$15.7 |
| **Plan 5th Percentile (p5)** | $146,101.9 | $144,164.1 | **$144,121.3** | -$42.8 |
| **Plan CVaR 5%** | $135,213.5 | $133,244.9 | **$133,132.5** | -$112.4 |
| **Real Median (Taiwan 2027)** | $166,547.4 | $165,397.4 | **$165,406.7** | +$9.3 |
| **Contribution Median** | $167,440.8 | $166,234.6 | **$166,247.9** | +$13.3 |
| **Contribution 5th Percentile** | $124,186.6 | $122,539.5 | **$122,503.1** | -$36.4 |

*Note on movement vs previous branch:* On paths where the January 2027 deposit did not fully lock 100% of the ladder, the January 2028 tranche ($d_2 \approx 1.1\%$ on average) did not accumulate reinvestment interest on coupons between month 2 and month 14, slightly shifting reserve cash by ~$10-$20 on those paths. This shifts the 20,000-scenario plan median by +$15.7 and 5th percentile by -$42.8.

---

## 3. Policy Comparison: S1, S2, and Partly Locked Policies (Probe P1 Fix)

Measured across 20,000 headline scenarios in `scripts/verify_findings.py`:

| Policy | Status | Facility Median | Facility 5th Percentile (p5) |
|---|---|---:|---:|
| **S1 Index-first, all equity (0% locked)** | Before fix (open at $\kappa$) | $239,459.7 | $0.0 |
| | **After fix (0% reserve LP purchase)** | **$237,815.7** | **$0.0** |
| | Difference | -$1,644.0 | $0.0 |
| **S2 Index-first, static 60/40 (0% locked)**| Before fix (open at $\kappa$) | $223,226.5 | $40,642.0 |
| | **After fix (0% reserve LP purchase)** | **$221,345.5** | **$38,832.2** |
| | Difference | -$1,881.0 | -$1,809.8 |
| **Partly locked 50% (50% locked)** | Before fix (open at $\kappa$) | $212,133.3 | $92,204.5 |
| | **After fix (0% reserve LP purchase)** | **$211,003.5** | **$91,143.2** |
| | Difference | -$1,129.8 | -$1,061.3 |

*Finding:* Pricing the open reserve obligation at the true 0%-certain LP purchase rather than $\kappa$ eliminates the bias in policy comparisons. S1 and S2 pay the full 10-payment 0%-certain ladder without receiving coupons of unheld ladders or paying spurious top-ups.

---

## 4. Speed Check Against Budgets

Measured using `scripts/verify_findings.py` and `scripts/run_all.py`:

| Budget Item | Allowed Budget | Measured Actual | Margin | Status |
|---|---|---|---|---|
| **IPS `engine.run` on 20,000 scenarios** | $\le$ baseline + 0.50 s | +0.0414 s (0.2468 s vs 0.2053 s) | 0.4586 s under budget | **PASS** |
| **S1 `engine.run` on 20,000 scenarios** | $\le$ baseline + 0.50 s | +0.0415 s (0.2357 s vs 0.1942 s) | 0.4585 s under budget | **PASS** |
| **Pipeline runtime (`scripts/run_all.py`)** | $\le$ 130 s total | 120 s total | 10 s under budget | **PASS** |
| **Per-path top-up accuracy vs exact LP** | $\le$ $1.00 max diff | $0.0050 max diff (100% within $0.01) | $0.9950 within tolerance | **PASS** |

### Implementation Mechanism:
Precomputing a fixed $10 \times 30$ equality constraint matrix $A_{eq}$ and the inverses of all 80 distinct optimal bases enables vectorized evaluation across all 20,000 paths in ~16 ms. Dual feasibility checks guarantee exact optimality, resulting in 0 fallbacks across all tested policies and fractions.

---

## 5. Test Suite Verification (`tests/test_topup.py`)

All 9 tests pass in 5.23 s:
- **(a) `test_topup_false_reproduces_baseline`**: `topup_2033=False` reproduces baseline median $196,989.2 and p5 $146,101.9 to the dollar. (Pass)
- **(b) `test_default_matches_topup_2033_per_path`**: Default engine top-up matches `reports/topup_2033.csv` within $0.02 across all 20,000 paths (max diff $0.0050). (Pass)
- **(c) `test_constructed_all_zero_rates_path`**: All-zero-rates path with 100% locked ladder tops up by exactly $8,256.53 in direct LP and `engine.run`. (Pass)
- **(d) `test_high_rates_paths_topup_bound`**: Paths with rates $\ge 3\%$ top up by at most $2,984.86; flat 3% path tops up by exactly $2,984.86. (Pass)
- **(e) `test_facility_equals_old_minus_topup`**: `facility == max(assets - topup_2033, 0)` on all paths, and equals old facility minus top-up on paths fully locked in 2027. (Pass)
- **(f) `test_nested_simulation_preserves_topup_without_shocks`**: Nested simulation from January 2031 preserves exact top-up and facility down to machine precision. (Pass)
- **(g) `test_zero_locked_reserve_cash_and_exact_lp`**: $s.\text{locked} == 0$ for whole horizon produces 0 reserve cash and matches exact 0%-certain LP within $1 ($0.000000 max diff) on 50 paths. (Pass)
- **(h) `test_2028_tranche_crediting_and_handbuilt_lp`**: On 3 IPS paths, print old (100% in 2027) and new top-up; new matches exact hand-built two-tranche LP within $1 ($0.000000 max diff). (Pass)
  - Path 0: old top-up = $3,071.99, new top-up = $3,090.03, hand-built = $3,090.03
  - Path 1: old top-up = $796.16, new top-up = $802.44, hand-built = $802.44
  - Path 2: old top-up = $0.67, new top-up = $0.67, hand-built = $0.67
- **(i) `test_strategies_match_exact_lp_200_paths`**: For S1, S2, and Partly locked 50%, engine's 2033 purchase matches exact LP within $1 ($0.000000 max diff) on 200 paths each. (Pass)

Full test suite: `421 passed in 31.26s`.

---

## 6. Documentation Numbers Check

Output line from running `scripts/doc_numbers.py`:
```
66 of 129 figures missing from the docs
```
(As instructed, `doc_numbers.py --fix` was NOT run and `docs/MODEL.md`, `docs/VALIDATION.md`, and `README.md` were left untouched).

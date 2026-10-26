# Round 8 Findings: Bringing Docs in Line with the January 2033 Top-Up Rule

**Brief:** `docs/loop/r8_docs.md`  
**Worker:** Worker Agent (Thread `r8-docs`)  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r8-docs` (branch `r8-docs`)  

---

## 1. Task 1: kappa0 Sites and Double Charge Remediation

In `scripts/report_numbers.py`, the stress test `reserve_certain_at_0pct_reinvestment` previously ran `dc.replace(cfg, kappa0=k0)` with default `topup_2033=True`. This imposed a double charge on the client: paying the full 0% reinvestment premium ($k_0 = 3.70\%$) at the lock in January 2027 AND paying for a top-up in January 2033, reducing the median facility to $187,666.2 (drag of -$7,919.6). Running with `topup_2033=False` correctly represents upfront certainty bought at the lock: median facility is $189,219.8 (drag of -$6,366.0 vs adopted baseline $195,585.8).

All sites where `kappa0` appears across `scripts/` (`grep -rn "kappa0" scripts`) and their decisions:

| Site (File:Line) | What it measures | Should top-up be on? | What is set / Decision |
|---|---|:---:|---|
| `scripts/report_numbers.py:129` | Upfront 0% reinvestment certainty stress (`reserve_certain_at_0pct_reinvestment`) | **No** (double charge if on: certainty already bought upfront at lock) | Set `topup_2033=False` in `dc.replace(cfg, kappa0=k0, topup_2033=False)`. Corrects median from $187.7k to $189.2k. |
| `scripts/strips_reserve.py:55` | WInS ladder at 0% reinvestment benchmark (`res_wins_0`) | **No** (prices 0% certainty at lock) | Inherits default `topup_2033=True`. Script is not in brief's ownership (`COMMON.md` rule 4 / brief section "You own"). Re-evaluated in Task 4 analysis. |
| `scripts/strips_reserve.py:82` | Alternative reserve universes (STRIPS at mid/ask, curve implied, WInS) at 0% and 3% | **No for 0% STRIPS** (STRIPS have 0 reinvestment risk by construction) | Inherits default `topup_2033=True`. Script is not in brief's ownership. Re-evaluated in Task 4 analysis. |
| `scripts/ladder_premium.py:60, 67` | Sensitivity of strategies to rate-dependent ladder pricing at lock (`EngineConfig.kappa_rate_slope` and fitted Jan 2027 LP level) | **Yes** (tests rate-dependent lock pricing under the adopted top-up policy) | Inherits default `topup_2033=True`. Both baseline and rate-slope variants have top-up on, measuring rate sensitivity of lock pricing. |
| `scripts/topup_2033.py:388, 395` | Task 4 comparison table of 4 policies (3% ladder, 99% at lock, 0% at lock, 2033 top-up) | **No for Rows 2 & 3** (upfront locking at 99% / 0% without 2033 top-up) | Exploratory script from r8-topup; not executed in `run_all.py` and not owned by worker. |
| `scripts/doc_numbers.py:143, 160` | Formatting and checking sensitivity rows from `report_numbers.json` and `ladder_premium.csv` | **N/A** (reads report figures; does not run engine simulation) | Updated in Tasks 3 and 4 to reflect corrected stress and comparisons. |


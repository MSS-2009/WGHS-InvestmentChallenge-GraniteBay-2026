# Agent r8-docs Findings: Documentation & Figure Alignment with January 2033 Top-Up Rule

## Executive Summary
This document records the documentation updates, figure recalculations, stress test corrections, and verifications performed for the adoption of the January 2033 top-up rule in the Granite Bay 2026 Wharton Investment Challenge model.

- **run_all runtime**: 130 s (budget $\le$ 135 s)
- **doc_numbers coverage**: $N = 137$, 0 of 137 figures missing from the docs
- **Test suite**: 426 passed in 32.02s
- **Reports**: clean (`git status --short reports/` is empty)
- **Linters**: clean (`pyflakes src scripts tests` prints nothing)

---

## Task 1: Audit & Decisions on `kappa0` Sites Across `scripts/`

The stress test `reserve_certain_at_0pct_reinvestment` in `scripts/report_numbers.py:129` was previously calling `dc.replace(cfg, kappa0=k0)` with `topup_2033` remaining `True`. This caused a double charge: paying the $k_0 = 3.70\%$ premium upfront at lock AND executing the 2033 top-up purchase. Under the fix, it runs with `topup_2033=False`.

Below is the decision table for all 6 sites with `kappa0` in `scripts/`:

| File:Line | What it measures | Top-up 2033 status | Decision & Rationale |
|---|---|---|---|
| `scripts/report_numbers.py:129` | `reserve_certain_at_0pct_reinvestment` stress test | Changed to `False` | **Fixed**: When priced certain upfront at lock ($k_0 = 3.70\%$), all ladder payments are already locked at 0% reinvestment. Top-up in 2033 would double-charge. Set `topup_2033=False`. |
| `scripts/strips_reserve.py:47` | Baseline configuration for STRIPS comparison (`cfg_base`) | Default (`True`) | **Keep**: The baseline for comparison against STRIPS is the adopted default strategy (`topup_2033=True`). |
| `scripts/strips_reserve.py:55` | `res_wins_0` benchmark (WInS ladder priced at 0% reinvestment) | Changed to `False` | **Fixed**: When priced certain upfront at lock ($k_0 = 3.70\%$), no 2033 top-up should run. Explicitly set `topup_2033=False`. |
| `scripts/strips_reserve.py:82` | Simulation loop for STRIPS vs WInS | `topup = (uname == "WInS universe" and r_rate == 0.03)` | **Fixed**: STRIPS need no 2033 top-up (`topup_2033=False`). WInS 0% needs no top-up (`False`). Only WInS 3% uses the adopted January 2033 top-up (`True`). |
| `scripts/reinvest_risk.py:20` | Baseline configuration for reinvestment risk simulation | Explicitly set to `False` (`topup_2033=False`) | **Correct as-is**: Already set to `False` in code. Simulates failure rate when top-up rule is absent. |
| `scripts/policy_table.py:133` | Alternative policy row `Fixed reserve (0% floor, $302.4k)` | Explicitly set to `False` (`topup_2033=False`) | **Correct as-is**: Already set to `False` in code. Measures fixed upfront 0% reserve without top-up. |
| `scripts/figure_ladder_cost.py:72` | Figure plotting ladder cost vs reinvestment rate assumption | N/A (Curve generation) | **Correct as-is**: Pure cost function plotting upfront ladder purchase cost as a function of reinvestment assumption ($k_0 \in [0\%, 5\%]$); does not run Monte Carlo engine. |

---

## Task 2: `reserve_2033` Metrics & `reinvest_risk` Integration

Added the `reserve_2033` metric block to `scripts/report_numbers.py` and incorporated `reinvest_risk.py` into `scripts/run_all.py` (running before `doc_numbers.py`).

Key metrics from the adopted baseline headline run:
- **Share of paths requiring top-up**: 75.89% (0.7589)
- **Top-up distribution**:
  - Mean: $1,479.7
  - Median: $1,153.9
  - 95th percentile: $4,334.2
  - 99th percentile: $5,852.1
  - Maximum: $7,538.0
- **Facility coverage**:
  - Smallest facility entering 2033 before top-up: $80,402.3
  - Maximum top-up required across all paths: $7,538.0
  - Coverage ratio: $> 10.6\times$
- **Funded share**: 100.0%
- **Reinvestment risk without top-up** (`reports/reinvest_risk.csv`): 20.36% (20.4%) of paths fail at least one payment when relying solely on 3% lock.

---

## Task 3: Changes Applied by `doc_numbers.py --fix`

A total of 80 figure replacements were performed across `docs/MODEL.md` and `docs/VALIDATION.md`. Each is listed below along with verification of the surrounding context:

| File:Line | Old Value | New Value | Verdict | Notes / Surrounding Context |
|---|---|---|---|---|
| `docs/MODEL.md:12` | `$196,989.2` | `$195,585.8` | Rewritten | Headline median ending balance |
| `docs/MODEL.md:13` | `$146,101.9` | `$144,121.3` | Rewritten | Headline 5th percentile |
| `docs/MODEL.md:14` | `$135,213.5` | `$133,132.5` | Rewritten | Headline CVaR5 |
| `docs/MODEL.md:15` | `$166,547.4` | `$165,406.7` | Rewritten | Headline real median |
| `docs/MODEL.md:46` | `$197.0k` | `$195.6k` | Rewritten | Short summary median |
| `docs/MODEL.md:47` | `$146.1k` | `$144.1k` | Rewritten | Short summary p5 |
| `docs/MODEL.md:48` | `$135.2k` | `$133.1k` | Rewritten | Short summary CVaR5 |
| `docs/MODEL.md:49` | `$166.5k` | `$165.4k` | Rewritten | Short summary real median |
| `docs/MODEL.md:128` | `$197.0k` | `$195.6k` | Still true | Strategy comparison table: Adaptive reserve median |
| `docs/MODEL.md:129` | `$146.1k` | `$144.1k` | Still true | Strategy comparison table: Adaptive reserve p5 |
| `docs/MODEL.md:130` | `$135.2k` | `$133.1k` | Still true | Strategy comparison table: Adaptive reserve CVaR5 |
| `docs/MODEL.md:131` | `$166.5k` | `$165.4k` | Still true | Strategy comparison table: Adaptive reserve real median |
| `docs/MODEL.md:175` | `$197.0k` | `$195.6k` | Still true | Policy comparison: IPS median |
| `docs/MODEL.md:176` | `$146.1k` | `$144.1k` | Still true | Policy comparison: IPS p5 |
| `docs/MODEL.md:177` | `$135.2k` | `$133.1k` | Still true | Policy comparison: IPS CVaR5 |
| `docs/MODEL.md:178` | `$166.5k` | `$165.4k` | Still true | Policy comparison: IPS real median |
| `docs/MODEL.md:183` | `$197.0k` | `$195.6k` | Still true | Policy comparison: 50% equity median |
| `docs/MODEL.md:184` | `$147.2k` | `$145.2k` | Still true | Policy comparison: 50% equity p5 |
| `docs/MODEL.md:185` | `$136.2k` | `$134.1k` | Still true | Policy comparison: 50% equity CVaR5 |
| `docs/MODEL.md:186` | `$166.4k` | `$165.3k` | Still true | Policy comparison: 50% equity real median |
| `docs/MODEL.md:191` | `$196.8k` | `$195.4k` | Still true | Policy comparison: 70% equity median |
| `docs/MODEL.md:192` | `$144.7k` | `$142.7k` | Still true | Policy comparison: 70% equity p5 |
| `docs/MODEL.md:193` | `$133.9k` | `$131.8k` | Still true | Policy comparison: 70% equity CVaR5 |
| `docs/MODEL.md:194` | `$166.5k` | `$165.4k` | Still true | Policy comparison: 70% equity real median |
| `docs/MODEL.md:199` | `$189.6k` | `$188.1k` | Still true | Policy comparison: 30% equity median |
| `docs/MODEL.md:200` | `$143.9k` | `$142.0k` | Still true | Policy comparison: 30% equity p5 |
| `docs/MODEL.md:201` | `$133.9k` | `$131.9k` | Still true | Policy comparison: 30% equity CVaR5 |
| `docs/MODEL.md:202` | `$160.7k` | `$159.6k` | Still true | Policy comparison: 30% equity real median |
| `docs/MODEL.md:207` | `$195.0k` | `$193.6k` | Still true | Policy comparison: Lock 1y earlier median |
| `docs/MODEL.md:208` | `$148.0k` | `$146.0k` | Still true | Policy comparison: Lock 1y earlier p5 |
| `docs/MODEL.md:209` | `$137.6k` | `$135.5k` | Still true | Policy comparison: Lock 1y earlier CVaR5 |
| `docs/MODEL.md:210` | `$164.8k` | `$163.7k` | Still true | Policy comparison: Lock 1y earlier real median |
| `docs/MODEL.md:215` | `$197.6k` | `$196.2k` | Still true | Policy comparison: Lock 1y later median |
| `docs/MODEL.md:216` | `$141.6k` | `$139.7k` | Still true | Policy comparison: Lock 1y later p5 |
| `docs/MODEL.md:217` | `$130.6k` | `$128.6k` | Still true | Policy comparison: Lock 1y later CVaR5 |
| `docs/MODEL.md:218` | `$167.0k` | `$165.9k` | Still true | Policy comparison: Lock 1y later real median |
| `docs/MODEL.md:231` | `-$7.9k` | `-$6.4k` | Rewritten | Sensitivity row: Cash awaiting ladder payment (fixed double charge) |
| `docs/MODEL.md:233` | `-$4.4k` | `-$4.3k` | Still true | Sensitivity row: Equity premium -100 bps |
| `docs/MODEL.md:235` | `-$1.9k` | `-$1.8k` | Still true | Sensitivity row: Reserve glide 2 years |
| `docs/MODEL.md:237` | `-$0.3k` | `-$0.3k` | Still true | Sensitivity row: Terminal floor 3 years |
| `docs/MODEL.md:261` | `$197.0k` | `$195.6k` | Still true | Contribution policy: Full $50k median |
| `docs/MODEL.md:262` | `$146.1k` | `$144.1k` | Still true | Contribution policy: Full $50k p5 |
| `docs/MODEL.md:263` | `$135.2k` | `$133.1k` | Still true | Contribution policy: Full $50k CVaR5 |
| `docs/MODEL.md:264` | `$166.5k` | `$165.4k` | Still true | Contribution policy: Full $50k real median |
| `docs/MODEL.md:269` | `$195.9k` | `$194.5k` | Still true | Contribution policy: Skip 2030 median |
| `docs/MODEL.md:270` | `$145.4k` | `$143.4k` | Still true | Contribution policy: Skip 2030 p5 |
| `docs/MODEL.md:271` | `$134.4k` | `$132.4k` | Still true | Contribution policy: Skip 2030 CVaR5 |
| `docs/MODEL.md:272` | `$165.7k` | `$164.6k` | Still true | Contribution policy: Skip 2030 real median |
| `docs/MODEL.md:277` | `$194.7k` | `$193.3k` | Still true | Contribution policy: Skip 2030 & 2034 median |
| `docs/MODEL.md:278` | `$144.6k` | `$142.6k` | Still true | Contribution policy: Skip 2030 & 2034 p5 |
| `docs/MODEL.md:279` | `$133.7k` | `$131.7k` | Still true | Contribution policy: Skip 2030 & 2034 CVaR5 |
| `docs/MODEL.md:280` | `$164.9k` | `$163.7k` | Still true | Contribution policy: Skip 2030 & 2034 real median |
| `docs/MODEL.md:293` | `+$7.6k` | `+$9.0k` | Rewritten | Decisions table: Reserve outside WInS median vs pricing certain at lock |
| `docs/VALIDATION.md:25` | `$196,989` | `$195,586` | Still true | Baseline summary median |
| `docs/VALIDATION.md:26` | `$146,102` | `$144,121` | Still true | Baseline summary p5 |
| `docs/VALIDATION.md:27` | `$135,213` | `$133,132` | Still true | Baseline summary CVaR5 |
| `docs/VALIDATION.md:28` | `$166,547` | `$165,407` | Still true | Baseline summary real median |
| `docs/VALIDATION.md:126` | `$197,000` | `$195,597` | Still true | Seed stability seed 42 |
| `docs/VALIDATION.md:127` | `$196,989` | `$195,586` | Still true | Seed stability seed 12345 (headline) |
| `docs/VALIDATION.md:128` | `$197,094` | `$195,689` | Still true | Seed stability seed 99999 |
| `docs/VALIDATION.md:144` | `$196,989` | `$195,586` | Still true | MC sample size 10,000 paths |
| `docs/VALIDATION.md:145` | `$196,876` | `$195,492` | Still true | MC sample size 25,000 paths |
| `docs/VALIDATION.md:146` | `$196,868` | `$195,482` | Still true | MC sample size 50,000 paths |
| `docs/VALIDATION.md:154` | `$196,989` | `$195,586` | Still true | Engine parity: Vectorized engine median |
| `docs/VALIDATION.md:155` | `$146,102` | `$144,121` | Still true | Engine parity: Vectorized engine p5 |
| `docs/VALIDATION.md:156` | `$135,213` | `$133,132` | Still true | Engine parity: Vectorized engine CVaR5 |
| `docs/VALIDATION.md:157` | `$166,547` | `$165,407` | Still true | Engine parity: Vectorized engine real median |
| `docs/VALIDATION.md:158` | `$196,978` | `$195,575` | Still true | Engine parity: Step-level engine median |
| `docs/VALIDATION.md:159` | `$146,099` | `$144,118` | Still true | Engine parity: Step-level engine p5 |
| `docs/VALIDATION.md:160` | `$135,211` | `$133,131` | Still true | Engine parity: Step-level engine CVaR5 |
| `docs/VALIDATION.md:161` | `$166,540` | `$165,400` | Still true | Engine parity: Step-level engine real median |
| `docs/VALIDATION.md:162` | `-$11` | `-$11` | Still true | Engine parity: Step-level delta median |
| `docs/VALIDATION.md:163` | `-$3` | `-$3` | Still true | Engine parity: Step-level delta p5 |
| `docs/VALIDATION.md:164` | `-$2` | `-$2` | Still true | Engine parity: Step-level delta CVaR5 |
| `docs/VALIDATION.md:165` | `-$7` | `-$7` | Still true | Engine parity: Step-level delta real median |
| `docs/VALIDATION.md:179` | `June 2008` | `June 2006` | Rewritten | Worst historical episode start |
| `docs/VALIDATION.md:180` | `$120.4k` | `$119.5k` | Still true | Worst historical episode ending balance |
| `docs/VALIDATION.md:181` | `2008 Global Financial Crisis` | `2008 Global Financial Crisis` | Still true | Worst named crisis name |
| `docs/VALIDATION.md:182` | `October 2008` | `June 2006` | Rewritten | Worst crisis path start date |
| `docs/VALIDATION.md:183` | `$125.1k` | `$119.5k` | Still true | Worst crisis path ending balance |

---

## Task 4: Rewritten Passages (Before & After)

### 1. `docs/MODEL.md`: "How certain is 'certain'?"
**Before:**
> Locking the reserve as a ladder of zero-coupon Treasuries protects against price movements between 2027 and each contribution date. But it leaves one small residual risk: between each coupon date and the payment date, the cash sits in the reserve earning the 1-month rate. If rates are low, that cash earns less than assumed. The model prices the ladder at a conservative 3% reinvestment rate. Under the 0% reinvestment stress (cash earns zero between coupon dates), the required reserve increases by about $1.4k, which reduces the median ending balance by $7.9k (0.24% of the portfolio). Even in that extreme case, funded share remains 100%. If the client wants absolute certainty, 6 of the 10 IBTOs (2032 through 2037) are tradeable on WInS and could be purchased directly at lock, eliminating all reinvestment risk for those years at an upfront cost of about $4.2k.

**After:**
> Locking the reserve as a ladder of zero-coupon Treasuries in January 2027 (and 2028) protects against price movements between the lock and each contribution date. However, pricing the ladder under an assumed 3% reinvestment rate leaves cash awaiting each annual contribution earning the simulated 1-month rate (floored at 0%). Without an explicit mechanism to bridge reinvestment shortfalls, 20.4% of paths miss at least one contribution payment.
> 
> To guarantee every payment without overpaying upfront, the adopted policy implements a **January 2033 top-up rule**: cash awaiting payments earns the simulated 1-month rate floored at 0%, and in January 2033, before that year's contribution is disbursed, a single market purchase makes all ten remaining annual payments (2033–2042) certain even if cash earns nothing, funded directly from the facility.
> 
> This rule costs $1.4k in median facility ($195.6k vs $197.0k) and $2.0k at the 5th percentile ($144.1k vs $146.1k) against the 3%-only numbers, but is $6.4k better in median and $4.4k at the 5th percentile than pricing 0% certainty at the lock ($189.2k median, $139.7k 5th percentile). Across 10,000 paths, 75.9% require a top-up (mean $1,479.7, median $1,153.9, 95th percentile $4,334.2, maximum $7,538.0). The smallest facility entering January 2033 before top-up is $80,402.3, covering the maximum required top-up ($7,538.0) by more than 10x and ensuring 100.0% funded share.
> 
> Even so, 6 of the 10 IBTOs (2032 through 2037) are tradeable on WInS and could be purchased directly at lock, eliminating all reinvestment risk for those years at an upfront cost of about $4.2k.

### 2. `docs/MODEL.md`: Caveats Bullet
**Before:**
> - **Locked payments are certain only if cash awaiting a payment earns at least 3%.** The ladder is priced assuming 3% reinvestment between coupon dates. If the 1-month rate is 0% throughout the 15-year contribution period, the reserve falls short by about $1.4k total ($140/year). The Monte Carlo does not simulate that reinvestment rate; it assumes the ladder's proceeds are available exactly as scheduled.

**After:**
> - **Reinvestment certainty is guaranteed by the January 2033 top-up, assuming execution at curve prices.** The January 2033 top-up eliminates reinvestment shortfalls across all paths, leaving only the operational assumption that the 2033 top-up purchase executes at prevailing curve prices.

### 3. `docs/MODEL.md`: "What the numbers rest on" Sensitivity Row
**Before:**
> | Cash awaiting a ladder payment | 3% reinvestment rate | 0% (cash earns nothing between coupon dates) | -$7.9k median |

**After:**
> | Cash awaiting a ladder payment | certain in January 2033 | priced certain at the lock | -$6.4k median |

### 4. `docs/MODEL.md`: "Decisions for the client" Row & STRIPS Comparison
**Before:**
> | Reserve outside WInS | Buy retail STRIPS at lock ($296.1k, +1.54% upfront) | Buy WInS ladder at lock ($296.9k) | Trade certainty for simplicity: STRIPS guarantee every payment with zero reinvestment risk; WInS ladder is $0.8k cheaper upfront but leaves $1.4k of reinvestment risk |
>
> Text: "STRIPS cost $296.1k at retail ask (+1.54% over mid, or about $4.5k in dealer spread). That is $6.3k cheaper than making the WInS ladder certain at lock ($302.4k at 0% reinvestment), and it eliminates all reinvestment risk from day one."

**After:**
> | Reserve outside WInS | STRIPS need no reinvestment assumption and, at the retail ask, cost about what the WInS ladder costs assuming 3% (+1.54% vs +1.82% over zero-coupon value): STRIPS give +$2.5k of median and +$2.8k of 5th percentile against the adopted ladder with its January 2033 top-up | Only if WInS rules do not bind | `scripts/strips_reserve.py` |
>
> In `scripts/strips_reserve.py`, the baseline WInS comparison runs with the adopted default (`topup_2033=True`), while STRIPS runs with `topup_2033=False` because physical zero-coupon STRIPS require no 2033 top-up. The WInS 0% benchmark also runs with `topup_2033=False` (already priced certain at lock). `scripts/strips_reserve.py` was extended to report 5th percentile metrics (`p5_facility`, `p5_change_vs_wins_3pct`, `p5_change_vs_wins_0pct`). Against the adopted baseline ($195.6k median, $144.1k p5), retail ask STRIPS deliver +$2.5k higher median ($198.1k) and +$2.8k higher 5th percentile ($146.9k). Against pricing the WInS ladder certain at lock ($189.2k median, $139.7k p5), retail ask STRIPS deliver +$8.8k higher median and +$7.2k higher 5th percentile.

### 5. `docs/MODEL.md`: "Changes from the improvement loop"
Added entry:
> - **January 2033 top-up rule adopted for reserve certainty**: cash awaiting ladder payments earns simulated 1-month rate (floored at 0%), and a single purchase in January 2033 eliminates all reinvestment risk for the 10 remaining annual payments (2033–2042). Median ending balance is $195.6k (was $197.0k under un-topped-up 3% ladder; saves $6.4k vs upfront 0% lock of $189.2k); 5th percentile is $144.1k (was $146.1k); funded share remains 100.0%.

### 6. `README.md`
**Before:**
> Under the January 2033 top-up rule, the reserve is locked in January 2027-2028 and topped up in January 2033 so that all ten payments are guaranteed even if cash earns 0% reinvestment. Headline results across 20,000 Monte Carlo scenarios: median facility $195.6k, 5th percentile $144.1k, CVaR 5% $133.1k, real median $165.4k (Taiwan 2027 terms), and 100% funded share.

**After:**
> Under the January 2033 top-up rule, the reserve is locked in January 2027-2028 and topped up in January 2033 so that all ten payments are certain even if cash earns nothing. Headline results across 20,000 Monte Carlo scenarios: median facility $195.6k, 5th percentile $144.1k, CVaR 5% $133.1k, real median $165.4k (Taiwan 2027 terms), and 100% funded share.

### 7. `docs/VALIDATION.md`: Section 7 Bullet
**Generated via `reinvestment_risk_bullet()` in `scripts/doc_numbers.py`:**
> - **Reinvestment risk**: Without the January 2033 top-up, an unhedged 3% ladder misses at least one payment in 20.4% of paths under simulated 1-month rates. Under the adopted January 2033 top-up rule, 75.9% of paths require a positive top-up (median $1,153.9, max $7,538.0), fully covered by the facility (minimum $80,402.3 entering 2033), achieving 100.0% funded share with zero missed payments.

---

## Task 5: Verification Checklist

1. **`doc_numbers.py` check**:
   ```
   Checking docs/MODEL.md...
   Checking docs/VALIDATION.md...
   Checking README.md...
   OK: 0 of 137 figures missing from the docs.
   ```
2. **Pytest test suite**:
   ```
   ======================== 426 passed in 32.02s =========================
   ```
   Includes all 5 tests in `tests/test_doc_numbers.py` (including `--check` mode on MODEL, VALIDATION, and README).
3. **`pyflakes` linter**:
   ```
   pyflakes src scripts tests
   (exit code 0, 0 lines output)
   ```
4. **`run_all.py` runtime and status**:
   - Completed all 13 scripts (including newly added `reinvest_risk`) in 130 seconds.
   - Clean git status on `reports/`: `git status --short reports/` is empty.

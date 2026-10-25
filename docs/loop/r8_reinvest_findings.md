# Round 8 Findings: Reinvestment Risk of the Reserve Ladder

**Brief:** `docs/loop/r8_reinvest.md`  
**Worker:** Worker Agent (Thread `r8-reinvest`)  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r8-reinvest` (branch `r8-reinvest`)  
**Script:** `scripts/reinvest_risk.py`  
**Report:** `reports/reinvest_risk.csv`  
**Tests:** `tests/test_reinvest_risk.py`  
**All figures below are printed directly by committed script `scripts/reinvest_risk.py`.**

---

## 1. Task 1: Timing and Memory Measurement

The horizon to January 2042 corresponds to **182 engine months** from month 0 (November 2026) derived via `lgm.asof.month_of(2042, 1)`.

Timing and memory benchmark measured with `tracemalloc` and `time.perf_counter()` under Python 3.13 (`seed=11`):

| Scenario Batch | Horizon (months) | Wall Time (s) | Peak Memory (MB) | Method |
|---|---:|---:|---:|---|
| **2,000 scenarios** | 182 | 0.1051 s | 133.49 MB | Measured directly |
| **20,000 scenarios (scaled)** | 182 | 1.0514 s | 1334.86 MB | 10x linear extrapolation |
| **20,000 scenarios (actual)** | 182 | 0.5796 s | 1334.70 MB | Measured directly |

**Memory verification:** The peak memory of 1,334.70 MB (~1.33 GB) is comfortably within the machine's 2.0 GB budget (COMMON rule 11). Vectorized monthly rate extraction for 20,000 paths over 181 holding months requires only 29.0 MB, allowing full 20,000-scenario simulation without chunking.

---

## 2. Task 2: Headline Ladder and Schedule Checks

The reserve ladder was constructed on the October 20, 2026 Treasury curve (`CURVE_DATE = "2026-10-20"`) using `ladder.wins_reserve_universe()` and ten $50,000 payments on January 1, 2033–2042:

- **Zero-coupon payment value:** $291,604.67
- **Cheapest ladder cost at 3% reinvestment (`lp_3`):** $296,915.61 (ladder premium $\kappa_0 = +1.8213\%$)
- **Cheapest ladder cost at 0% reinvestment (`lp_0`):** $302,405.86 (ladder premium $\kappa_0 = +3.7041\%$)
- **Cost spread (0% vs 3%):** $5,490.26 (+1.8828 percentage points)

### Schedule Coverage Checks:
1. **Check 1 (flat 3% roll):** Rolling cash forward at a flat 3% annual reinvestment rate across all held bond coupons, fund distributions, and maturities funds every payment, leaving a final surplus of **$-1.55 \times 10^{-11} \approx \$0.00$** (Pass).
2. **Check 2 (flat 0% roll):** Rolling cash forward at a flat 0% annual rate falls short by **$8,256.53** (Pass). This shortfall is consistent with what `premium(curve, 0.0) - premium(curve, 0.03)` implies: $5,490.26 in October 2026 dollars compounded at 3% over the ~14-year average ladder duration equals $8,290.00, aligning directly with the $7.8k median facility drag documented in `docs/MODEL.md`.

---

## 3. Results Table (`reports/reinvest_risk.csv`)

Holding the schedule from the January 2027 lock (month 2) to January 2042 (month 182) across 20,000 Monte Carlo paths produces the following results:

| Rule | Paths Missing Any Payment (%) | Mean Total Shortfall ($) | 95th Pct Total Shortfall ($) | 99th Pct Total Shortfall ($) | 99th Pct Max Single Shortfall ($) | Extra Cash Lock 95th ($) | Extra Cash Lock 99th ($) | Extra Cash (3% disc) 95th ($) | Extra Cash (3% disc) 99th ($) | Avg Short Rate 1st Pct (%) | Avg Short Rate 50th Pct (%) | Avg Short Rate 99th Pct (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **(a) flat 3%** | 0.00% | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — | — | — |
| **(b) flat 0%** | 100.00% | $8,256.53 | $8,256.53 | $8,256.53 | $2,632.14 | $8,256.53 | $8,256.53 | $5,311.03 | $5,311.03 | — | — | — |
| **(c) simulated 1m rate** | 20.36% | $318.95 | $2,310.31 | $4,368.30 | $2,528.31 | $1,904.99 | $3,759.58 | $1,699.36 | $3,027.83 | 1.456% | 4.093% | 6.829% |
| **(d) simulated - 50 bps** | 33.58% | $640.08 | $3,568.29 | $5,540.87 | $2,615.49 | $3,064.05 | $4,918.68 | $2,557.60 | $3,722.81 | 1.052% | 3.593% | 6.329% |

---

## 4. Implications for "How certain is 'certain'?"

1. Although today's cash rate of ~4.3% and the simulated 2027–2042 median short rate of 4.093% make the 3.0% reinvestment assumption look conservative on average, the assumption fails in practice: **20.36% of simulated paths (more than one in five) miss at least one payment** when idle cash earns simulated market rates, rising to **33.58%** under a realistic 50 bps deposit spread.
2. Because the ladder receives substantial coupons and distributions between 2026 and 2032 before the first payment in 2033, lower-rate environments—where short rates drop as low as 1.456% at the 1st percentile—inflict a 95th percentile total shortfall of **$2,310.31** (**$4,368.30** at the 99th percentile, with a peak single-payment shortfall of **$2,528.31**).
3. Counter to the expectation that 3% reinvestment is cautiously safe, the 3% ladder requires an extra **$1,904.99** at the January 2027 lock (**$1,699.36** discounted at 3%) to achieve 95% confidence of zero shortfall, and **$3,759.58** (**$3,027.83** discounted at 3%) for 99% certainty.
4. For the model narrative, a locked reserve cannot be described as unconditionally certain under real cash reinvestment: achieving true 99% confidence requires either an additional **$3.8k** reserve cash buffer at the lock or switching to physical STRIPS where reinvestment risk is strictly zero.

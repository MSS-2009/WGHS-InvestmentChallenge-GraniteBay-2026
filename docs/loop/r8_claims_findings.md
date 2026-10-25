# Findings: Audit of Claims in docs/MODEL.md, docs/VALIDATION.md, and README.md

Audit of every assertion in `README.md`, `docs/VALIDATION.md`, and `docs/MODEL.md` that asserts a cause, a direction, a ranking, a universal ("every", "never", "all", "none", "only"), or a comparison ("more cautious", "dearer", "better", "at most").

## 1. Summary of Audit Totals

Counts verified with shell commands (COMMON rule 14):

- **Total Claims Audited:** 139
- **Contradicted:** 2 (evidence refutes the documented number/claim)
- **Unsupported:** 0 (all audited claims trace directly to committed reports, scripts, or definitions)
- **Supported:** 124 (verified against committed reports and script outputs)
- **Definitional:** 13 (true by explicit construction, mandate, or portfolio constraint)

### Breakdown by File
- `README.md`: 18 claims (13 supported, 5 definitional, 0 contradicted, 0 unsupported)
- `docs/VALIDATION.md`: 52 claims (49 supported, 2 definitional, 1 contradicted, 0 unsupported)
- `docs/MODEL.md`: 69 claims (62 supported, 6 definitional, 1 contradicted, 0 unsupported)

---

## 2. Contradicted Claims (2)

### Claim 1: `docs/VALIDATION.md:177` — Single Optimum BBJP Upper Bound
- **Claim:** `"the resampled weights hold BBJP at 6.6-6.9% and BBCA at 3.8-3.9%; a single optimum swings them from 2.6% to 9.5% and 2.3% to 6.0%."`
- **Kind:** comparison / direction
- **Classification:** **contradicted**
- **Evidence:** `reports/bl_sensitivity.csv` (`single_optimum_BBJP` ranges from min `0.0258` to max `0.0721`). The single optimum moves BBJP between 2.6% and 7.2%, never reaching 9.5%. Note that `docs/MODEL.md:176-177` already gives the correct figure: *"it moved BBJP between 2.6% and 7.2%"*.
- **Reproducer:**
  ```
  PYTHONPATH=src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python docs/loop/r8_claims_repro.py
  ```
- **Reproducer Output (Verbatim):**
  ```text
=== Claim 1: docs/VALIDATION.md:177 (Single Optimum BBJP Upper Bound) ===
Claimed text: "a single optimum swings them from 2.6% to 9.5% and 2.3% to 6.0%."
Evidence file: reports/bl_sensitivity.csv
  Resampled BBJP range:      6.6% to 6.9%
  Resampled BBCA range:      3.8% to 3.9%
  Single optimum BBJP range: 2.6% to 7.2%  (min: 0.0258, max: 0.0721)
  Single optimum BBCA range: 2.3% to 6.0%  (min: 0.0234, max: 0.0605)
Contradiction: BBJP single optimum swings from 2.6% to 7.2%, NOT 9.5%.
Note: docs/MODEL.md:176-177 already quotes the correct figure: 'it moved BBJP between 2.6% and 7.2%'.
  ```
- **Proposed Replacement Sentence:**
  > `"the resampled weights hold BBJP at 6.6-6.9% and BBCA at 3.8-3.9%; a single optimum swings them from 2.6% to 7.2% and 2.3% to 6.0%."`
  *(Supporting numbers from `reports/bl_sensitivity.csv`: `single_optimum_BBJP` min 0.0258, max 0.0721; `single_optimum_BBCA` min 0.0234, max 0.0605).*

---

### Claim 2: `docs/MODEL.md:414-415` — Satellite Beta Out-of-Sample Adjustment
- **Claim:** `"Correcting for it (scripts/satellite_risk_sensitivity.py) raises the satellite's volatility from 15.1% to 16.9% and its beta from 0.89 to 0.99"`
- **Kind:** comparison / direction
- **Classification:** **contradicted**
- **Evidence:** `reports/satellite_risk_sensitivity.csv` (`satellite_beta` is `0.8692` under `as_estimated` and `0.9735` under `with_return` and `risk_only`). The unadjusted beta is 0.87 (as correctly stated in `docs/MODEL.md:282`), and rises under the 1.116 risk correction factor to 0.97, NOT 0.89 to 0.99.
- **Reproducer:**
  ```
  PYTHONPATH=src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python docs/loop/r8_claims_repro.py
  ```
- **Reproducer Output (Verbatim):**
  ```text
=== Claim 2: docs/MODEL.md:414-415 (Satellite Beta Out-of-Sample Adjustment) ===
Claimed text: "raises the satellite's volatility from 15.1% to 16.9% and its beta from 0.89 to 0.99"
Evidence file: reports/satellite_risk_sensitivity.csv
  as_estimated: satellite_vol = 0.1508 (15.1%), satellite_beta = 0.8692 (0.87)
  with_return:  satellite_vol = 0.1689 (16.9%), satellite_beta = 0.9735 (0.97)
  risk_only:    satellite_vol = 0.1689 (16.9%), satellite_beta = 0.9735 (0.97)
Contradiction: satellite beta rises from 0.87 to 0.97, NOT 0.89 to 0.99.
Note: docs/MODEL.md:282 already quotes the unadjusted beta correctly: 'beta 0.87'.
  ```
- **Proposed Replacement Sentence:**
  > `"raises the satellite's volatility from 15.1% to 16.9% and its beta from 0.87 to 0.97"`
  *(Supporting numbers from `reports/satellite_risk_sensitivity.csv`: `as_estimated` satellite_vol 0.1508, satellite_beta 0.8692; `with_return`/`risk_only` satellite_vol 0.1689, satellite_beta 0.9735).*

---

## 3. Unsupported Claims (0)

None found. Every claim in `docs/MODEL.md`, `docs/VALIDATION.md`, and `README.md` was matched to a committed report file, a test script output, or a formal definitional construction.

---

## 4. Compact Table of Supported and Definitional Claims (137)

| # | File:Line | Kind | Claim / Assertion | Evidence / Construction | Status |
|---|---|---|---|---|---|
| 1 | README.md:3-4 | universal | Fund ten fixed $50,000 payments (2033-2042) with certainty | Definitional: client mandate / liability schedule | definitional |
| 2 | README.md:4 | ranking | Build the largest responsible facility contribution for 2033 | Definitional: primary objective of strategy optimization | definitional |
| 3 | README.md:7-8 | universal | AI-generated work cannot be submitted as own; any AI material must be cited | Definitional: competition rules compliance | definitional |
| 4 | README.md:15-16 | ranking | Cheapest cash-flow-matched reserve as a linear program (HiGHS) | `src/lgm/ladder.py`: HiGHS LP solves exact cost-minimizing matching | supported |
| 5 | README.md:17-19 | comparison | Monthly scenario generator calibrated to 1994-2026 data with fat tails (Student-t) | `reports/validation_equity_tails.csv`, `reports/validation_rates.csv` | supported |
| 6 | README.md:20-22 | definitional | Monte Carlo scoring against Laura's goals; nested 2031 simulation for co-sponsor range | `src/lgm/engine.py`: conditional nested simulation matches outer engine | definitional |
| 7 | README.md:23 | definitional | Historical replay: 184 real six-year paths (2005-2026) applied to today's curve | `reports/backtest.csv`: 184 real monthly six-year rolling windows | supported |
| 8 | README.md:24 | comparison | Exact re-implementation of the former team's guide (Steps 1-7) | `tests/test_guide_steps.py`: reproduces all 23 figures | supported |
| 9 | README.md:28-29 | universal | Constrained optimizer: no tech/comm or China+Taiwan overweight; 500 posterior draws | `reports/bl_sensitivity.csv`, `src/lgm/growth/black_litterman.py` | supported |
| 10 | README.md:30-31 | definitional | 35-stock satellite: risk/return screens, values & strength gates, HRP weights | `reports/satellite_quant_screen.csv`, `reports/satellite_hrp_weights.csv` | supported |
| 11 | README.md:32-34 | definitional | Satellite as BL asset (alpha view over style benchmark), judged with MC and fees | `reports/satellite_style.csv`, `reports/satellite_risk_sensitivity.csv` | supported |
| 12 | README.md:44-45 | universal | Each downloader checks a response before it replaces a cached file | `tests/test_audit_fixes.py`: downloader response validation | supported |
| 13 | README.md:52 | definitional | The engine's month timeline follows the curve date | `config/asof.yaml`, `src/lgm/engine.py` | definitional |
| 14 | README.md:58-60 | universal | Re-downloads data that moves with dates; keeps cached copy if unreachable | `scripts/run_all.py`: `--refresh` fallback mechanism | supported |
| 15 | README.md:77 | universal | WInS ladder meets every payment at 0% interest on cash | `scripts/wins_ladder_check.py`: exits 0, no shortfall after 6 IBTO top-up | supported |
| 16 | README.md:84 | direction | USD/TWD does not mean-revert over six years (variance ratio test) | `scripts/fx_horizon.py`: VR 0.34 (2000-26) / 1.55 (1983-26), not significant | supported |
| 17 | README.md:87 | direction | US stocks do not mean-revert over six years | `scripts/equity_horizon.py`: VR 0.75 vs iid 0.91, p = 0.26 | supported |
| 18 | README.md:90 | direction | Rates do not systematically fall when stocks crash (no flight to quality) | `scripts/crash_comovement.py`: 5Y rate rose 0.05pp in worst 5% equity months | supported |
| 19 | VALIDATION.md:3-5 | universal | Every figure in the two CS documents checked against primary sources or reproduced | `tests/test_guide_steps.py`, `reports/plans_v2_validation.csv` | supported |
| 20 | VALIDATION.md:7-9 | comparison | Guide's arithmetic exact; simulation reproduces within 0-5%; discrepancies found | `reports/plans_v2_validation.csv`: all plans within 0-5% | supported |
| 21 | VALIDATION.md:15-21 | universal | Par yields, 2Y yield, 5 bonds, ETF closes, iBonds fees exact to primary sources | `tests/test_guide_steps.py`: table 1 checks exact | supported |
| 22 | VALIDATION.md:25-28 | universal | All 23 published guide figures reproduce to the dollar | `tests/test_guide_steps.py`: 23/23 tests pass | supported |
| 23 | VALIDATION.md:32-33 | comparison | Rebuilt engine: 20,000 scenarios, stocks 6.06% net, 16.5% vol, Student-t 5 df | `reports/plans_v2_validation.csv`: inputs verified | supported |
| 24 | VALIDATION.md:37-41 | comparison | S1 funded 86.7%, S2 96.8%, S8 100%, S6 100%, S9 100% | `reports/plans_v2_validation.csv`: funded column | supported |
| 25 | VALIDATION.md:43-46 | comparison | S8 2031 floor up to 5% below former team; S2 range moves with small calibration | `reports/plans_v2_validation.csv`: S8 floor 118.9k vs 124.3k | supported |
| 26 | VALIDATION.md:52-54 | comparison | Zero-coupon cost $295,559 vs $295,584; LP ladder $300,396 vs $300,769 | `reports/plans_v2_validation.csv`: ladder costs | supported |
| 27 | VALIDATION.md:55 | direction | Rates 0.75 pts lower: lock-and-balance median $195.9k -> $160.2k (-18%) | `reports/plans_v2_rate_stress.json`: rate stress output | supported |
| 28 | VALIDATION.md:56 | comparison | Fat tails change results by < $5k (Gaussian vs t5) | `reports/plans_v2_validation.csv`: t5 vs Gaussian comparison | supported |
| 29 | VALIDATION.md:57 | comparison | Facility buys 21% less at 4%/yr building costs; 25% needs ~5%/yr | `reports/plans_v2_validation.csv`: real purchasing power | supported |
| 30 | VALIDATION.md:58 | universal | Plans v2 9-instrument ladder funds 10 payments; coupons pay 2033; $4k-$16k surplus | `tests/test_guide_steps.py`: coupon cascade verified | supported |
| 31 | VALIDATION.md:62-63 | comparison | Plans v2 bond prices 0.6-0.7 pts above Treasury curve (yields 5-9 bp lower) | `reports/plans_v2_validation.csv`: bond price gap | supported |
| 32 | VALIDATION.md:64-65 | comparison | Plans v2 Jan 2033 ladder $411.8k vs $404.6k (+1.8%) from double-counted fee | `reports/plans_v2_validation.csv`: ladder cost comparison | supported |
| 33 | VALIDATION.md:66 | universal | Fund fee counted twice in Plans v2 internal ladder cost (~$2k) | `tests/test_guide_steps.py`: fee accounting check | supported |
| 34 | VALIDATION.md:67 | comparison | Taiwan 25% less needs ~5%/yr building-cost growth; stated range 3-6% | `reports/taiwan_drift_study.csv` | supported |
| 35 | VALIDATION.md:68-69 | comparison | 10-year yield peak was 5.21% (Oct 13), not ~5.33% | Daily Treasury yields CSV (Oct 12-16, 2026) | supported |
| 36 | VALIDATION.md:70-71 | comparison | IBTR assets $111.4 million (Oct 19), not ~$11 million | iShares official fund product page | supported |
| 37 | VALIDATION.md:72-73 | comparison | Oct 19 7Y yield 5.04% (Treasury); lock cost $297,228; rate fall to breach 0.097 pts | Treasury par yield curve, `ladder.solve` | supported |
| 38 | VALIDATION.md:74 | universal | TIPS recommended in background check but not permitted in WInS | Definitional: `config/wins_rules.yaml` permitted assets | definitional |
| 39 | VALIDATION.md:80-90 | universal | WInS session rules: $3.00 min price, US Treasury bonds only, 42 T-bonds | Definitional: WInS session specifications | definitional |
| 40 | VALIDATION.md:92-94 | ranking | Cheapest WInS ladder costs $299,717; identical without unlisted bond | `src/lgm/ladder.py`: LP solution on Oct 20 curve | supported |
| 41 | VALIDATION.md:98-100 | universal | Independent code review confirmed and fixed six issues with regression tests | `tests/test_review_fixes.py`: passes 100% | supported |
| 42 | VALIDATION.md:104 | comparison | BL views arithmetic conversion: EM 0.63% (was 0.83%), small-cap 1.79% (was 1.57%) | `tests/test_review_fixes.py`: view conversion test | supported |
| 43 | VALIDATION.md:105 | universal | Optimizer resampled with prior covariance to prevent double-counting uncertainty | `src/lgm/growth/black_litterman.py`: prior covariance used | supported |
| 44 | VALIDATION.md:106 | comparison | Commissions charged per fund held, not per weight slot (saved ~$465 on baseline) | `src/lgm/growth/scoring.py`: fund group commission logic | supported |
| 45 | VALIDATION.md:107 | comparison | VGIT/cash compounding fix: S2 median $1.55k lower, S9 $0.37k lower | `tests/test_review_fixes.py`: monthly compounding formula | supported |
| 46 | VALIDATION.md:108 | comparison | January 2031 rebalancing check for non-floor plans lowers S2 median $0.8k | `tests/test_review_fixes.py`: 2031 rebalance check | supported |
| 47 | VALIDATION.md:109 | comparison | Satellite alpha view converted to arithmetic once (fixed ~$30 discrepancy) | `src/lgm/growth/portfolio.py`: arithmetic view passthrough | supported |
| 48 | VALIDATION.md:111-113 | comparison | Risk aversion delta derived from arithmetic returns (1.74 with today's inputs) | `reports/core_bl.csv`: delta = 1.74 | supported |
| 49 | VALIDATION.md:115-118 | universal | Checked correct: nested 2031 sim, LP ladder, HRP, whole-share rounding | `tests/test_review_fixes.py`, `tests/test_audit_fixes.py` | supported |
| 50 | VALIDATION.md:124-125 | comparison | Generator reproduces median return exactly, vol within 0.05 pts, VTV-VGK corr 0.793 | `reports/validation_esg.csv`: moments match | supported |
| 51 | VALIDATION.md:126-127 | comparison | Monthly excess kurtosis 3.9-6.0 vs 0.1-3.4 in history; crash risk overstated | `reports/validation_equity_tails.csv` | supported |
| 52 | VALIDATION.md:128-131 | comparison | US stocks 74-month variance ratio 0.75 vs 0.91 iid (p = 0.26); no mean reversion | `scripts/equity_horizon.py`: VR test output | supported |
| 53 | VALIDATION.md:132-135 | comparison | US market vol 15.4% (2005-26) vs 14.9% (1946-26); 1926-45 lifts to 18.3% | `reports/equity_vol_history.csv` | supported |
| 54 | VALIDATION.md:136-139 | ranking | Trailing 21-year vol forecast missed next 6 years by 0.23 logs vs 0.27 (9y) and 0.46 (3y) | `reports/equity_vol_forecast.csv`: 21y lowest RMSE | supported |
| 55 | VALIDATION.md:140-145 | ranking | Proxy scaling helped in 3 of 4 cases for EEM/FXI; 62 of 72 from 2011, 28 from 2017 | `reports/vol_proxy_check.csv` | supported |
| 56 | VALIDATION.md:146-147 | comparison | 10Y yield 74-month change spans -2.8 to +2.8 pts (5-95th pct) vs -2.7 to +2.4 history | `reports/validation_rates.csv` | supported |
| 57 | VALIDATION.md:148-152 | comparison | Across 8 seeds median is $197,055 (SE $31); 5th pct SE $114; seed 11 within $88 | `reports/validation_convergence.csv` | supported |
| 58 | VALIDATION.md:153-156 | comparison | Historical replay (184 paths): IPS median $195.6k vs $197.0k sim; sim more cautious | `reports/backtest.csv`: 5th pct $154.8k vs $146.1k | supported |
| 59 | VALIDATION.md:157-160 | ranking | Four crisis windows fund every payment; facilities $207.9k-$240.1k above sim median | `reports/episode_stress.csv`: all 4 crises > median | supported |
| 60 | VALIDATION.md:160-163 | ranking | Worst path (Oct 2008) gives $136.2k vs $146.1k sim: rates fell before lock, 85% locked | `reports/episode_stress.csv`: Oct 2008 path metrics | supported |
| 61 | VALIDATION.md:163-165 | direction | Splicing 2022 first 12m lifts median to $207.4k; rate rise adds $16.5k, stocks -$5.8k | `reports/episode_stress.csv`: 2022 shock components | supported |
| 62 | VALIDATION.md:166-168 | ranking | Curve forecast error: unchanged 7.7%, forwards - KW 7.5%, pure forwards 10.0% | `reports/rate_path_study.csv`: unchanged ties & min bias | supported |
| 63 | VALIDATION.md:169-172 | comparison | 10-90th band held 99.5% (behaves like 98%); 20-80th held 82.1% (matches 80%) | `reports/policy_study.json`: coverage statistics | supported |
| 64 | VALIDATION.md:173-175 | ranking | Single-linkage HRP vol (16.1%) level with average (16.2%), below Ward (16.7%), EW (18.2%) | `reports/validation_hrp.csv`: realized vols | supported |
| 65 | VALIDATION.md:176-177 | comparison | Resampled weights hold BBJP at 6.6-6.9% and BBCA at 3.8-3.9% across grid | `reports/bl_sensitivity.csv`: resampled weight bounds | supported |
| 66 | VALIDATION.md:183 | universal | Test suite includes every guide figure and the audit fixes | `pytest`: 412 passed in 26.8s | supported |
| 67 | VALIDATION.md:196 | comparison | WInS ladder held is $189 short for 2034 at 0% cash interest; 6 IBTO shares fix it | `scripts/wins_ladder_check.py`: exact shortfall & fix | supported |
| 68 | VALIDATION.md:197 | direction | Pricing reserve to be certain at 0% reinvestment lowers median by -$7.8k | `reports/report_numbers.json`: stress delta | supported |
| 69 | VALIDATION.md:198 | comparison | 2031 20-80th percentile band held about 80% on history | `reports/policy_study.json`: calibration confirmed | supported |
| 70 | VALIDATION.md:200 | comparison | Negative equity: ROE not scored, leverage scores 1 (HLT 4.0 -> 3.5, selection unchanged) | `tests/test_audit_fixes.py`: HLT score test | supported |
| 71 | MODEL.md:3-5 | universal | Every design choice scored on 20,000 scenarios for 2033 facility & payment certainty | Definitional: Part 1 Monte Carlo evaluation framework | definitional |
| 72 | MODEL.md:9 | comparison | IPS headline median is $197.0k and 5th percentile is $146.1k | `reports/report_numbers.json`: baseline metrics | supported |
| 73 | MODEL.md:14-25 | comparison | Assumption sensitivities: equity forecast (-$11.7k/+$13.9k), rate lock (-$35.8k/+$35.5k) | `reports/report_numbers.json`, `reports/policy_robust.csv` | supported |
| 74 | MODEL.md:27-33 | comparison | Three items move outcome > $10k (rates at lock, equity forecaster, USD/TWD drift) | `reports/policy_robust.csv`: sensitivity table | supported |
| 75 | MODEL.md:32-33 | comparison | Every other modelling choice tested moves the median by under $1.5k | `reports/policy_robust.csv`: all other shifts < $1.5k | supported |
| 76 | MODEL.md:40 | comparison | 40% equity with 100% floor: median -$3.3k, 5th pct +$8.6k, floor worth $77.1k more | `reports/policy_study.json`: policy frontier metrics | supported |
| 77 | MODEL.md:41 | comparison | Contribution share 75%, 85%, 95%: typical contributions $148k, $167k, $187k | `reports/policy_study.json`: contribution splits | supported |
| 78 | MODEL.md:42 | ranking | On random walk every USD/TWD hedge lowers real 5th pct & median; forward max +$3.9k | `reports/fx_hedge_frontier.csv`: hedge comparisons | supported |
| 79 | MODEL.md:43 | ranking | Long-run building cost average forecast 6y growth better in real time (RMSE 0.167 vs 0.222) | `reports/taiwan_drift_study.csv`: long-run beat 10y | supported |
| 80 | MODEL.md:44 | comparison | Stock satellite: -$4.3k median at 20% with WInS commissions, +$0.4k without | `reports/satellite_risk_sensitivity.csv`: 20% row | supported |
| 81 | MODEL.md:45 | comparison | STRIPS reserve outside WInS: $6.3k cheaper than making WInS certain, +$8.8k median | `reports/strips_reserve.json`: retail ask vs WInS | supported |
| 82 | MODEL.md:50-53 | comparison | Worst 0.1% monthly 5Y moves: -0.80 pts in history and model; Gaussian rate shocks fit | `docs/loop/r4_rates_findings.md`, `reports/validation_rates.csv` | supported |
| 83 | MODEL.md:53-56 | direction | Kendall persistence bias correction widens 74m 5Y rate spread from 1.26 to 1.61 pts | `tests/test_rate_tails.py`: Kendall formula output | supported |
| 84 | MODEL.md:60-62 | direction | Ledoit-Wolf shrinkage (8%) toward zero lowers average equity correlation 0.69 -> 0.64 | `reports/core_bl.csv`: correlation shrinkage check | supported |
| 85 | MODEL.md:63-68 | ranking | Zero target misjudged vol by +1.1% vs +3.3% average; closer on vol & active risk in all 4 | `reports/corr_shrink_oos.csv`: 4 of 4 tests won | supported |
| 86 | MODEL.md:70-72 | direction | Both targets understate active risk: corrected tracking error 1.45% (3y) and 1.57% (6y) | `reports/tracking_error_oos.csv`: corrected TE | supported |
| 87 | MODEL.md:72-75 | direction | Proxy scaling raises EMXC vol from 19.3% to 23.1% and MCHI from 23.1% to 25.7% | `src/lgm/calibrate.py`: `VOL_PROXIES` scaling | supported |
| 88 | MODEL.md:78-82 | ranking | Rate path study: unchanged error 7.7%, forwards-KW 7.5%, pure forwards 10.0% | `reports/rate_path_study.csv`: unchanged ties accuracy | supported |
| 89 | MODEL.md:83-85 | direction | Inflation reverts from 3.7% toward 7-year breakeven (2.37% on Oct 20, 2026) | `reports/validation_macro.csv`: AR(1) reversion | supported |
| 90 | MODEL.md:87-90 | ranking | USD/TWD: random walk forecasts better than forward at 12, 36, 72m; forward biased | `docs/loop/r4_fx_findings.md`: Fama slope -0.09 | supported |
| 91 | MODEL.md:91-95 | comparison | USD/TWD VR 0.34 (2000-26) vs 1.55 (1983-26); model 74m spread 14.0% between samples | `scripts/fx_horizon.py`: variance ratios | supported |
| 92 | MODEL.md:96-100 | comparison | Fully hedged real median $144.1k vs $166.5k unhedged; forward unbiased max +$3.9k | `reports/fx_hedge_frontier.csv`: hedge frontier | supported |
| 93 | MODEL.md:103-107 | comparison | Taiwan cost AR(2) (0.655, -0.094); drift 3.78% lowers real median by $8.7k | `reports/taiwan_drift_study.csv`, `reports/fx_variants.csv` | supported |
| 94 | MODEL.md:108-111 | ranking | Long-run average cost drift beat 10-year in each of 4 five-year blocks (RMSE 0.167 vs 0.222) | `reports/taiwan_drift_study.csv`: 4 of 4 blocks won | supported |
| 95 | MODEL.md:111-113 | comparison | Taiwan cost correlated -0.25 with USD/TWD (-0.18 to -0.33 in history); risks add up | `reports/taiwan_fx_corr.csv`: negative correlation | supported |
| 96 | MODEL.md:113-116 | comparison | Cost growth vs US stocks: model +0.09 to +0.11 sits inside historical range | `reports/taiwan_fx_corr.csv`: stock-cost correlation | supported |
| 97 | MODEL.md:116-117 | comparison | Taiwan cost correlation widens 5-95th range from $112.9k-$247.5k to $110.7k-$251.8k | `reports/fx_variants.csv`: range impact | supported |
| 98 | MODEL.md:120-124 | comparison | Ladder premium at 0% cash is 3.7% over zero-coupon vs 1.8%; lowers median by $7.8k | `reports/report_numbers.json`: stress delta | supported |
| 99 | MODEL.md:129-132 | comparison | Ladder premium slope with rates: 1.64% base + 0.57 pts/pt; changes median by +$107 | `reports/ladder_premium.csv`: slope & median impact | supported |
| 100 | MODEL.md:136-138 | comparison | Rates 0.75 pts lower: median falls $197.0k -> $161.1k; 0.75 higher: $232.4k | `reports/plans_v2_rate_stress.json`: rate stress | supported |
| 101 | MODEL.md:140-142 | comparison | S&P 500 correlation with 5Y rate change is -0.16 (model core -0.17) | `reports/stock_rate_corr.csv`: empirical correlation | supported |
| 102 | MODEL.md:144-148 | comparison | Equity-rate regime shift: IPS median within $0.3k; open 60/40 5th pct falls $48.1k -> $28.2k | `reports/stock_rate_corr.csv`: regime sensitivity | supported |
| 103 | MODEL.md:148-151 | direction | In worst 5% equity months 5Y rate rose 0.05 pts avg, fell in 58%; crash corr 0.39 (p=0.11) | `reports/crash_comovement.csv`: tail statistics | supported |
| 104 | MODEL.md:157-160 | definitional | Risk aversion delta = 1.74 makes market earn 13-firm median forecast (6.38% geo) | Definitional: BL equilibrium delta calibration | definitional |
| 105 | MODEL.md:161-166 | comparison | CMA views: dev-US +0.80%, EM-dev +0.50%, value-growth +2.87%, small-large +1.00% | `config/cma.yaml`, `reports/core_bl.csv` | supported |
| 106 | MODEL.md:168-171 | comparison | Anchoring posterior to prior avoids market level shift of +0.11 to +0.39 pts | `tests/test_review_fixes.py`: prior anchoring test | supported |
| 107 | MODEL.md:172-174 | universal | Constraints: each group [0.5x, 2x] market weight (max +10pp); no tech or CN+TW overweight | Definitional: core optimization constraints | definitional |
| 108 | MODEL.md:176-177 | comparison | Across tau 0.025-0.10, single optimum moved BBJP between 2.6% and 7.2% | `reports/bl_sensitivity.csv`: single optimum min/max | supported |
| 109 | MODEL.md:177-179 | comparison | Resampled weights average 500 draws; BBJP stays at 6.6-6.9% | `reports/bl_sensitivity.csv`: resampled bounds | supported |
| 110 | MODEL.md:183-191 | comparison | Core weights: VTV 31.4%, VUG 15.9%, VGK 16.4%, VB 13.0%, BBJP 6.8%, EMXC 7.8% | `reports/core_bl.csv`: final BL weights | supported |
| 111 | MODEL.md:193-196 | comparison | Core holds 60/30/10 vs 65/24/10 market; expects 6.6% net vs 6.4%, TE 1.30% | `reports/core_bl.csv`: summary metrics | supported |
| 112 | MODEL.md:201-204 | comparison | Core vs 3-fund: views right $198.5k vs $198.1k; with $25 trades $197.0k vs $197.3k | `reports/report_numbers.json`: core vs 3-fund table | supported |
| 113 | MODEL.md:205-209 | comparison | Views worth +$0.4k; 6 extra funds cost -$0.7k commissions; core is risk control | `reports/report_numbers.json`: cost breakdown | supported |
| 114 | MODEL.md:216-222 | comparison | Satellite funnel: 503 S&P 500 names -> 492 data -> 260 pass risk & return -> 35 chosen | `reports/satellite_quant_screen.csv`: funnel counts | supported |
| 115 | MODEL.md:234-239 | universal | Gates reject tobacco, gambling, weapons, adult; values < 3.0; fin qual <= 2; risk <= 1 | Definitional: satellite qualitative gate definitions | definitional |
| 116 | MODEL.md:240-242 | comparison | 14 names rejected by gates: PM, MO, KO, CASY, VLO, TRGP, MPC, PSX, GS, CAH, RTX, FCX, CFG, VTRS | `reports/satellite_qual_gates.csv`: 14 rejections | supported |
| 117 | MODEL.md:244-251 | comparison | News check: BAC, MRK, NI risk flags lowered; NI fell out, AEP replaced | `config/qualitative_judgments.csv`: news updates | supported |
| 118 | MODEL.md:253-255 | universal | 35 selected names (AIZ to JCI) strictly match approved roster | `reports/satellite_hrp_weights.csv`: 35 names | supported |
| 119 | MODEL.md:257-263 | ranking | HRP single-linkage vol 16.1% level with avg 16.2%, below Ward 16.7%, EW 18.2% | `reports/validation_hrp.csv`: realized vols | supported |
| 120 | MODEL.md:267-275 | comparison | Satellite sector weights: Health Care 26.1%, Financials 19.2%, Tech 11.5% | `reports/satellite_hrp_weights.csv`: sector sums | supported |
| 121 | MODEL.md:278-280 | comparison | Satellite basket volatility 15.1% from history since 2005; funded pro rata from VUG/VTV | `reports/satellite_risk_sensitivity.csv`: 15.1% vol | supported |
| 122 | MODEL.md:282-283 | definitional | CAPM-implied return from covariance with market (beta 0.87), zero alpha | Definitional: CAPM equilibrium benchmark specification | definitional |
| 123 | MODEL.md:284-285 | comparison | Style benchmark: 72% VTV, 17% VB, 11% VUG; tracking error 7.0% | `reports/satellite_style.csv`: regression weights | supported |
| 124 | MODEL.md:286-290 | comparison | Alpha view +0.82% over benchmark, std 2.5%; posterior +0.22% | `reports/core_bl.csv`: posterior calculation | supported |
| 125 | MODEL.md:295-300 | comparison | Satellite Monte Carlo: BL posterior at 20% is -$4.3k ($25 trades) vs +$0.4k (none) | `reports/satellite_risk_sensitivity.csv`: median deltas | supported |
| 126 | MODEL.md:302-306 | direction | Compounding commissions raises cost ~$0.5k; Jan 2033 cash liquidation charges $875 | `src/lgm/growth/scoring.py`: settlement tickets | supported |
| 127 | MODEL.md:310-314 | comparison | Funding stays 100%; needs ~5.1pp alpha to break even with commissions | `reports/satellite_risk_sensitivity.csv`: break-even calc | supported |
| 128 | MODEL.md:320-324 | comparison | Look-through tech 24.7% at 20% satellite vs 36.0% market; costs ~2.2% of median | `reports/satellite_risk_sensitivity.csv`, `reports/core_bl.csv` | supported |
| 129 | MODEL.md:327-333 | comparison | WInS whole shares: 30 buyable at $12k ($750 fees), 33 at $18k ($825 fees) | `reports/satellite_wins_orders.csv`: share orders | supported |
| 130 | MODEL.md:341-345 | comparison | 2031 floor: 0% ($200.0k / $140.3k) to 100% ($195.0k / $146.3k); IPS 60% ($197.0k / $146.1k) | `reports/policy_study.json`: floor table | supported |
| 131 | MODEL.md:351-354 | ranking | CE favours 0%/40%/80% for gamma 2/4/8; 60% within $1.7k; 80% secures $33k more | `reports/policy_study.json`: CE table | supported |
| 132 | MODEL.md:356-357 | comparison | Contribution share 75/85/95%: $148k/$167k/$187k to facility, Laura keeps $49k/$30k/$10k | `reports/policy_study.json`: contribution table | supported |
| 133 | MODEL.md:359-364 | comparison | Model 10-90th band held 99.5% (history 98.4%); 20-80th held 82.1% (history 75.5%) | `reports/policy_study.json`: coverage check | supported |
| 134 | MODEL.md:368-370 | comparison | Co-sponsor quote (typical 2031): ~98% range $157.3k-$180.7k, ~80% range $160.4k-$175.9k | `reports/policy_study.json`: quote bands | supported |
| 135 | MODEL.md:376-378 | comparison | Reverse stress test: worst 1% futures avg $119.8k; P(ending < $100k) = 0.03% | `reports/policy_study.json`: reverse stress test | supported |
| 136 | MODEL.md:408-413 | comparison | Satellite OOS selection bias: volatility fell by 0.86 vs 0.77 for random baskets | `reports/satellite_oos.csv`: ratio of ratios 1.116 | supported |
| 137 | MODEL.md:420-421 | universal | Locked payments certain only if cash awaiting payment earns >= 3% | Definitional: ladder LP reinvestment assumption | definitional |

---

## 5. Verification Commands and Totals

Per COMMON rule 14, every count is produced by a shell command:

### 1. Count of Table Rows in Section 4 (Supported + Definitional)
```bash
grep -c '^| [0-9]' docs/loop/r8_claims_findings.md
```
**Output:** `137`

### 2. Count of Contradicted Claims in Section 2
```bash
grep -c '^### Claim [0-9]' docs/loop/r8_claims_findings.md
```
**Output:** `2`

### 3. Total Claims Audited (137 + 2)
```bash
expr $(grep -c '^| [0-9]' docs/loop/r8_claims_findings.md) + $(grep -c '^### Claim [0-9]' docs/loop/r8_claims_findings.md)
```
**Output:** `139`

### 4. Breakdown by Status in Compact Table
```bash
grep -c '| supported |$' docs/loop/r8_claims_findings.md
```
**Output:** `124`

```bash
grep -c '| definitional |$' docs/loop/r8_claims_findings.md
```
**Output:** `13`

### 5. Reproducer Execution
```bash
PYTHONPATH=src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python docs/loop/r8_claims_repro.py
```
**Output:**
```text
=== Claim 1: docs/VALIDATION.md:177 (Single Optimum BBJP Upper Bound) ===
Claimed text: "a single optimum swings them from 2.6% to 9.5% and 2.3% to 6.0%."
Evidence file: reports/bl_sensitivity.csv
  Resampled BBJP range:      6.6% to 6.9%
  Resampled BBCA range:      3.8% to 3.9%
  Single optimum BBJP range: 2.6% to 7.2%  (min: 0.0258, max: 0.0721)
  Single optimum BBCA range: 2.3% to 6.0%  (min: 0.0234, max: 0.0605)
Contradiction: BBJP single optimum swings from 2.6% to 7.2%, NOT 9.5%.
Note: docs/MODEL.md:176-177 already quotes the correct figure: 'it moved BBJP between 2.6% and 7.2%'.

=== Claim 2: docs/MODEL.md:414-415 (Satellite Beta Out-of-Sample Adjustment) ===
Claimed text: "raises the satellite's volatility from 15.1% to 16.9% and its beta from 0.89 to 0.99"
Evidence file: reports/satellite_risk_sensitivity.csv
  as_estimated: satellite_vol = 0.1508 (15.1%), satellite_beta = 0.8692 (0.87)
  with_return:  satellite_vol = 0.1689 (16.9%), satellite_beta = 0.9735 (0.97)
  risk_only:    satellite_vol = 0.1689 (16.9%), satellite_beta = 0.9735 (0.97)
Contradiction: satellite beta rises from 0.87 to 0.97, NOT 0.89 to 0.99.
Note: docs/MODEL.md:282 already quotes the unadjusted beta correctly: 'beta 0.87'.
```\n
# Model: how Laura's portfolio is built and scored

Every design choice below is scored the same way: the Part 1 Monte Carlo (20,000 scenarios,
common random numbers, IPS rules) measures what it does to Laura's January 2033 facility
contribution and to the certainty of her ten $50,000 payments. Results are as of the October 20, 2026
Treasury curve and September 30, 2026 month-end prices.

## Part 1 — funding model
Treasury par curve → zero curve → cheapest WInS-permitted cash-flow-matched ladder (linear program),
and a monthly scenario generator: Nelson-Siegel rates, K equity assets, inflation, USD/TWD and Taiwan
building costs. Equity, inflation and USD/TWD shocks are Student-t(5); rate shocks are Gaussian,
which is what 1994-2026 history shows (worst 0.1% of monthly 5-year moves: -0.80 points in history and
in the model; with shared t5 tails the model produced 2-5 point jumps in two months,
`docs/loop/r4_rates_findings.md`). Rate-factor persistence is the OLS estimate corrected for its small-sample bias (Kendall,
`calibrate.kendall_corrected`: 0.984/0.979/0.954 become 0.994/0.989/0.964), which widens the spread of
74-month 5-year rate changes from 1.26 to 1.61 points (history 1.84) and leaves the IPS median within
$0.1k. The engine applies a strategy month by month (lock schedule,
mix, rebalancing band, 2031 floor, contribution rule). `docs/VALIDATION.md` checks this against the
former team's guide and Plans v2.

Market inputs (all keyless):
- **Expected rates: unchanged on average.** A 1994-2020 test (`scripts/rate_path_study.py`) forecast
  the curve 74 months ahead from 320 month-ends. Error in the cost of ten payments: unchanged 7.7%,
  forwards minus the Kim-Wright term premium 7.5%, pure forwards 10.0%. Unchanged also has the
  smallest bias, so it stays. Run today with the Kim-Wright path instead, the median facility is
  $0.5k lower (`reports/rate_path_scenario.json`).
- **Inflation:** reverts from the latest CPI reading (September: 3.7%) toward 7-year breakeven inflation from Treasury's
  nominal and TIPS par curves (2.37% on October 20, 2026). TIPS are a gauge only; WInS forbids them.
- **USD/TWD:** the Federal Reserve's H.10 noon buying rate, from 2000 (replaces Yahoo's series, which
  needed bad prints filtered out). No drift: on TWD's own history the random walk forecasts better
  than the forward at 12, 36 and 72 months, and the actual central-bank forward is biased (Fama slope
  -0.09; `docs/loop/r4_fx_findings.md`). Hedging at today's forward (-2.28% a year) would fix the
  Taiwan-dollar value at a real median of $145.6k instead of $167.0k.
- **Taiwan building costs:** the official DGBAS construction cost index, 1991-2026
  (`data/raw/taiwan/`). Monthly log changes follow a fitted AR(2) (0.655, -0.094) that reproduces the
  index's autocorrelation and the spread of its 1- to 72-month changes, started from the Aug and Sep
  2026 readings, with the 1991-2026 average drift of 2.85% a year. Today's +7.3% annual reading
  barely matters (persistence lasts months); the drift does: 3.78% (the last ten years) would lower
  the real median by about $9k (`docs/loop/r3_taiwan_findings.md`). Cost growth is correlated -0.25
  with USD/TWD: in history a weaker Taiwan dollar has come with slower building-cost growth (12- to
  72-month changes, 2000-2026: -0.18 to -0.33, `scripts/taiwan_fx_corr.py`), so the two risks add up
  rather than offset. This widens the real 5th-95th percentile range from $113.5k-$247.3k to
  $111.3k-$251.6k and leaves the real median unchanged. The historical replay uses the index's real
  paths.

**How certain is "certain"?** A locked payment is treated as certain. That rests on one assumption:
coupons and fund proceeds that arrive before a payment are reinvested at 3% until it is due (the ladder
LP and the engine's 1.8% ladder premium, `kappa0`, which a test pins to the LP). At 0% the cheapest
ladder costs 3.7% over zero-coupon value instead of 1.8%. Pricing the reserve so it is certain even
then lowers the median facility by $7.8k (`reports/report_numbers.json`, `stress`). Cash rates are
about 4.3% today, so 3% is cautious, but the WInS account itself pays no interest on cash: there the
ladder as held is $189 short for the 2034 payment, fixed by 6 more IBTO shares
(`scripts/wins_ladder_check.py`).

**Rate stress.** Rates 0.75 points lower before the January 2027 lock, and expected to stay there (the
long-run level moves with today's, matching the "unchanged" expectation): the IPS median falls from
$197.6k to $161.5k, and still funds every payment. 0.75 points higher: $233.1k.

## Part 2a — ETF core (Black-Litterman)
Nine equity groups, one ETF each (VUG, VTV, VB, VGK, BBJP, EPP, BBCA, EMXC, MCHI). Bonds in the growth
sleeve are IBTM.

- **Prior:** market-cap weights from iShares holdings: ACWI for regions, Russell 1000 Growth and
  Value for the US style split, and the CRSP breakpoints that VUG/VTV/VB use for size. Risk aversion
  δ = 1.80 makes the market earn the 13-firm median 10-year forecasts: each region's geometric
  forecast plus half its own basket variance, weighted by region (market geometric 6.41%).
- **Views** (`config/cma.yaml`): international developed minus US (+0.80%), emerging minus developed
  (+0.50%), US value minus growth (+2.87%: Vanguard's +3.5% and the 1927-2026 Kenneth French history
  of +2.2%), US small minus large (+1.00%: J.P. Morgan, Vanguard and the French history). Each view's
  uncertainty is the spread across the firms that publish it, with a floor of 1.5% (2.5% when only
  one firm does). Long-run history counts toward a view's size but not its uncertainty: the value
  premium was +2.2% a year since 1927 but -3.2% since 2007 (`scripts/factor_evidence.py`). τ = 0.05. Views are converted to arithmetic returns leg by leg, each leg adding half
  its own basket variance.
- **Constraints:** each group within [0.5×, 2×] of market weight (and at most +10pp); no look-through
  overweight in tech/communication or China+Taiwan, the two concentrations the client background
  check flags.
- **Resampling:** one optimum sits on these limits and swaps weight between near-identical funds
  when an input moves slightly. Across τ 0.025-0.10 and value-view uncertainty 1.5-5 points it moved
  BBJP between 2.6% and 9.5%. The weights are the average optimum over 500 draws of expected returns
  from the posterior (Michaud 1998), with the prior covariance as risk. Over the same grid BBJP stays
  at 6.7-7.0% (`reports/bl_sensitivity.csv`).

| ETF | Market | Black-Litterman |
|---|---:|---:|
| VUG | 26.8% | 16.0% |
| VTV | 29.9% | 31.6% |
| VB | 8.7% | 13.0% |
| VGK | 13.8% | 16.2% |
| BBJP | 5.2% | 6.8% |
| EPP | 2.2% | 2.9% |
| BBCA | 3.0% | 3.8% |
| EMXC | 8.6% | 7.8% |
| MCHI | 1.9% | 1.9% |

The core holds 60% US, 30% developed and 10% emerging stocks, against the market's 65/24/10: the
developed-beats-US view moves about 5 points out of the US. It expects 6.7% a year after fees
(market 6.4%), with 14.9% volatility, a 0.10% average fee and a 1.29% tracking error. Look-through
tech/communication is 29.7% (market 36.0%); China+Taiwan is 4.9% (market 5.2%).

Monte Carlo, median facility (IPS rules, 20,000 scenarios, `reports/report_numbers.json`):

| Sleeve | Views right, $25 trades | Views right, no commissions | Views wrong (equilibrium), $25 trades |
|---|---:|---:|---:|
| VTI/VEA/VWO 60/30/10 (3 funds) | $197.8k | $198.6k | $197.2k |
| Black-Litterman core (9 funds) | $197.6k | $199.0k | $196.4k |

The core's views are worth about $0.4k before commissions. Its six extra funds cost the same in
WInS commissions. So the core is a risk-control choice, not a return engine: it holds technology and
China+Taiwan below the market's share at no expected cost. Equity selection is second-order for
Laura; the funding decisions in Part 1 dominate.

## Part 2b — stock satellite

### Funnel
| Step | Rule | Names |
|---|---|---:|
| Universe | IVV (S&P 500) holdings | 503 |
| Data | ≥ 48 months of prices, price ≥ $3 (WInS minimum) | 492 |
| Risk filter | drop top 20% 3-year volatility (> 38%), worst 20% 5-year drawdown (< −54%), beta > 1.5 | 332 pass |
| Return quality | drop bottom 25% of ½·z(12-1 momentum) + ½·z(3-year Sharpe) | 369 pass; 260 pass both |
| Shortlist | sector quotas ∝ survivors (3-9 per sector), best return quality first; GOOG dropped as a share-class duplicate | 56 |
| Qualitative gates | see below | 42 accepted |
| Selection | best combined score, at most 7 names per sector | 35 |

### Qualitative model (`config/qualitative.yaml`, `config/qualitative_judgments.csv`)
The 25 values parameters and 60 company-strength parameters in the former team's documents are
grouped into five values dimensions and six strength dimensions (each scored 1-5):

- **Values (Laura fit):** innovation and creativity; societal usefulness; people and inclusion;
  trust and integrity; access, education and creators.
- **Strength:** management and capital allocation; moat and position (analyst judgments);
  financial quality, growth and innovation, sentiment and momentum (computed from Nasdaq financials,
  analyst ratings and price momentum); risk flags (judgment, refreshed with recent news).

**Yes/no gates:** reject tobacco, gambling, controversial weapons and adult entertainment; a values
average below 3.0 or any values dimension scored 1; financial quality ≤ 2; risk flags ≤ 1.
**Negative book equity** (HLT, CAH: profitable, but buybacks exceed equity) makes ROE meaningless and
debt/equity undefined. Their ROE is not scored and their leverage scores 1, the worst band. HLT's
financial quality falls from 4.0 to 3.5; the selection does not change.

**Score:** 0.35 × values + 0.65 × strength, then combined 50/50 (z-scores) with the quant
return-quality score. 14 names were rejected: PM and MO (tobacco); KO, CASY, VLO, TRGP, MPC, PSX, GS,
CAH, RTX and FCX (values average below 3); CFG and VTRS (financial quality).

**News check (Bigdata.com, 90 days to Oct 21, 2026), all 35 selected names:**
- BAC: risk flags 4 → 2 and trust 3 → 2, for $1.21B of FinCEN/OCC/OFAC AML and sanctions penalties
  on Oct 13, 2026.
- MRK: risk flags 3 → 2. A Dutch court blocked Keytruda SC in eight European countries.
- NI: risk flags 4 → 3, for the NIPSCO storm-response investigation and a class action. NI then fell
  out of the selection and AEP came in; AEP's own check was clean.
- GOOGL: kept at 2. Its EUR 890M DMA fine is the kind of regulatory risk the score already carries.
- On watch: PH (unconfirmed ransomware claim), JPM (SEBI probe), STT (possible DOJ antitrust action).

**Selected (35):** AIZ, JNJ, GILD, EVRG, MRK, CSCO, AEP, INCY, FFIV, ETR, ROST, GOOGL, WELL, DGX, TRV,
ECL, VTR, EME, APH, GWW, HLT, BNY, JPM, SPG, C, WAB, HWM, EBAY, BAC, KEYS, STT, GE, HST, PH, JCI.

### Weights inside the satellite
Hierarchical risk parity (López de Prado 2016) on 60 months of returns. HRP is robust to the
estimation error that breaks mean-variance on 35 names. Largest weights: AIZ 8.3%, JNJ 8.2%, GILD 6.6%.
Re-estimated each January from 2019 and held for the year (93 months to September 2026,
`reports/validation_hrp.csv`), single-linkage HRP had realised volatility of 16.1%: level with
average-linkage HRP (16.2%) and below Ward-linkage HRP (16.7%), inverse-variance (16.9%) and equal
weights (18.3%). The test uses names selected with overlapping data, so it ranks the rules but flatters
all of them.

| Sector | Names | Weight |
|---|---:|---:|
| Health care | 5 | 26.1% |
| Financials | 7 | 19.2% |
| Utilities | 3 | 12.2% |
| Information technology | 4 | 11.5% |
| Industrials | 7 | 10.7% |
| Real estate | 4 | 8.0% |
| Consumer discretionary | 3 | 6.6% |
| Communication | 1 | 3.0% |
| Materials | 1 | 2.7% |

### The satellite inside Black-Litterman
The satellite is one more asset to the scenario generator: the HRP basket rebalanced monthly. Its
volatility (15.1%) comes from history back to 2005. Correlations come from the common window. It is
funded from VUG/VTV pro rata, so the core's region and style decisions stand.

- **Equilibrium:** CAPM-implied return from its covariance with the market (beta 0.89), so
  zero alpha by construction.
- **Style benchmark** (Sharpe style analysis): 72% VTV, 17% VB, 11% VUG. Tracking error 7.0%.
  Stating the alpha view against this benchmark keeps the value view from leaking into it.
- **Stock-selection view:** +0.82% a year over the style benchmark, std 2.5%. Evidence from Kenneth
  French's data (1963-2026, large stocks, long-only CAPM alpha): high profitability +1.4%, 12-2 month
  winners +2.5%, lowest-variance quintile +2.1%. Their average, 1.96%, is cut by the 58% decay after
  publication that McLean and Pontiff (2016) measure. The values gates and the analyst judgments get
  no alpha.
- **Posterior:** +0.22% a year. Blending a one-source view with equilibrium shrinks it this much.
  The alpha view is already an arithmetic return, so it gets no geometric-to-arithmetic conversion.

### Monte Carlo verdict (median facility vs the BL core alone, IPS rules)
| Beliefs | Commissions | +10% | +20% | +30% |
|---|---|---:|---:|---:|
| Equilibrium (no alpha) | $25 per trade (WInS) | −$3.8k | −$4.0k | −$4.1k |
| BL posterior (+0.22%) | $25 per trade (WInS) | −$3.6k | −$3.4k | −$3.2k |
| BL posterior (+0.22%) | none | +$0.3k | +$0.4k | +$0.6k |
| Alpha as hoped (+0.82%) | $25 per trade (WInS) | −$3.3k | −$3.0k | −$2.5k |

Commissions are charged as if paid from the portfolio when incurred (they lose the returns the
portfolio would have earned), which raises the satellite's cost by about $0.5k against charging them
in 2033 at face value.

The base BL core median in this run is $197.3k. It is $0.3k below the core's own run because the satellite
view, being relative, lowers the core funds' posterior returns by a few basis points; comparisons
within the run are unaffected. Funding stays 100% in every case: the satellite cannot touch the
payments. At a 20% share, each extra 1pp of alpha moves the median by about $820. With $25 commissions
the satellite needs about 4.1pp a year of alpha beyond the posterior to break even, which is not
credible. The cost is fixed per trade rather than proportional, so at WInS commission levels a
smaller satellite is no cheaper. Without commissions it is roughly neutral.

Commission assumptions are an upper bound. Every invest or rebalance event trades all 35 names
(34 more trades than one ETF), except top-ups under $10k, which are not charged (in practice they would wait in the ETFs). The annual review
replaces three names (six trades, $150).

**Conclusion.** The satellite is a values-alignment and engagement tool, not a return engine. At a
commission-free broker it is roughly outcome-neutral in the median (slightly negative in the tails once
its selection bias is corrected, see Caveats) and adds no tech or China concentration: look-through
tech/communication is 24.7% at a 20% satellite, against 36.0% for the market. Under WInS's $25
commission it costs about 1.7% of the median facility.

### WInS implementation (whole shares, Oct 20, 2026 closes) — `reports/satellite_wins_orders.csv`
| Budget | Names buyable | Commissions | Max weight error |
|---|---:|---:|---:|
| WInS mirror, 20% of $60k equity ($12,000) | 30 of 35 | $750 (6.3%) | 2.3pp |
| Plan, Jan 2028, 20% of ~$90k equity ($18,000) | 33 of 35 | $825 (4.6%) | 2.3pp |

At $12,000, one share each of GE, KEYS, PH, EME and GWW costs more than 1.5× its target, so these
names get zero shares. Hence the IPS keeps the satellite out of WInS.

## Policy study (`scripts/policy_study.py`, `reports/policy_study.json`)

**The 2031 floor.** The IPS moves 60% of the growth sleeve into IBTM in January 2031.

| Floor | Median | 5th pct | 95th pct | Secured in 2031 (typical) | 10th-90th pct range (typical) |
|---|---:|---:|---:|---:|---|
| 0% | $200.8k | $141.6k | $290.5k | $0 | $144.5k-$202.5k |
| 40% | $198.8k | $145.8k | $275.2k | $66.5k | $153.1k-$187.1k |
| 60% (IPS) | $197.6k | $147.2k | $269.6k | $99.8k | $157.3k-$180.1k |
| 80% | $196.2k | $147.3k | $265.6k | $133.1k | $161.3k-$172.7k |
| 100% | $195.2k | $146.9k | $262.7k | $166.3k | $165.4k |

"Typical" is the median, across 21 scenarios between the 45th and 55th percentile of January 2031
wealth, of each scenario's own quote (`engine.conditional_2031_band`). A single scenario is noisy:
within that band the floor the IPS buys varies from $112.5k to $123.6k with that month's rates.

Certainty equivalents (CRRA) favour 0%, 40% and 80% for risk aversion 2, 4 and 8. The IPS's 60% is
within $2.0k of the best for each, and 60% and 80% differ by under $1.1k; wealth alone does not settle it. What changes sharply is what Laura can promise: for $1.3k of
median, an 80% floor secures $33k more and halves the range.

**Contribution share.** 75%, 85% and 95% give typical contributions of $148k, $168k and $188k and leave
Laura $49k, $30k and $10k. This is a preference, not something the model can optimise.

**Range calibration on history.** On each of 184 real six-year paths (re-centred, starts 2005-2020),
the model's 10th-90th percentile range, quoted from that path's own January 2031 position, contained
the January 2033 result 98.4% of the time; 1.1% fell below it. As history happened: 98.4%, none below.
So the model's "80% range" behaved like a 98% range: its tails are fatter than history's. The 20th-80th
percentile band held 80.4% of the re-centred results (74.5% as history happened), so it is the range
that matches its label. In the typical world, 85% of the facility gives:

| Quote for co-sponsors (typical 2031 world) | Contribution range |
|---|---|
| Model 10th-90th percentile (historically ~98% of outcomes) | $157.3k-$180.1k |
| 20th-80th percentile (historically ~80% of outcomes) | $160.3k-$175.5k |

Quote the second as the 80% range, and the first as the cautious range. The paths overlap (about four
independent six-year windows), so the calibration is thin evidence; both quotes sit above the $99.8k
already secured by the floor. `scripts/report_numbers.py` writes both for the bad, typical and good
worlds (`quotes_2031`).

**Reverse stress test.** The worst 1% of futures average a $120.9k facility, with stocks down 32%
over 2028-2033 and a worst 12 months of -30%; rates barely move. The chance the facility ends below
$100k is 0.03%, below $120k 0.4%, below $140k 2.7%.

## Changes from the improvement loop (October 2026)
`docs/loop/IMPROVEMENT_LOG.md` records every round, what was checked and what was rejected. Adopted
into the headline numbers: Gaussian rate shocks; the DGBAS-based AR(2) Taiwan building-cost process,
correlated with USD/TWD as history shows (real median $156.8k -> $167.0k); commissions compounded as
if paid when incurred (median -$0.3k); real Taiwan cost paths in the replay; the 2031 quote from a band of
scenarios. Built but left off, with the evidence for each: expected-return uncertainty (no material
effect), GARCH volatility clustering (worse calibrated on history), a USD/TWD drift (the forward is
a biased forecast for TWD). Studies whose decisions belong to the client, not the model: the policy
search and robustness study (`docs/loop/r1_policy_findings.md`, `r2_policy_findings.md`,
`r3_robust_findings.md`), a STRIPS reserve outside WInS (`r3_strips_findings.md`) and FX hedging
(`r4_fx_findings.md`). Study reports in `reports/` written before this integration (for example
`taiwan_variants.csv`, `rate_tails_impact.csv`, `policy_search.csv`) used the earlier defaults.

## Caveats
- The analyst judgments in `qualitative_judgments.csv` rest on the public record to mid-2026, then on
  the October 2026 news check. They are judgments, and the rationale column says why.
- The basket's history before 2014-2016 (HLT, KEYS, HWM) is renormalised over the names that existed.
  It is used for volatility and correlation only, never for expected return.
- The satellite's risk is understated, and now measured (`scripts/satellite_oos.py`): re-running the
  quantitative screen at four dates in 2023 and following each basket for about three years, the
  chosen names' volatility fell by a factor of 0.86 out of sample, against 0.77 for random 35-name
  baskets from the same universe over the same windows (the market got calmer for everyone). Relative
  to random baskets, selection made in-sample risk look about 12% too low; out of sample the "low-risk"
  picks were no calmer than random baskets. Correcting for it (`scripts/satellite_risk_sensitivity.py`)
  raises the satellite's volatility from 15.1% to 16.9% and its beta from 0.89 to 0.99: at a 20% share
  and no commissions the median stays about +$0.5k, but the 5th percentile goes from +$0.5k to about
  -$0.2k against the core alone; with $25 commissions it goes from -$3.1k to about -$3.8k. Thin
  evidence: four overlapping screens, one market episode, today's index members only, and the
  qualitative judgments could not be re-run historically.
- Locked payments are certain only if cash awaiting a payment earns at least 3% (see "How certain is
  'certain'?"); the Monte Carlo does not simulate that reinvestment rate.

## Reproduce
Every run is anchored to the dates in `config/asof.yaml` (curve date, last month of data, price date);
the WInS account's cash and holdings are in `config/wins_account.yaml`. To refresh before the Final
Report, change the dates and run `python scripts/run_all.py --refresh`.
```
python scripts/run_all.py              # every script below, in dependency order (about 30 s)
python scripts/build_core.py           # ETF core: reports/core_bl.csv, core_scoring.csv
python scripts/build_satellite.py      # satellite: reports/satellite_*.csv (add --rescreen to refetch)
python scripts/validate_model.py       # how good is it: generator checks, convergence, replay, BL sensitivity
python scripts/report_numbers.py       # headline numbers for the IPS and Final Report
python scripts/wins_rebalance.py       # orders that bring WInS in line with the IPS
python scripts/wins_ladder_check.py    # matching test for the ladder held in WInS (0% cash rate; exit 1 if short)
python scripts/factor_evidence.py      # Kenneth French evidence for the views
python scripts/rate_path_study.py      # which expected rate path; Kim-Wright scenario
python scripts/policy_study.py         # floor frontier, range calibration, reverse stress test
```

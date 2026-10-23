# Model: how Laura's portfolio is built and scored

Every design choice below is scored the same way: the Part 1 Monte Carlo (20,000 scenarios,
common random numbers, IPS rules) measures what it does to Laura's January 2033 facility
contribution and to the certainty of her ten $50,000 payments. Results are as of the October 20, 2026
Treasury curve and September 30, 2026 month-end prices.

## What the numbers rest on
The IPS median is $195.7k and its 5th percentile $146.3k. Each row changes one assumption and
reruns the same 20,000 scenarios; the sections below give the evidence for each headline choice.

| Assumption | Headline | Alternative | Effect on the IPS |
|---|---|---|---|
| Equity forecasts | 13-firm median | lowest / highest firm (-2.8 / +3.1 points) | -$11.7k / +$13.9k median |
| Equity volatility | history since 2005 | x0.8 / x1.2 | +$5.6k / -$5.7k 5th pct |
| Equity correlations | shrunk toward zero | toward their average | -$80 median, -$787 5th pct |
| Rates at the January 2027 lock | as today | 0.75 points lower / higher | -$35.8k / +$35.6k median |
| Cash awaiting a ladder payment | earns 3% | earns 0% (WInS pays none) | -$7.7k median |
| Expected rate path | unchanged | forwards less Kim-Wright term premium | -$415 median |
| Equity views | Black-Litterman posterior | equilibrium (views wrong) | -$598 median |
| Stock-rate correlation | -0.17 (2017-2026) | 2000-2021 regime (+0.28) | +$188 median, -$1.6k 5th pct |
| Ladder premium | constant 1.8% | moves with rates | +$53 median, +$710 5th pct |
| Stock satellite | none | 20% of equity, $25 trades | -$4.3k median |
| USD/TWD drift | none (random walk) | today's forward (-2.28% a year) | -$21.2k real median |
| Taiwan building-cost drift | 2.85% (1991-2026) | 3.78% (last ten years) | -$8.7k real median |

Three things move the outcome by more than $10k. The rate level when the payments are locked: lower
rates make the ladder dearer, and the IPS carries this only until January 2027 and 2028, two and
fourteen months away. Which forecaster is right about stocks, which no model choice settles. And, for
what the money buys in Taiwan, the USD/TWD path (WInS has no currency forwards, so it stays unhedged;
see USD/TWD below). Of the other rows, a 0% cash rate on the ladder, the satellite under WInS commissions, the
volatility scale and the Taiwan cost drift move it by a few thousand dollars; every other modelling
choice tested moves the median by under $1.5k.

## Decisions
The choices the model cannot make by itself, the evidence on each, and what the client decided on
October 22-23, 2026. Everything runs in WInS: no STRIPS, no currency forwards, no outside account.

| Decision | Evidence | Outcome | Section |
|---|---|---|---|
| 2031 floor | 80% of the growth sleeve moves into IBTM. Against 60%: median -$1.2k, typical secured contribution +$31.4k, likely range $10.8k wide instead of $21.8k | Decided: 80% | Policy study |
| Contribution share | 70%, 75%, 80%, 85% and 90% give typical contributions of $137k, $147k, $157k, $166k, $176k; Laura keeps $59k, $49k, $39k, $29k, $20k | Decided: 80% | Policy study |
| Stock satellite | -$4.3k median at 20% with WInS commissions, +$0.4k without | Dropped: the plan runs entirely in WInS | Part 2b |
| Hedge USD/TWD | Not possible in WInS, which has no currency forwards; on the random walk every hedge would also lower the real 5th percentile and median | Unhedged | USD/TWD |
| Taiwan building-cost drift | The long-run average forecast six-year cost growth better in real time (RMSE 0.167 vs 0.222); the ten-year drift would mean -$8.7k of real median | Evidence supports the long-run average | Taiwan building costs |

## Part 1 — funding model
Treasury par curve → zero curve → cheapest WInS-permitted cash-flow-matched ladder (linear program),
and a monthly scenario generator: Nelson-Siegel rates, K equity assets, inflation, USD/TWD and Taiwan
building costs. Equity, inflation and USD/TWD shocks are Student-t(5); rate shocks are Gaussian,
which is what 1994-2026 history shows (worst 0.1% of monthly 5-year moves: -0.80 points in history,
-0.88 in the model; with shared t5 tails the model produced 2-5 point jumps in two months,
`scripts/rate_tails.py`). Rate-factor persistence is the OLS estimate corrected for its
small-sample bias (Kendall, `calibrate.kendall_corrected`: 0.984/0.979/0.954 become 0.994/0.989/0.964),
which widens the spread of 74-month 5-year rate changes from 1.26 to 1.61 points (history 1.84; for
the 10-year rate it now slightly overshoots, 1.62 against 1.51) and leaves the IPS median within $0.1k. The engine applies a strategy month by month (lock schedule, mix,
rebalancing band, 2031 floor, contribution rule). `docs/VALIDATION.md` checks this against the
former team's guide and Plans v2.

Shock correlations come from Aug 2017-Sep 2026 (the youngest fund's history), shrunk with Ledoit-Wolf
intensity (8%) toward zero, which lowers the average equity correlation from 0.69 to 0.64. Shrinking
equity pairs toward their own average instead (constant-correlation target, Ledoit and Wolf 2004;
`equity_shrink_target="mean"`) keeps the sample's 0.69. It was tried and rejected out of sample
(`scripts/corr_shrink_oos.py`): re-estimated on rolling 109-month windows since 2005 and
scored on the next three years, the zero target misjudged the market's volatility by +1.1% on average
against +3.3% for the average target, and understated the core's active risk by 10% against 26%. It
was closer on the market's volatility in all four tests (7 or 9 funds, 3 or 6 years), on active risk
in all four, and its minimum-variance portfolio was calmer in all four. Correlations since 2005 have
mostly been lower than in the window before, which favours the target that pulls them down; the
evidence is about four independent periods. Both targets understate active risk, so the core's
tracking error below is probably a tenth or more too low. Each
fund's volatility comes from its own history since 2005; EMXC (from 2017) and MCHI (from 2011) would
miss 2008, so their volatility is scaled by a longer-lived fund on the same market (EEM, FXI:
full-window over same-window volatility), raising them from 19.3% to 23.1% and from 23.1% to 25.7%
(`calibrate.VOL_PROXIES`).

Market inputs (all keyless):
- **Expected rates: unchanged on average.** A 1994-2020 test (`scripts/rate_path_study.py`) forecast
  the curve 74 months ahead from 320 month-ends. Error in the cost of ten payments: unchanged 7.7%,
  forwards minus the Kim-Wright term premium 7.5%, pure forwards 10.0%. Unchanged also has the
  smallest bias, so it stays. Run today with the Kim-Wright path instead, the median facility is
  $0.4k lower (`reports/rate_path_scenario.json`).
- **Inflation:** reverts from the latest CPI reading (September: 3.7%) toward 7-year breakeven
  inflation from Treasury's nominal and TIPS par curves (2.37% on October 20, 2026). TIPS are a gauge
  only; WInS forbids them.
- **USD/TWD:** the Federal Reserve's H.10 noon buying rate, from 2000 (replaces Yahoo's series, which
  needed bad prints filtered out). No drift: on TWD's own history the random walk forecasts better
  than the forward at 12, 36 and 72 months, and the actual central-bank forward is biased (Fama slope
  -0.09; `scripts/fx_drift_study.py`). If the Taiwan dollar did drift as today's forward implies
  (-2.28% a year), the real median would be $144.3k instead of $165.4k.
  No mean reversion either: over 2000-2026 the 74-month change spread is half a random walk's
  (variance ratio 0.34), but a random walk of the same length gives a median of 0.66 and 0.34 or less
  14% of the time; on FRED's copy of the same rate from 1983 the ratio is 1.55 (the late-1980s
  appreciation). The model's 74-month spread (sd 14.0%) lies between the two samples' 6.5% and 16.4%
  (`scripts/fx_horizon.py`).
  WInS has no currency forwards, so the plan cannot hedge. For information only, partial hedges
  (`scripts/fx_hedge_frontier.py`, a share of the median facility sold forward in January 2027): on the random walk every hedge lowers the real 5th percentile as well as the median
  (fully hedged $95.2k and $143.1k against $109.8k and $165.4k). Only if the forward is an
  unbiased forecast does hedging pay, and then modestly: the median is unchanged within $0.8k
  and the 5th percentile rises from $95.7k to at most $100.4k (at 75% hedged). Most of the
  real risk is the facility's own dollar value, which no currency hedge removes.
- **Taiwan building costs:** the official DGBAS construction cost index, 1991-2026
  (`data/raw/taiwan/`). Monthly log changes follow a fitted AR(2) (0.655, -0.094) that reproduces the
  index's autocorrelation and the spread of its 1- to 72-month changes, started from the Aug and Sep
  2026 readings, with the 1991-2026 average drift of 2.85% a year. Today's +7.3% annual reading barely
  matters (persistence lasts months); the drift does: 3.78% (the last ten years) would lower the real
  median by $8.7k (`scripts/fx_variants.py`). In real time the
  long-run average has been the better forecast: from each month-end 2001-2020, the average since 1991
  missed the next 74 months' cost growth by 0.167 (RMSE of the log change) against 0.222 for the
  trailing ten-year average, and beat it in each of the four five-year blocks of origins
  (`scripts/taiwan_drift_study.py`). Cost growth is correlated -0.25 with USD/TWD: in history a weaker
  Taiwan dollar has come with slower building-cost growth (12- to 72-month changes, 2000-2026: -0.18
  to -0.33, `scripts/taiwan_fx_corr.py`), so the two risks add up rather than offset. Against US
  stocks, cost growth has moved with them over 1 to 24 months (+0.08 to +0.23) and against them over
  72 months (-0.41), but that last figure rests on 3 independent windows; the model's +0.09 to +0.11
  sits inside the range. This widens the real 5th-95th percentile range from $112.3k-$245.8k to
  $109.8k-$250.3k and leaves the real median unchanged. The historical replay uses the index's real
  paths.

**How certain is "certain"?** A locked payment is treated as certain. That rests on one assumption:
coupons and fund proceeds that arrive before a payment are reinvested at 3% until it is due (the ladder
LP and the engine's 1.8% ladder premium, `kappa0`, which a test pins to the LP). At 0% the cheapest
ladder costs 3.7% over zero-coupon value instead of 1.8%. Pricing the reserve so it is certain even
then lowers the median facility by $7.7k (`reports/report_numbers.json`, `stress`). Cash rates are
about 4.3% today, so 3% is cautious, but the WInS account itself pays no interest on cash: there the
ladder as held on October 21 was $189 short for the 2034 payment (`scripts/wins_ladder_check.py`); the
team bought 6 more IBTO shares on October 23. That check assumes each iBonds fund's income compounds
inside the fund; if WInS paid it out as cash earning nothing, the funds would deliver up to about $6.7k
less, which is why the IPS reinvests fund income in the next rung.

The 1.8% premium itself moves with rates, because cash awaiting a payment is assumed to earn a fixed 3%:
re-solving the LP on simulated January 2027 curves gives 1.64% at today's 5-year rate plus 0.57 points
per point of rate (0.9% to 2.5% across scenarios; `scripts/ladder_premium.py`). Scoring with that
slope changes the IPS median by +$53 and its 5th percentile by +$0.7k; with the lower level as well,
+$0.7k and +$1.2k. The engine keeps the constant 1.8%: it is slightly cautious, and in low-rate
scenarios the slope relies on cash earning 3% above market rates, which can make the premium negative.

**Rate stress.** Rates 0.75 points lower before the January 2027 lock, and expected to stay there (the
long-run level moves with today's, matching the "unchanged" expectation): the IPS median falls from
$195.7k to $159.9k, and still funds every payment. 0.75 points higher: $231.2k.

**Stock-rate correlation.** Correlations come from Aug 2017-Sep 2026, the youngest fund's history,
where the S&P 500's monthly correlation with the 5-year rate change is -0.16 (the model's core: -0.17).
That window averages two regimes, +0.41 in 2017-2021 and -0.47 since 2022, and over longer history the
sign follows inflation: 1994-1999 -0.30, 2000-2021 +0.36, 1994-2026 +0.09. A positive correlation is
the bad case for an open ladder (rates fall as stocks fall). Re-scoring with the equity-rate block
rescaled to each regime (`scripts/stock_rate_corr.py`): the IPS median stays within $0.2k and its 5th
percentile ranges from $144.6k (the 2000-2021 regime) to $146.3k (today's). The index-first
60/40, which leaves the liabilities open, is exposed: its 5th percentile runs from $47.8k
to $27.8k. Crash months show no flight to quality on average either: in the worst 5% of equity months
since 2007 the 5-year rate rose 0.05 points on average and fell in 58% of them, and the "crash
correlation" of 0.39 rests on 12 months (p = 0.11 against no extra tail dependence;
`scripts/crash_comovement.py`).

## Part 2a — ETF core (Black-Litterman)
Nine equity groups, one ETF each (VUG, VTV, VB, VGK, BBJP, EPP, BBCA, EMXC, MCHI). Bonds in the growth
sleeve are IBTM.

- **Prior:** market-cap weights from iShares holdings: ACWI for regions, Russell 1000 Growth and
  Value for the US style split, and the CRSP breakpoints that VUG/VTV/VB use for size. Risk aversion
  δ = 1.74 makes the market earn the 13-firm median 10-year forecasts: each region's geometric
  forecast plus half its own basket variance, weighted by region (market geometric 6.38%).
- **Views** (`config/cma.yaml`): international developed minus US (+0.80%), emerging minus developed
  (+0.50%), US value minus growth (+2.62%: Vanguard's +3.0% and the 1927-2026 Kenneth French history
  of +2.2%), US small minus large (+0.90%: J.P. Morgan, Vanguard and the French history). Each view's
  uncertainty is the spread across the firms that publish it, with a floor of 1.5% (2.5% when only
  one firm does). Long-run history counts toward a view's size but not its uncertainty: the value
  premium was +2.2% a year since 1927 but -3.2% since 2007 (`scripts/factor_evidence.py`). τ = 0.05.
  Views are converted to arithmetic returns leg by leg, each leg adding half its own basket variance.
  All four views are relative, so the posterior is shifted to give the market its prior (consensus)
  return (`black_litterman.anchor_to_prior`): otherwise the views also move the market's level, by
  +0.11 to +0.39 points depending on small changes in risk (the correlation target, the EM and China
  volatilities). Weights are unchanged by the shift.
- **Constraints:** each group within [0.5×, 2×] of market weight (and at most +10pp); no look-through
  overweight in tech/communication or China+Taiwan, the two concentrations the client background
  check flags.
- **Resampling:** one optimum sits on these limits and swaps weight between near-identical funds
  when an input moves slightly. Across τ 0.025-0.10 and value-view uncertainty 1.5-5 points it moved
  BBJP between 2.6% and 7.8%. The weights are the average optimum over 500 draws of expected returns
  from the posterior (Michaud 1998), with the prior covariance as risk. Over the same grid BBJP stays
  at 6.7-6.9% (`reports/bl_sensitivity.csv`).

| ETF | Market | Black-Litterman |
|---|---:|---:|
| VUG | 26.8% | 16.3% |
| VTV | 29.9% | 31.0% |
| VB | 8.7% | 12.8% |
| VGK | 13.8% | 16.6% |
| BBJP | 5.2% | 6.8% |
| EPP | 2.2% | 2.9% |
| BBCA | 3.0% | 3.9% |
| EMXC | 8.6% | 7.8% |
| MCHI | 1.9% | 1.9% |

The core holds 60% US, 30% developed and 10% emerging stocks, against the market's 65/24/10: the
developed-beats-US view moves about 5 points out of the US. It expects 6.6% a year after fees
(market 6.4%), with 15.2% volatility, a 0.10% average fee and a 1.25% tracking error. Look-through
tech/communication is 29.9% (market 36.0%); China+Taiwan is 5.0% (market 5.2%).

Monte Carlo, median facility (IPS rules, 20,000 scenarios, `reports/report_numbers.json`):

| Sleeve | Views right, $25 trades | Views right, no commissions | Views wrong (equilibrium), $25 trades |
|---|---:|---:|---:|
| VTI/VEA/VWO 60/30/10 (3 funds) | $196.2k | $197.0k | $196.1k |
| Black-Litterman core (9 funds) | $195.7k | $197.2k | $195.1k |

The core's views are worth about $0.2k before commissions. Its six extra funds cost about $0.7k in
WInS commissions, so with $25 trades it trails the 3-fund portfolio by $0.5k. So the core is a
risk-control choice, not a return engine: it holds technology and China+Taiwan below the market's
share for about 0.3% of the median. Equity selection is second-order for Laura; the funding
decisions in Part 1 dominate.

### Fund scorecard (`scripts/fund_scorecard.py`, `reports/fund_scorecard.csv`)
Every equity fund the WInS account has held, ranked on one index from each model: the nine core
funds plus ESGV and VSGX, which the previous team bought on Oct 21, 2026 and we sold on Oct 23. Each
index is scaled so the average of the 11 funds is 50 and one standard deviation is 10 points; the
overall score is the average of the three.

- **Quantitative index:** the S&P 500 screen's return-quality score (Part 2b), 0.5 z(12-1 month
  momentum) + 0.5 z(3-year Sharpe ratio), on each fund's total returns to Sep 30, 2026.
- **Black-Litterman index:** how far the custom BL model's views move a fund's expected return above
  or below what its market risk alone implies (posterior minus equilibrium excess return), less its
  fee. The market portfolio scores zero. ESGV and VSGX are mapped onto the nine core funds by
  returns-based style analysis (60 months, R² 0.99 for both): ESGV is 61% VUG, 28% VTV, 10% VB.
- **Qualitative index:** the qualitative model's two fund limits, look-through tech/communication
  and China+Taiwan (Bigdata.com ETF tearsheets, Oct 23, 2026; `config/fund_lookthrough.yaml`),
  -0.5 z(tech/communication) - 0.5 z(China+Taiwan).

| Fund | Quantitative | Black-Litterman | Qualitative | Overall | Rank | BL weight (market) |
|---|---:|---:|---:|---:|---:|---:|
| BBCA | 55.6 (2) | 52.8 (6) | 59.4 (2) | 55.9 | 1 | 3.9% (3.0%) |
| VTV | 54.3 (5) | 55.5 (3) | 57.3 (4) | 55.7 | 2 | 31.0% (29.9%) |
| EMXC | 64.0 (1) | 63.9 (1) | 37.8 (10) | 55.2 | 3 | 7.8% (8.6%) |
| VGK | 49.1 (8) | 55.0 (4) | 58.9 (3) | 54.3 | 4 | 16.6% (13.8%) |
| VSGX (sold) | 54.9 (4) | 56.8 (2) | 48.2 (7) | 53.3 | 5 | 0% |
| EPP | 45.0 (9) | 50.8 (7) | 61.7 (1) | 52.5 | 6 | 2.9% (2.2%) |
| BBJP | 55.2 (3) | 48.1 (8) | 53.4 (6) | 52.2 | 7 | 6.8% (5.2%) |
| VB | 44.3 (10) | 54.9 (5) | 56.0 (5) | 51.7 | 8 | 12.8% (8.7%) |
| ESGV (sold) | 52.4 (6) | 37.6 (10) | 45.5 (8) | 45.1 | 9 | 0% |
| VUG | 50.3 (7) | 27.4 (11) | 39.6 (9) | 39.1 | 10 | 16.3% (26.8%) |
| MCHI | 24.8 (11) | 47.3 (9) | 32.3 (11) | 34.8 | 11 | 1.9% (1.9%) |

The scorecard ranks; it does not set weights, which come from the BL optimisation and its limits.
The two agree where it matters: the funds ranked last overall (VUG, MCHI) are the ones the limits
hold at or below market weight, and VUG is the core's largest underweight (16.3% against 26.8%).
ESGV ranks 9th: the views expect it to earn 0.66 points a year less than its risk implies, because
it behaves like a growth fund, and 56% of it is tech/communication. VSGX ranks 5th on the strength
of its international and emerging tilt, which the core already holds fund by fund. It fails the
qualitative limit: held as 40% of stocks, as the previous team held it, its 19.2% in China+Taiwan
puts the portfolio at 7.7% against the market's 5.2% (the core: 4.9%).

## Part 2b — stock satellite (tested, not adopted)
The IPS holds no individual stocks. The plan runs entirely in WInS, and under its $25 commissions the
35-stock satellite below lowers the median facility (Monte Carlo verdict). It is kept here as a tested
alternative.

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
weights (18.2%). The test uses names selected with overlapping data, so it ranks the rules but flatters
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

- **Equilibrium:** CAPM-implied return from its covariance with the market (beta 0.87), so
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
| Equilibrium (no alpha) | $25 per trade (WInS) | −$4.8k | −$4.8k | −$5.0k |
| BL posterior (+0.22%) | $25 per trade (WInS) | −$4.5k | −$4.3k | −$4.3k |
| BL posterior (+0.22%) | none | +$0.1k | +$0.4k | +$0.4k |
| Alpha as hoped (+0.82%) | $25 per trade (WInS) | −$4.3k | −$3.8k | −$3.6k |

Commissions are charged as if paid from the portfolio when incurred (they lose the returns the
portfolio would have earned), which raises the satellite's cost by about $0.5k against charging them
in 2033 at face value. The January 2033 sale that pays the contribution in cash is charged too: one
ticket per fund still held (nine for the core, $225; 35 more for the satellite, $875;
`EngineConfig.sell_at_settlement`).

The base BL core median in this run is $195.8k. It is $0.1k above the core's own run because the
satellite, as one more asset with its own view, moves the core funds' posterior returns by a few basis points;
comparisons within the run are unaffected. Funding stays 100% in every case: the satellite cannot
touch the payments. At a 20% share, each extra 1pp of alpha moves the median by about $759. With $25
commissions the satellite needs about 5.7pp a year of alpha beyond the posterior to break even, which
is not credible. The cost is fixed per trade rather than proportional, so at WInS commission levels a
smaller satellite is no cheaper. Without commissions it is roughly neutral.

Commission assumptions are an upper bound. Every invest or rebalance event trades all 35 names
(34 more trades than one ETF), except top-ups under $10k, which are not charged (in practice they
would wait in the ETFs). The annual review replaces three names (six trades, $150).

**Conclusion.** The satellite is a values-alignment and engagement tool, not a return engine. At a
commission-free broker it would be roughly outcome-neutral in the median (slightly negative in the tails once
its selection bias is corrected, see Caveats) and adds no tech or China concentration: look-through
tech/communication is 24.7% at a 20% satellite, against 36.0% for the market. Under WInS's $25
commission it costs about 2.2% of the median facility. The plan runs entirely in WInS, so the IPS holds no satellite.

### WInS implementation (whole shares, Oct 20, 2026 closes) — `reports/satellite_wins_orders.csv`
| Budget | Names buyable | Commissions | Max weight error |
|---|---:|---:|---:|
| WInS mirror, 20% of $60k equity ($12,000) | 30 of 35 | $750 (6.3%) | 2.3pp |
| Plan, Jan 2028, 20% of ~$90k equity ($18,000) | 33 of 35 | $825 (4.6%) | 2.3pp |

At $12,000, one share each of GE, KEYS, PH, EME and GWW costs more than 1.5× its target, so these
names get zero shares. That is a second reason the IPS holds no satellite.

## Policy study (`scripts/policy_study.py`, `reports/policy_study.json`)

**The 2031 floor.** The IPS moves 80% of the growth sleeve into IBTM in January 2031 (60% until the
client's decision on October 22, 2026).

| Floor | Median | 5th pct | 95th pct | Secured in 2031 (typical) | 10th-90th pct range (typical) |
|---|---:|---:|---:|---:|---|
| 0% | $199.9k | $140.2k | $290.9k | $0 | $136.0k-$190.9k |
| 40% | $198.1k | $144.6k | $275.7k | $62.9k | $143.7k-$177.0k |
| 60% | $196.9k | $146.1k | $270.2k | $94.3k | $147.6k-$169.4k |
| 80% (IPS) | $195.7k | $146.3k | $266.1k | $125.8k | $151.8k-$162.6k |
| 100% | $195.0k | $146.3k | $263.7k | $157.2k | $156.5k |

"Typical" is the median, across 21 scenarios between the 45th and 55th percentile of January 2031
wealth, of each scenario's own quote (`engine.conditional_2031_band`). A single scenario is noisy:
within that band the floor the IPS buys varies from $148.4k to $176.6k with that month's rates.

Certainty equivalents (CRRA) favour 0%, 40% and 80% for risk aversion 2, 4 and 8. The IPS's 80% is
within $2.7k of the best for each, and 60% and 80% differ by under $1.1k; wealth alone does not
settle it. What changes sharply is what Laura can promise: for $1.2k of
median, an 80% floor secures $31k more and halves the range.

**Contribution share.** 70%, 75%, 80%, 85% and 90% give typical contributions of $137k, $147k, $157k, $166k and $176k and leave
Laura $59k, $49k, $39k, $29k and $20k. This is a preference, not something the model can optimise; the client chose 80%.

**Range calibration on history.** On each of 184 real six-year paths (re-centred, starts 2005-2020),
the model's 10th-90th percentile range, quoted from that path's own January 2031 position, contained
the January 2033 result 98.9% of the time; 0.5% fell below it. As history happened: 98.4%, none below.
So the model's "80% range" behaved like a 98% range: its tails are fatter than history's. The 20th-80th
percentile band held 82.1% of the re-centred results (75.5% as history happened). In the typical
world, 80% of the facility gives:

| Quote for co-sponsors (typical 2031 world) | Contribution range |
|---|---|
| Model 10th-90th percentile (historically ~98% of outcomes) | $151.8k-$162.6k |
| 20th-80th percentile (historically ~80% of outcomes) | $153.2k-$160.4k |

The IPS quotes the first. The narrower band was chosen on the same overlapping history (about four
independent six-year windows) and held only 75.5% of outcomes as history happened, and promising too
much is the risk the case warns about. Both quotes sit above the $125.8k already secured by the floor. `scripts/report_numbers.py` writes both for the bad, typical and good
worlds (`quotes_2031`).

**Reverse stress test.** The worst 1% of futures average a $120.8k facility, with stocks down 29%
over 2028-2033 and a worst 12 months of -30%; rates barely move. The chance the facility ends below
$100k is 0.03%, below $120k 0.4%, below $140k 2.8%.

## Changes adopted in October 2026
Adopted into the headline numbers after the October 21-22 improvement loop and the October 23 review
(`docs/VALIDATION.md`, sections 10-11): Gaussian rate shocks; the DGBAS-based AR(2) Taiwan building-cost
process at the 1991-2026 average drift, correlated with USD/TWD as history shows (real median $156.8k -> $165.4k);
commissions compounded as if paid when incurred, plus sale tickets in January 2033 (an upper bound: with
an 80% floor the matured IBTM usually covers the contribution); the 2031 floor move charged one ticket
per fund; no commission on rounding residue under $1; rate-factor persistence bias-corrected (wider
long-horizon rate spread, median unchanged); J.P. Morgan's 2027 assumptions and Vanguard's September 30,
2026 run, including its value/growth and small/large figures; short-history EM and China volatilities
scaled to include 2008; the Black-Litterman market level anchored to the 13-firm consensus (a judgment:
left alone, the relative views lift the market's expected return by 0.1 to 0.4 points); real Taiwan cost
paths in the replay; the 2031 quote from a band of scenarios.

Client decisions, October 22-23, 2026: the 2031 floor raised from 60% to 80% of the growth sleeve; 80% of
the facility fund contributed; no stock satellite; everything in WInS, so USD/TWD stays unhedged (no
currency forwards) and no STRIPS.

Built but left off, with the evidence for each: expected-return uncertainty (no material effect), equity
correlations shrunk toward their average rather than zero (forecast worse out of sample), GARCH volatility
clustering (worse calibrated on history), a USD/TWD drift (the forward is a biased forecast for TWD), a
rate-dependent ladder premium (+$53 median, and it relies on 3% cash in low-rate scenarios). Checked and found not to need
a change: the stock-rate correlation regime (the IPS barely moves), crash-month co-movement (not
significant), and long-horizon mean reversion in stocks or USD/TWD (neither significant). The policy
search (`scripts/policy_search.py`, 3,456 policies) and robustness study (`scripts/policy_robust.py`)
put the 60/40 mix with an 80% floor close to the best certainty equivalent at every risk aversion tested;
mixes with 40% stocks give a better bad case for a lower median, a preference the IPS leaves at 60/40.
Study reports in `reports/` that `scripts/run_all.py` does not regenerate (for example
`taiwan_variants.csv`, `rate_tails_impact.csv`, `policy_search.csv`) used the defaults of their day.

## Caveats
- The analyst judgments in `qualitative_judgments.csv` rest on the public record to mid-2026, then on
  the October 2026 news check. They are judgments, and the rationale column says why.
- The basket's history before 2014-2016 (HLT, KEYS, HWM) is renormalised over the names that existed.
  It is used for volatility and correlation only, never for expected return.
- The satellite's risk is understated, and now measured (`scripts/satellite_oos.py`): re-running the
  quantitative screen at four dates in 2023 and following each basket for about three years, the
  chosen names' volatility fell by a factor of 0.86 out of sample, against 0.77 for random 35-name
  baskets from the same universe over the same windows (the market got calmer for everyone). Relative
  to random baskets, selection made in-sample risk look about 12% too low; out of sample the
  "low-risk" picks were no calmer than random baskets. Correcting for it
  (`scripts/satellite_risk_sensitivity.py`) raises the satellite's volatility from 15.1% to 16.9% and
  its beta from 0.89 to 0.99: at a 20% share and no commissions the median stays positive (+$0.4k as
  estimated, +$0.5k to +$0.7k corrected), but the 5th percentile goes from +$0.3k to -$0.2k to -$0.3k
  against the core alone; with $25 commissions from -$4.4k to -$4.8k to -$4.9k. Thin evidence: four
  overlapping screens, one market episode, today's index members only, and the qualitative judgments
  could not be re-run historically.
- The Taiwan building-cost drift (2.85%, the 1991-2026 average) is a judgment backed by a real-time
  test; the last ten years' 3.78% would lower the real median by about $9k.
- Locked payments are certain only if cash awaiting a payment earns at least 3% (see "How certain is
  'certain'?"); the Monte Carlo does not simulate that reinvestment rate.

## Reproduce
Every run is anchored to the dates in `config/asof.yaml` (curve date, last month of data, price date);
the WInS account's cash and holdings are in `config/wins_account.yaml`. To refresh before the Final
Report, change the dates and run `python scripts/run_all.py --refresh`.
```
python scripts/run_all.py              # every script, the studies the docs quote, then the doc check (~100 s)
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

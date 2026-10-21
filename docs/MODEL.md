# Model: how Laura's portfolio is built and scored

Every design choice below is scored the same way: the Part 1 Monte Carlo (20,000 scenarios,
common random numbers, IPS rules) measures what it does to Laura's January 2033 facility
contribution and to the certainty of her ten $50,000 payments. Results are as of the October 20, 2026
Treasury curve and September 30, 2026 month-end prices.

## Part 1 — funding model
Treasury par curve → zero curve → cheapest WInS-permitted cash-flow-matched ladder (linear program),
and a monthly scenario generator: Nelson-Siegel rates, K equity assets, inflation, USD/TWD and Taiwan
building costs, with Student-t shocks. The engine applies a strategy month by month (lock schedule,
mix, rebalancing band, 2031 floor, contribution rule). `docs/VALIDATION.md` checks this against the
former team's guide and Plans v2.

Market inputs (all keyless):
- **Expected rates: unchanged on average.** A 1994-2020 test (`scripts/rate_path_study.py`) forecast
  the curve 74 months ahead from 320 month-ends. Error in the cost of ten payments: unchanged 7.7%,
  forwards minus the Kim-Wright term premium 7.5%, pure forwards 10.0%. Unchanged also has the
  smallest bias, so it stays. Run today with the Kim-Wright path instead, the median facility is
  $0.7k lower (`reports/rate_path_scenario.json`).
- **Inflation:** reverts from September's 3.7% toward 7-year breakeven inflation from Treasury's
  nominal and TIPS par curves (2.37% on October 20, 2026). TIPS are a gauge only; WInS forbids them.
- **USD/TWD:** the Federal Reserve's H.10 noon buying rate, from 2000 (replaces Yahoo's series, which
  needed bad prints filtered out).
- **Taiwan building costs:** still assumed (4% a year, 1.5% volatility); Taiwan's statistics sites
  were unreachable from this environment.

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
| VTI/VEA/VWO 60/30/10 (3 funds) | $197.9k | $198.6k | $197.3k |
| Black-Litterman core (9 funds) | $197.9k | $199.0k | $196.7k |

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
Re-estimated every year from 2019 to 2026, it had lower realised volatility (16.3%) than average- or
Ward-linkage HRP (16.3%, 16.9%), inverse-variance (17.0%) or equal weights (18.5%).

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
| Equilibrium (no alpha) | $25 per trade (WInS) | −$3.2k | −$3.3k | −$3.3k |
| BL posterior (+0.22%) | $25 per trade (WInS) | −$2.9k | −$2.8k | −$2.5k |
| BL posterior (+0.22%) | none | +$0.1k | +$0.4k | +$0.7k |
| Alpha as hoped (+0.82%) | $25 per trade (WInS) | −$2.7k | −$2.3k | −$1.7k |

The base BL core median in this run is $197.6k. It is $0.4k below the core's own run because the satellite
view, being relative, lowers the core funds' posterior returns by a few basis points; comparisons
within the run are unaffected. Funding stays 100% in every case: the satellite cannot touch the
payments. At a 20% share, each extra 1pp of alpha moves the median by about $880. With $25 commissions
the satellite needs about 3.2pp a year of alpha beyond the posterior to break even, which is not
credible. The cost is fixed per trade rather than proportional, so at WInS commission levels a
smaller satellite is no cheaper. Without commissions it is roughly neutral.

Commission assumptions are an upper bound. Every invest or rebalance event trades all 35 names
(34 more trades than one ETF), except top-ups under $10k, which are not charged (in practice they would wait in the ETFs). The annual review
replaces three names (six trades, $150).

**Conclusion.** The satellite is a values-alignment and engagement tool, not a return engine. At a
commission-free broker it is outcome-neutral and adds no tech or China concentration: look-through
tech/communication is 24.7% at a 20% satellite, against 36.0% for the market. Under WInS's $25
commission it costs about 1.4% of the median facility.

### WInS implementation (whole shares, Oct 20, 2026 closes) — `reports/satellite_wins_orders.csv`
| Budget | Names buyable | Commissions | Max weight error |
|---|---:|---:|---:|
| WInS mirror, 20% of $60k equity ($12,000) | 30 of 35 | $750 (6.3%) | 2.3pp |
| Plan, Jan 2028, 20% of ~$90k equity ($18,000) | 33 of 35 | $825 (4.6%) | 2.3pp |

At $12,000, one share each of GE, KEYS, PH, EME and GWW costs more than 1.5× its target, so these
names get zero shares. Hence the IPS keeps the satellite out of WInS.

## Policy study (`scripts/policy_study.py`, `reports/policy_study.json`)

**The 2031 floor.** The IPS moves 60% of the growth sleeve into IBTM in January 2031.

| Floor | Median | 5th pct | 95th pct | Secured in 2031 (typical) | 80% range (typical) |
|---|---:|---:|---:|---:|---|
| 0% | $201.1k | $141.8k | $290.7k | $0 | $145.8k-$203.2k |
| 40% | $199.0k | $145.9k | $275.7k | $67.1k | $154.0k-$188.5k |
| 60% (IPS) | $197.9k | $147.4k | $269.8k | $100.7k | $158.3k-$181.2k |
| 80% | $196.7k | $148.1k | $265.6k | $134.3k | $162.5k-$174.0k |
| 100% | $195.5k | $147.5k | $262.8k | $167.9k | $167.1k |

Certainty equivalents (CRRA) favour 0%, 40% and 80% for risk aversion 2, 4 and 8, but differ by under
$1.1k; wealth alone does not settle it. What changes sharply is what Laura can promise: for $1.2k of
median, an 80% floor secures $34k more and halves the range.

**Contribution share.** 75%, 85% and 95% give typical contributions of $148k, $168k and $188k and leave
Laura $49k, $30k and $10k. This is a preference, not something the model can optimise.

**Range calibration on history.** On each of 184 real six-year paths (re-centred, starts 2005-2020),
the 80% range quoted from that path's own January 2031 position contained the January 2033 result
98.4% of the time; 1.1% fell below it. As history happened: 97.8%, none below. The range is
conservative (the model's tails are fatter than history), but the paths overlap, so the evidence is
thin.

**Reverse stress test.** The worst 1% of futures average a $119.9k facility, with stocks down 28%
over 2028-2033 and a worst 12 months of -30%; rates barely move. The chance the facility ends below
$100k is 0.03%, below $120k 0.4%, below $140k 2.8%.

## Caveats
- The analyst judgments in `qualitative_judgments.csv` rest on the public record to mid-2026, then on
  the October 2026 news check. They are judgments, and the rationale column says why.
- The basket's history before 2014-2016 (HLT, KEYS, HWM) is renormalised over the names that existed.
  It is used for volatility and correlation only, never for expected return.
- The engine charges commissions at the end and does not compound them, which slightly understates
  their cost.
- The satellite's risk is probably understated: names were picked for low past volatility and
  drawdown, and the correlation window overlaps the screening window, so its beta (0.89) and
  volatility (15.1%) are likely biased low.

## Reproduce
```
python scripts/build_core.py           # ETF core: reports/core_bl.csv, core_scoring.csv
python scripts/build_satellite.py      # satellite: reports/satellite_*.csv (add --rescreen to refetch)
python scripts/validate_model.py       # how good is it: generator checks, convergence, replay, BL sensitivity
python scripts/report_numbers.py       # headline numbers for the IPS and Final Report
python scripts/wins_rebalance.py       # orders that bring WInS in line with the IPS
python scripts/wins_ladder_check.py    # matching test for the ladder held in WInS
python scripts/factor_evidence.py      # Kenneth French evidence for the views
python scripts/rate_path_study.py      # which expected rate path; Kim-Wright scenario
python scripts/policy_study.py         # floor frontier, range calibration, reverse stress test
```

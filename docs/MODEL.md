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

## Part 2a — ETF core (Black-Litterman)
Nine equity groups, one ETF each (VUG, VTV, VB, VGK, BBJP, EPP, BBCA, EMXC, MCHI). Bonds in the growth
sleeve are IBTM.

- **Prior:** market-cap weights from iShares holdings: ACWI for regions, Russell 1000 Growth and
  Value for the US style split, and the CRSP breakpoints that VUG/VTV/VB use for size. Risk aversion
  δ = 1.80 makes the market earn the 13-firm median 10-year forecasts: each region's geometric
  forecast plus half its own basket variance, weighted by region (market geometric 6.41%).
- **Views** (`config/cma.yaml`): international developed minus US (+0.80%), emerging minus developed
  (+0.50%), US value minus growth (+3.50%, Vanguard only), US small minus large (+0.95%). Each view's
  uncertainty is the spread across the firms that publish it, with a floor of 1.5% (2.5% when only
  one firm does). τ = 0.05. Views are converted to arithmetic returns leg by leg, each leg adding half
  its own basket variance.
- **Constraints:** each group within [0.5×, 2×] of market weight (and at most +10pp); no look-through
  overweight in tech/communication or China+Taiwan, the two concentrations the client background
  check flags.
- **Resampling:** one optimum sits on these limits and swaps weight between near-identical funds
  when an input moves slightly. Across τ 0.025-0.10 and value-view uncertainty 1.5-5 points it moved
  BBJP between 2.6% and 8.4%. The weights are the average optimum over 500 draws of expected returns
  from the posterior (Michaud 1998), with the prior covariance as risk. Over the same grid BBJP stays
  at 6.6-6.9% (`reports/bl_sensitivity.csv`).

| ETF | Market | Black-Litterman |
|---|---:|---:|
| VUG | 26.8% | 15.4% |
| VTV | 29.9% | 32.8% |
| VB | 8.7% | 12.6% |
| VGK | 13.8% | 16.0% |
| BBJP | 5.2% | 6.8% |
| EPP | 2.2% | 2.9% |
| BBCA | 3.0% | 3.8% |
| EMXC | 8.6% | 7.8% |
| MCHI | 1.9% | 1.9% |

The core keeps 61% US, 29% developed and 10% emerging stocks. It expects 6.7% a year after fees
(market 6.4%), with 14.9% volatility, a 0.10% average fee and a 1.36% tracking error. Look-through
tech/communication is 29.5% (market 36.0%); China+Taiwan is 4.9% (market 5.2%).

Monte Carlo, median facility (IPS rules, 20,000 scenarios, `reports/report_numbers.json`):

| Sleeve | Views right, $25 trades | Views right, no commissions | Views wrong (equilibrium), $25 trades |
|---|---:|---:|---:|
| VTI/VEA/VWO 60/30/10 (3 funds) | $197.6k | $198.3k | $197.3k |
| Black-Litterman core (9 funds) | $197.7k | $198.8k | $196.7k |

The core's views are worth about $0.6k before commissions. Its six extra funds cost about the same in
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
- **Stock-selection view:** +1.0% a year over the style benchmark, std 2.5%. The evidence is the
  low-risk, quality and momentum premia, taken at about a third to a half of their long-short size
  for a long-only basket and halved again for post-publication decay. The values gates and the
  analyst judgments get no alpha.
- **Posterior:** +0.27% a year. Blending a one-source view with equilibrium shrinks it this much.
  The alpha view is already an arithmetic return, so it gets no geometric-to-arithmetic conversion.

### Monte Carlo verdict (median facility vs the BL core alone, IPS rules)
| Beliefs | Commissions | +10% | +20% | +30% |
|---|---|---:|---:|---:|
| Equilibrium (no alpha) | $25 per trade (WInS) | −$3.2k | −$3.3k | −$3.3k |
| BL posterior (+0.27%) | $25 per trade (WInS) | −$2.9k | −$2.7k | −$2.4k |
| BL posterior (+0.27%) | none | +$0.2k | +$0.4k | +$0.8k |
| Alpha as hoped (+1.0%) | $25 per trade (WInS) | −$2.5k | −$2.1k | −$1.4k |

The base BL core median in this run is $197.3k. It is $0.4k below the core's own run because the satellite
view, being relative, lowers the core funds' posterior returns by 6-10 basis points; comparisons
within the run are unaffected. Funding stays 100% in every case: the satellite cannot touch the
payments. At a 20% share, each extra 1pp of alpha moves the median by about $870. With $25 commissions
the satellite needs about 3.1pp a year of alpha beyond the posterior to break even, which is not
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
```

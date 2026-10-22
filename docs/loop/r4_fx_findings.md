# r4-fx findings: the USD/TWD drift

The Gemini worker collected the Taiwan money-market rates, wrote the loader and the forecast-rule study,
and then hit its quota (its study was preserved as an unverified WIP commit). The planner (Claude)
re-downloaded the rates and confirmed them, then added the central bank's actual forward rates, the
forward checks, the variants and this document. Numbers come from `scripts/fx_drift_study.py`
(`reports/fx_drift_study.csv`, `reports/fx_forward_check.csv`) and `scripts/fx_variants.py`
(`reports/fx_variants.csv`). Sources: `data/raw/twrates/SOURCES.md`.

## Data
- Taiwan 90-day commercial paper (secondary market) and the overnight call rate: CBC Table 29.F, monthly
  1987-2026 (re-downloaded by the planner: all 472 rows identical).
- USD/TWD forward rates, 10-180 days: CBC Table 31.C, monthly 1991-2026.
- US 3-month Treasury yield (cached Treasury par curves) and month-end USD/TWD (Federal Reserve H.10, from 2000).

## Which forecast rule works for USD/TWD (2000-2026)
Forecast error of the log change (RMSE; bias = forecast minus outcome):

| Horizon | Random walk | Full CIP drift | Half CIP | Trailing 10-year drift | Independent windows |
|---|---|---|---|---|---:|
| 12 months | 5.08% (bias -0.01%) | 5.33% (-0.72%) | 5.14% (-0.37%) | 5.37% (-0.50%) | 25 |
| 36 months | 6.95% (+0.61%) | 7.78% (-0.84%) | 7.09% (-0.12%) | 8.60% (-2.95%) | 7 |
| 72 months | 6.95% (+2.56%) | 8.60% (+0.29%) | 6.90% (+1.42%) | 10.11% (-4.62%) | 3 |

Fama regression of the realised change on the CIP drift (Newey-West errors, lag = horizon): slope
0.02 (se 0.41) at 12 months, 0.09 (0.28) at 36, 0.17 (0.22) at 72. Each rejects an unbiased forward
(slope 1: t = -2.4, -3.3, -3.7) and none rejects a random walk (slope 0).

The actual forward market says the same. The annualised 180-day forward premium tracks the CIP drift
(correlation 0.89; mean -1.61% vs -0.76% a year, mostly because commercial paper is a credit rate).
Regressing the realised 6-month change on the actual 6-month premium gives a slope of -0.09 (se 0.51;
t(slope = 1) = -2.1), and the random walk forecasts better than the forward (RMSE 3.88% vs 4.03%).
This is the forward premium puzzle, holding for TWD. Half CIP edges the random walk at 72 months
(6.90% vs 6.95%), on three independent windows: noise.

## What it does to the facility in Taiwan terms
IPS headline parameters, Taiwan building costs from the fitted AR(2) at the 2.85% full-sample drift.
The nominal median is $197,910 in every row.

| USD/TWD drift | Real median | Real p5 | Real p95 | USD/TWD change 2027-33 (p50) |
|---|---:|---:|---:|---:|
| 0 (random walk, today) | $167,355 | $113,371 | $247,964 | +0.0% |
| -1.14%/yr (half the forward) | $156,272 | $105,862 | $231,542 | -6.6% |
| -2.07%/yr (CIP, Aug 2026) | $147,798 | $100,122 | $218,987 | -11.7% |
| -2.28%/yr (actual 180-day forward, Aug 2026) | $145,922 | $98,851 | $216,208 | -12.8% |

The FX assumption moves the real median by up to $21k, more than the Taiwan cost drift does (up to $11k).

## Recommendation (planner)
Keep `fx_drift = 0` for the expected outcome: on Taiwan's own history the random walk is the better
forecast at every horizon tested, and the forward is biased. But report the forward case next to it,
because it is not only a forecast: it is the price of certainty. A client who wants the facility's
Taiwan-dollar value fixed today can hedge, and hedging at the forward locks in about 12.8% fewer
Taiwan dollars than the unhedged expectation over 2027-2033 (real median $145.9k instead of $167.4k),
in exchange for removing the -20% to +25% FX range. Whether to hedge is the client's decision.

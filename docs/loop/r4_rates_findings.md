# r4-rates findings: the rate shocks' tails

Tasks 1-3 were done by the Gemini worker (commits cbc7659, 0017817, 099896e). Its run stopped on a
Gemini quota limit before Task 4; this document was written by the planner (Claude) from the
committed reports, after re-running the tests and the pipeline. Every number below is printed by
`scripts/rate_tails.py` (`reports/rate_tails.csv`), `scripts/rate_tails_impact.py`
(`reports/rate_tails_impact.csv`) or `lgm.calibrate.calibrate_block_tails()`.

## What was built (opt-in; defaults reproduce every existing report byte-for-byte)
New `ESGParams` fields: `rate_dof` (None = shares `t_dof`, as today; `"gaussian"`; or a number for an
independent Student-t mixing variable), `rate_shared` (the share of the equity mixing variance the
rate block also takes), and `infl_dof` and `fx_dof` with the same meaning. The mixing variables
scale the uncorrelated draws before the Cholesky factor. Each has unit mean square, so every
covariance is preserved exactly. A rate shock still inherits a little of the equity tail through
its correlation with equities.

## The tails, 5-year zero rate (history: 1994-2026 month ends; model: 20,000 scenarios)
| | 1-month sd | excess kurtosis | min | p0.1 | 2-month min | 74-month sd |
|---|---:|---:|---:|---:|---:|---:|
| History | 0.26 | 0.59 | -0.81 | -0.80 | -1.30 | 1.84 |
| Today (shared t5) | 0.26 | 3.22 | -1.99 | -1.16 | -2.56 | 1.25 |
| `rate_dof="gaussian"` | 0.26 | 0.05 | -1.16 | -0.80 | -1.65 | 1.26 |
| `rate_dof=14` | 0.26 | 0.59 | -1.26 | -0.88 | -1.63 | 1.27 |
| `rate_dof=8` | 0.26 | 1.14 | -1.61 | -1.01 | -2.53 | 1.27 |
| `rate_shared=0.10` | 0.26 | 0.10 | -1.14 | -0.82 | -1.62 | 1.26 |
(percentage points; the 10-year rate gives the same picture)

Gaussian rate shocks reproduce history's worst 0.1% of months exactly; t14 reproduces its kurtosis.
Both remove the 2-5 point jumps. The 74-month spread is lower than history's in every variant; history's
includes the 1994-2021 secular fall in rates, which the "unchanged on average" expectation leaves out
by design.

## Crash co-movement: lost nothing, because there was nothing to lose
The worry was that a shared mixing variable is what makes stocks and rates move together in crashes.
In history the correlation between the equity core's return and the 5-year rate change is 0.06 over
all months and 0.39 in the worst 5% of equity months (VTI: 0.09 and 0.15). The model with today's
shared t5 gives 0.02 and 0.03. A mixing variable scales shocks; it cannot create a correlation that
appears only in crashes. Every variant scores the same here, so switching the rate tails costs
nothing. Reproducing crash-only co-movement would need a regime or copula model, a separate project.

## Degrees of freedom: use the moment estimates, not the MLE
`calibrate_block_tails()` reports two estimates per series. The MLE for the level factor (2.03), the
5-year rate (2.007) and the 10-year rate (2.02) sit on the search bound of 2: they are the edge of
the box, not estimates, and they contradict the same series' kurtosis-implied values (6.9, 14.1,
10.6). The likely cause is heteroskedasticity: the 2009-2021 near-zero-rate years contribute many
tiny changes, which a constant-variance t-fit reads as a sharp peak. The recommendation rests on the
tail quantiles above, not on either estimate. Inflation residuals are genuinely fat-tailed (excess
kurtosis 5.7, moment dof 5.1), so `infl_dof` should stay shared. USD/TWD is moderate (1.6, dof 7.8).

## What it changes
Headline IPS (Black-Litterman core, $25 commissions, 20,000 scenarios):

| | min | p1 | p5 | CVaR5 | median | CE gamma 4 | CE gamma 8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Today (shared t5) | $73,736 | $129,285 | $147,375 | $136,215 | $197,910 | $188,488 | $175,077 |
| `rate_dof="gaussian"` | $83,715 | $129,841 | $147,396 | $136,629 | $197,846 | $188,597 | $176,155 |

The headline barely moves; the extreme tail and the risk-averse CE improve a little. The fix matters
for stress tests: with equity tails at t3, the shared mixing variable produced a scenario in which the
5-year rate fell about 4.5 points before the 2027 lock and every policy ended at $0, setting every
CE to $27. With Gaussian rates that scenario disappears: IPS CE at gamma 4 is $188,702, P2361
$188,805, P2305 $190,792. One genuine $0 scenario remains for P0964 (half the ladder left open, all
equity), which is that policy's real risk, not an artifact.

## Recommendation (planner)
Make `rate_dof="gaussian"` the default for headline numbers; keep `infl_dof` and `fx_dof` shared. It is
a correctness fix supported by the data, and it changes the headline median by $64. Adopting it
regenerates every report, so it is listed with the other default changes for the user to approve.

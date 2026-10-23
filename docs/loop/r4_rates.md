# Agent brief r4-rates: the generator's interest-rate tails are far fatter than history's

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), `docs/MODEL.md`,
`src/lgm/esg.py` (`simulate`: how the Student-t mixing variable `w` scales every shock),
`src/lgm/calibrate.py` (`calibrate`, `calibrate_assets`, `factor_history`, `ar1`),
`src/lgm/nelson_siegel.py`, `scripts/report_numbers.py` (the rate stresses), `scripts/policy_robust.py`.
**Your worktree:** branch `r4-rates`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`. You are a new worker on this project: read
`docs/MODEL.md` first.

## 0. What the planner found (reproduce it first)
`esg.simulate` draws ONE Student-t mixing variable per month (`t_dof = 5`) and multiplies **every**
shock by it: equities, the three Nelson-Siegel rate factors, inflation and USD/TWD. That gives
equities the fat tails history shows, but rates did not have them. The planner measured the change in
the 5-year zero rate (1994-2026 month-end history vs 20,000 simulated scenarios from
`lgm.profiles.cs_team()`, seed 11):

| | 1-month: min | p0.1 | sd | 2-month: min | share of 2-month falls > 1.5 pp |
|---|---|---|---|---|---|
| History (394 months; excess kurtosis 0.6) | -0.81 pp | -0.80 | 0.26 | -1.30 pp | 0.000% |
| Model, t_dof = 5 (today) | -1.99 | -1.16 | 0.26 | -2.56 | 0.070% |
| Model, t_dof = 3 | -3.85 | -1.50 | 0.25 | -5.39 | 0.230% |
| Model, Gaussian | -1.22 | -0.81 | 0.26 | -1.63 | 0.005% |

Why it matters: the reserve ladder is bought in January 2027, two months from the curve date. In the
robustness study, under t_dof = 3 one scenario's 5-year rate fell about 4.5 points before the lock,
the ladder could not be completed, the plan ended $450 short, and that one scenario set every
certainty equivalent to about $27. Even at t_dof = 5 the worst scenario has a 2.3-point fall in two
months, beyond anything since 1994. Reproduce these numbers before changing anything.

## 1. Task 1: separate tails for each shock block (opt-in)
Add an option to `ESGParams` that gives the rate factors (and, if the data says so, inflation and
USD/TWD) their own tail treatment while equities keep `t_dof`. Candidates: Gaussian rate shocks; a
second, independent mixing variable with its own degrees of freedom; or a partly shared mixing
variable. Estimate the rate block's degrees of freedom from the NS factor residuals (and do the same
for inflation and FX residuals), by maximum likelihood or by matching kurtosis; report each.
**Keep the correlations.** A common mixing variable is also what makes stocks and rates move
together in crashes, so check it. Report the correlation between equity returns and 5-year rate
changes in the worst 5% of equity months, history vs each option. Default off reproduces today's
scenarios bit-for-bit. Tests in `tests/test_rate_tails.py`. Commit.

## 2. Task 2: validation table (`scripts/rate_tails.py`)
For history, today's model, and each option, per horizon (1, 2, 3, 12 and 74 months), report for
the 5- and 10-year zero rates: sd, excess kurtosis, min, p0.1, p99.9, max. Add the crash-month
correlation from Task 1. Write `reports/rate_tails.csv`. Commit.

## 3. Task 3: what it changes
Headline IPS numbers (as `scripts/report_numbers.py` builds them): funded share, minimum, p1, p5,
CVaR5, median, CE at gamma 4, under today's model and your recommended option. Then re-run the
`tails_tdof3` and `tails_gaussian` rows of `scripts/policy_robust.py`'s shortlist with your option
applied to rates (equity tails as in each row); do this from your own script, without editing
`policy_robust.py`. Write `reports/rate_tails_impact.csv`. Commit.

## 4. Findings `docs/loop/r4_rates_findings.md`
The tables, the degrees of freedom you estimated, the crash-correlation check, and a recommendation.

## Verify / acceptance
- [ ] planner's table reproduced
- [ ] opt-in per-block tails, calibrated, correlations checked, tested; default bit-for-bit
- [ ] `reports/rate_tails.csv` per horizon x variant; `reports/rate_tails_impact.csv`
- [ ] `docs/loop/r4_rates_findings.md` with a recommendation
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes; `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
In `src/lgm/esg.py`, only the shock-generation block at the top of `simulate` (the `z`, `w`,
`chol`, `shocks` lines) and new `ESGParams` fields. **Another worker is editing the Taiwan
building-cost block at the bottom of `simulate` right now**: do not touch it, and keep your changes
in separate lines so the planner can merge both. Also yours: `src/lgm/calibrate.py` (additive),
`scripts/rate_tails.py`, `tests/test_rate_tails.py`, `reports/rate_tails*.csv`,
`docs/loop/r4_rates_findings.md`.

## Not yours to decide
Whether the option becomes the default.

## Budget
About 2 hours and 20 minutes of compute. Keep peak memory low (COMMON.md rule 11).

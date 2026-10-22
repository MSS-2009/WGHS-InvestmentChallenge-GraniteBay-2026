# Agent brief r3-taiwan: refit the Taiwan cost process on monthly changes

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), your findings
`docs/loop/r2_taiwan_findings.md`, `src/lgm/esg.py` (your `tw_cost_phi` code), `config/taiwan.yaml`,
`scripts/taiwan_variants.py`.
**Your worktree:** branch `r3-taiwan`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed, and what the planner found wrong
Your r2-taiwan branch is merged (opt-in; nothing is a default). The plumbing is good: the state
pass-through to `conditional_2031`, the real-cost replay in `backtest.history_paths`, the tests.
The **specification** is not adopted, for a reason the planner checked numerically:
- `tw_cost_phi = 0.9728` is the AR(1) of the **overlapping 12-month inflation rate**. Consecutive
  12-month rates share 11 of 12 months, so even i.i.d. monthly changes give an AR(1) of about
  0.92 (planner's simulation: 0.916). Most of the 0.97 is that overlap, not persistence.
- The code then uses it as the persistence of the **instantaneous** monthly rate. That is a
  different quantity, so it builds multi-year inflation regimes the data does not have: from the
  mean, the 72-month growth spans -15% to +66% (p5-p95), against -0.3% to +44% in history.
- The data says persistence is short: monthly log changes have autocorrelation 0.60 (lag 1),
  0.30 (lag 2) and 0.03 (lag 12). The ratio of the k-month change's standard deviation to the
  i.i.d. scaling is about 1.7 at every horizon from 12 to 72 months (12m: 5.38% vs 3.09%; 72m:
  12.68% vs 7.57%).
- Your `persistent_monthly_today` variant went the other way (72-month p5-p95 of 10.8% to 27.7%,
  narrower than history), so its scaling also looks wrong. Find out why.
So the headline claim "the starting state dominates" holds only under the mis-specified process. It
needs re-testing under one that fits the data. Getting this wrong was a reasonable mistake, and the
planner's round-2 brief pushed you toward the 12-month rate. Finding where it fails is the point.

## 1. Task 1: a process fitted to monthly changes
Fit a low-order model to monthly log changes of the index (AR(1) or AR(2); ARMA(1,1) if clearly
better; state the criterion). Choose the innovation variance so that the model reproduces the
**variance-ratio profile**: the standard deviation of k-month log changes for k = 1, 3, 6, 12, 24,
36, 72, computed on the history the same way. Report the model's and history's values side by side,
per k. Implement it opt-in in `esg.py`, replacing or alongside your `tw_cost_phi` code (an AR(2)
needs two lags of state: carry both through `start` for nested simulations). Starting state: the
last observed monthly changes (Aug and Sep 2026). Tests: default unchanged bit-for-bit; simulated
acf and the variance-ratio profile match the fit within sampling error. Commit.

## 2. Task 2: validate against history, unconditional and conditional
- Unconditional: the 72-month cumulative growth distribution (p5/p50/p95) from the model started at
  the mean, against all rolling historical windows.
- Conditional, the test that matters for "from today": historical windows that **start** when the
  12-month rate is above 5% (list every such start month, with its subsequent 72-month growth),
  against the model started from each of those months' own state. Report per window. There are few
  independent episodes: say how many.
- Drift: report the full-sample (2.85%), last-20-year and last-10-year means, and show the real
  median under each. Choosing among them is a judgment, not yours.
Write `reports/taiwan_validation.csv`. Commit.

## 3. Task 3: rerun the variants
Add your new process to `scripts/taiwan_variants.py` (`fitted_from_mean`, `fitted_from_today`, each at
the three drifts), and regenerate `reports/taiwan_variants.csv`. Keep the old rows for comparison.
Commit.

## 4. Findings `docs/loop/r3_taiwan_findings.md`
Does the starting state matter under the fitted process, and by how much in real-median dollars?
Which specification and drift you recommend, and why.

## Verify / acceptance
- [ ] fitted monthly process, opt-in, with the variance-ratio table per horizon, tested
- [ ] unconditional and per-window conditional validation in `reports/taiwan_validation.csv`
- [ ] variants regenerated, old rows kept
- [ ] `docs/loop/r3_taiwan_findings.md`
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes; `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/esg.py` (the Taiwan-cost part), `src/lgm/engine.py` (only the `start` pass-through line for
your state), `scripts/taiwan_variants.py`, `scripts/taiwan_validation.py`, `tests/test_taiwan_esg.py`,
`config/taiwan.yaml`, `reports/taiwan_*`, `docs/loop/r3_taiwan_findings.md`. Two other workers own
`ladder.py`/`instruments.py` and a new robustness script this round; do not touch those.

## Not yours to decide
The drift and specification used for headline numbers.

## Budget
About 1.5 hours. Keep peak memory low (COMMON.md rule 11).

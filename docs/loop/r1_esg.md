# Agent brief r1-esg: does the scenario generator understate risk?

**Read first, in order:** `docs/loop/COMMON.md` (standing rules; they apply to you in full),
`docs/MODEL.md`, `src/lgm/esg.py`, `src/lgm/calibrate.py`, `src/lgm/growth/scoring.py`,
`scripts/report_numbers.py`, `scripts/policy_study.py` (section 3, range calibration on history),
`config/cma.yaml`.
**Your worktree:** branch `r1-esg`, based on `improve`. It already exists; you are in it.
Call its absolute path `WT`. Run everything as `PYTHONPATH=$WT/src PY ...` (see COMMON.md).

## 0. What is settled
The generator reproduces its own inputs (median returns exactly, volatilities within 0.05 points),
converges (median s.e. $32 over 8 seeds), and its 10th-90th percentile range from a 2031 position was
historically too wide (held 98% of outcomes). Do not re-check those.

## 1. The problem
Two simplifications in `esg.simulate` may matter:
1. **Expected returns are treated as known.** Every scenario uses the same median return per asset
   (`eq_geo`). The 13 firms in `config/cma.yaml` disagree by several points a year about US equities
   (3.1% to 9.0%). Uncertainty about the mean is not in the simulated spread.
2. **Volatility is constant.** Shocks are i.i.d. Student-t months. Real markets cluster volatility
   (2008, 2020), which changes the distribution of multi-year outcomes and of the 2031-2033 window.

The question is whether either matters for the outcomes the model reports, and whether the model
then matches history better or worse. "It makes no material difference" is a perfectly good answer
if that is what the numbers say.

## 2. Task 1: expected-return uncertainty (opt-in)
- Add an optional field to `ESGParams`, e.g. `eq_mu_cov: np.ndarray | None = None`: the (K, K) annual
  covariance of the error in each asset's median return. When set, draw one error vector per scenario
  (held fixed for the whole path) and add it to that scenario's drift. Antithetic pairs must get
  mirrored draws, like the shocks. `None` must reproduce today's numbers exactly.
- Nested simulations (`engine.conditional_2031`) re-simulate 2031-2033 from one scenario. Decide
  whether the inner run should keep that scenario's drawn drift or redraw; state your reasoning in the
  findings doc (keeping it is the Bayesian-consistent choice unless you show otherwise). Make it work
  either way without breaking the existing call signature.
- Calibrate a default covariance from the cross-firm dispersion in `config/cma.yaml` (us, intl_dev,
  em columns), mapped to the K assets by region. Find how the code maps assets to regions
  (`src/lgm/growth/universe.py`); do not hard-code a second mapping. Put the calibration in a function
  in `src/lgm/calibrate.py` so it can be reused.
- Tests in `tests/test_esg_v2.py`: `None` reproduces the old scenarios exactly; with a covariance the
  cross-scenario spread of per-scenario mean log returns matches the covariance within sampling error;
  antithetic mirroring holds.
- Commit.

## 3. Task 2: volatility clustering (opt-in)
- Add an optional volatility process to the equity shocks. Your choice of a GARCH(1,1)-type variance
  on a common factor or a two-state Markov regime-switching volatility; state why. Keep it simple and
  keep the Student-t mixing. Requirements:
  - the unconditional annual volatility of each asset stays within 0.2 points of today's;
  - each asset's median 74-month return stays within 0.1%/yr of today's;
  - default off reproduces today's numbers exactly;
  - it starts from a stated initial state (say which: unconditional, or today's estimated state).
- Calibrate it on the monthly equity history already cached (VTI from `data/raw/yahoo`, 2001-2026).
  Report the fitted parameters, and the autocorrelation of squared monthly returns at lags 1-6 for
  history, today's model, and the new model.
- Tests in `tests/test_esg_v2.py`. Commit.

## 4. Task 3: does it matter? (new script `scripts/esg_variants.py`)
Build the headline parameters the way `scripts/report_numbers.py` does (IPS strategy, Black-Litterman
core, $25 WInS commissions, 20,000 scenarios, same seed for every variant). Four variants:
`baseline`, `drift_unc`, `vol_cluster`, `both`. Also run `drift_unc` at 0.5x and 2x the calibrated
covariance.
For each variant report, one row each (write `reports/esg_variants.csv`):
- funded share, p5, p10, median, p90, p95, cvar5 of the facility;
- 74-month cumulative return percentiles (5/50/95) of the 60/30/10 sleeve;
- the 2031 conditional range at the median 2031 scenario (p10/p90 and p20/p80);
- **history calibration**: repeat policy_study's section 3 (quote the range from each of the 184
  historical paths' own Jan 2031 position, check where Jan 2033 landed) using the variant's generator
  for the inner simulation. Report coverage of the 10-90 and 20-80 bands, and the share below each
  band, as-happened and re-centred. Copy what you need from `scripts/policy_study.py` into your script
  rather than editing that file.
Compute is small (seconds per variant), except the history calibration (184 inner simulations per
variant); measure one before running all, and keep the total under 20 minutes.
Commit the script and the report.

## 5. Findings doc `docs/loop/r1_esg_findings.md`
Per-variant table (from the script), fitted parameters, the autocorrelation table, and a plain
recommendation: should either feature be switched on for the headline numbers, and why. Mark it as
your recommendation; the decision is not yours (below).

## Verify
- `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the last line verbatim).
- `PYTHONPATH=$WT/src PY scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical.

## Acceptance criteria
- [ ] `eq_mu_cov` (or equivalent) implemented, opt-in, calibrated from `config/cma.yaml`, tested
- [ ] volatility clustering implemented, opt-in, calibrated, tested, with the squared-return autocorrelation table
- [ ] `scripts/esg_variants.py` and `reports/esg_variants.csv` with one row per variant, including history coverage
- [ ] `docs/loop/r1_esg_findings.md` with per-variant numbers and a recommendation
- [ ] tests pass; pre-existing reports byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/esg.py`, `src/lgm/calibrate.py` (additive), `scripts/esg_variants.py`, `tests/test_esg_v2.py`,
`reports/esg_variants.csv` (and any other new `reports/esg_*` file), `docs/loop/r1_esg_findings.md`.
Another worker is editing `src/lgm/engine.py` and `src/lgm/strategies.py` in parallel: if you must
touch `engine.py` (for the nested-simulation drift), keep it to a minimal, additive change and list it.

## Not yours to decide
Whether either feature becomes the default, the magnitude used for headline numbers, and any change
to `t_dof` or other existing calibration. Recommend; report `question` if you think a default must change.

## Budget
About 2 hours of work and 20 minutes of compute in total. Stop and report at the budget.

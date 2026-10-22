# Agent brief r2-esg: does volatility clustering help when it knows the current volatility?

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), your round-1 findings
`docs/loop/r1_esg_findings.md`, `scripts/esg_variants.py`, `src/lgm/calibrate.py`
(`calibrate_equity_garch`), `src/lgm/esg.py` (the `eq_garch` and `start["garch_h"]` code),
`src/lgm/backtest.py`.
**Your worktree:** branch `r2-esg`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed last round (verified by the planner)
Your r1-esg branch is merged. The planner reproduced `reports/esg_variants.csv`. Settled:
expected-return uncertainty calibrated from forecaster dispersion changes nothing material (it
stays opt-in, off). GARCH as tested **lowered** the 20-80 band's historical coverage from 81% to 72%
(re-centred) and from 75.5% to 66% (as happened).

## 1. Why that test was not fair to GARCH, and the question
In the history check, every one of the 184 inner simulations started GARCH at the unconditional
state (`h0 = 1`). The only reason to model volatility clustering for the 2031 co-sponsor quote is
that in January 2031 you KNOW whether markets have been calm or turbulent, and the quote should
widen or narrow accordingly. A fixed `h0` throws that information away, and with fat tails at a
fixed variance the central band gets narrower, which is exactly the coverage drop you measured.
Question: when each historical path's inner simulation starts from the GARCH variance **filtered
through that path's own returns up to its January 2031 month**, does the 20-80 band's coverage
come back to about 80%, and does it beat the baseline on calibration *conditional on the regime*?
Breaking GARCH for good is a perfectly good outcome.

## 2. Task 1: a variance filter
Add a function in `src/lgm/calibrate.py` that runs the fitted GARCH recursion over a return series
and returns the variance state at every month (same normalisation as `esg.simulate` uses for `h`).
Test that filtering the generator's own simulated returns recovers its simulated `garch_h` path.
Use it to report today's state (Sep 2026) and say whether it matches the 0.70 you reported.
Commit.

## 3. Task 2: the fair test (extend `scripts/esg_variants.py` or add `scripts/esg_garch_conditional.py`)
For the 184 historical paths (as-happened and re-centred), run the 2031-2033 inner simulation with:
(a) baseline (no GARCH), (b) GARCH from `h0 = 1`, (c) GARCH from the filtered state for that path.
Report coverage of the 10-90 and 20-80 bands and the share below each, for each variant. Then the
part that matters: split the 184 paths into terciles by the filtered 2031 variance (calm, normal,
turbulent) and report coverage and band width **per tercile per variant**, not a range across them.
Also report the headline (today's) IPS numbers with GARCH started from today's filtered state.
Overlapping paths mean about four independent six-year windows: say how much that limits the
conclusion. Write `reports/esg_garch_conditional.csv`. Commit.

## 4. Findings `docs/loop/r2_esg_findings.md`
The per-variant, per-tercile table and a recommendation: should the 2031 quote use filtered GARCH?

## Verify / acceptance
- [ ] filter function in `calibrate.py`, tested against simulated paths
- [ ] fair history test, per-variant and per-tercile, in `reports/esg_garch_conditional.csv`
- [ ] headline numbers with GARCH from today's filtered state
- [ ] `docs/loop/r2_esg_findings.md` with a recommendation
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the summary line verbatim); `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/calibrate.py` (additive), `scripts/esg_variants.py`, `scripts/esg_garch_conditional.py`,
`tests/test_esg_garch_filter.py`, `reports/esg_*`, `docs/loop/r2_esg_findings.md`.
**Do not edit `src/lgm/esg.py`, `src/lgm/backtest.py` or `src/lgm/engine.py`**: two other workers own
them this round. If you need a change there, report `question` with the exact change.

## Not yours to decide
Whether GARCH becomes the default.

## Budget
About 2 hours and 20 minutes of compute. 184 paths x 3 variants x 2 histories of inner simulations:
measure one, multiply, and size `n_inner` so the total fits. Keep peak memory low (COMMON.md rule 11).

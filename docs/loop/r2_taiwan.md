# Agent brief r2-taiwan: put the real Taiwan cost data into the generator

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), your own round-1 findings
`docs/loop/r1_taiwan_findings.md`, `config/taiwan.yaml`, `src/lgm/esg.py`, `src/lgm/backtest.py`,
`src/lgm/growth/scoring.py` (`esg_params`), `src/lgm/engine.py` (`facility_real_tw2027`).
**Your worktree:** branch `r2-taiwan`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed last round (verified by the planner)
Your r1-taiwan branch is merged into `improve`. The planner re-downloaded `ccispl.ods` and
`cpispl.ods` from DGBAS and got your exact SHA-256s, re-ran your calibration and got your numbers.
Settled: the index is persistent (monthly AR(1) 0.60, 12-month-inflation AR(1) 0.97), and 72-month
historical growth spans -0.3% to +44.1% (p5-p95), against 19.1%-34.4% under today's assumption.

## 1. The problem your round-1 work did not address
Your proposed AR(1) process starts from the long-run mean. But persistence is the whole point: the
latest reading (Sep 2026) is **+7.29% year on year**, far above the 2.8% long-run mean. With a
12-month AR(1) of 0.97, a model that starts from today's state will forecast much higher 2027-2033
cost growth than one that starts from the mean. The starting state is likely to matter more than
the drift. Measure that, rather than assume it.

## 2. Task 1: opt-in persistent Taiwan cost process in `esg.py`
Add to `ESGParams` an optional persistent process for Taiwan building-cost inflation (default off, so
today's numbers reproduce exactly). Your choice of specification, e.g. AR(1) on monthly log changes,
or AR(1) on the 12-month inflation rate mapped to monthly changes; state why. Requirements:
- a starting state taken from the data (the latest observed inflation, and whatever lags the
  process needs), with nested simulations (`engine.conditional_2031`) starting from that scenario's
  own 2031 state (pass it through `start`, like `fx_log` and `tw_cost_log` are now);
- correlation with the other shocks only if it is material and you can estimate it: report the
  estimate either way;
- the `(N, M+1)` `tw_cost_log` output keeps its meaning (0 at the start).
Tests in `tests/test_taiwan_esg.py`: default reproduces old scenarios bit-for-bit; the simulated
process's unconditional mean, volatility and AR(1) match the calibration within sampling error; a
start far above the mean decays at the calibrated rate. Commit.

## 3. Task 2: real Taiwan cost paths in the historical replay
`backtest.history_paths` currently fills `tw_cost_log` with a straight 4% line. Make it use the
actual DGBAS index path for each historical window, opt-in via a keyword argument (default keeps
today's behaviour). Test it. Commit.

## 4. Task 3: what it changes (`scripts/taiwan_variants.py`)
Build the headline parameters exactly as `scripts/report_numbers.py` does (IPS, BL core, $25
commissions, 20,000 scenarios, one seed). Variants, one row each in `reports/taiwan_variants.csv`:
`current` (4%/1.5% iid), `iid_dropin` (from `config/taiwan.yaml`), `persistent_from_mean`,
`persistent_from_today`. For each: median and p5/p95 of `facility_real_tw2027`, the nominal median
(must be unchanged: say so if it is not), and the p5/p50/p95 of cumulative Taiwan cost growth
Jan 2027-Jan 2033. Also, on the 184 historical paths with real Taiwan cost paths: the
distribution of the real facility (as-happened), next to the same paths with the 4% line.
Commit the script and report.

## 5. Findings `docs/loop/r2_taiwan_findings.md`
Per-variant numbers, your specification and why, and a recommendation for the headline. Report
whether the starting state or the long-run drift moves the real median more.

## Verify / acceptance
- [ ] persistent process implemented, opt-in, data-calibrated start, nested sims start from their own 2031 state, tested
- [ ] historical replay can use real Taiwan cost paths (opt-in), tested
- [ ] `scripts/taiwan_variants.py` and `reports/taiwan_variants.csv`, one row per variant
- [ ] `docs/loop/r2_taiwan_findings.md` with a recommendation
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the summary line verbatim); `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/esg.py` (the Taiwan-cost part only: another worker may read, but not edit, it this round),
`src/lgm/backtest.py`, `scripts/taiwan_variants.py`, `tests/test_taiwan_esg.py`,
`reports/taiwan_variants.csv`, `docs/loop/r2_taiwan_findings.md`, and additions to `config/taiwan.yaml`.
Do not edit `engine.py` beyond passing the new start state in `conditional_2031` (one or two lines,
additive; list them). Another worker owns the rest of `engine.py` this round.

## Not yours to decide
Whether any of this becomes the default for headline numbers.

## Budget
About 2 hours and 20 minutes of compute. Keep peak memory low (COMMON.md rule 11).

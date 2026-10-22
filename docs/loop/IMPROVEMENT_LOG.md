# Improvement loop log

A planner (Claude) writes briefs in `docs/loop/`, a worker (Gemini via `agy`) implements each one on its
own branch and worktree, and the planner verifies the result before merging it into `improve`.
Nothing here is adopted into the headline numbers until the planner has checked it.

Baseline (branch `improve` at the start of round 1, = `origin/core-model` c76a18b):
- `python -m pytest`: 61 passed.
- `python scripts/run_all.py`: about 27 s; regenerates every file in `reports/` byte-identically.
- IPS median facility $197,910, 5th percentile $147,375 (`reports/report_numbers.json`, `plan`).

## Round 1 (dispatched 2026-10-21)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-esg | r1-esg | `docs/loop/r1_esg.md` | Does the scenario generator understate risk by treating expected returns as known and volatility as constant? |
| lgm-policy | r1-policy | `docs/loop/r1_policy.md` | Is the IPS policy (lock all, 60/40, 60% floor in 2031) close to the best in a wider family, including dynamic rules? |
| lgm-taiwan | r1-taiwan | `docs/loop/r1_taiwan.md` | Replace the assumed 4%/1.5% Taiwan building-cost inflation with data |

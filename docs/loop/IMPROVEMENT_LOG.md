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

### Round 1 results (verified by the planner, all three merged into `improve`)
After merging: 77 tests pass; `run_all.py` leaves every pre-existing report byte-identical. Nothing
was switched on by default.
- **r1-taiwan.** Official DGBAS construction cost index 1991-2026 and Taiwan CPI. Checked by
  re-downloading `ccispl.ods` and `cpispl.ods` from DGBAS: SHA-256 identical to the committed files.
  The index is persistent (monthly AR(1) 0.60), and 72-month growth spans -0.3% to +44.1% (p5-p95)
  against 19.1%-34.4% under the 4% assumption. Gap: the proposed AR(1) starts at the long-run mean,
  but the latest reading is +7.3% y/y. Round 2 measures the effect of the starting state.
- **r1-policy.** Opt-in glide path, floor timing and ratchet; 3,456 policies, all 100% funded. The
  IPS is within $2.2k of the best CE at gamma 4 and $2.4k at gamma 2; the median "winner" (+$12.7k)
  cuts p5 by $38.7k. Bug found by the planner: `conditional_2031` ranks scenarios on growth assets
  only, so for policies that floor before 2031 the "median 2031 scenario" is arbitrary (the reported
  $234k secured for P2485 is that artifact). Fixed in round 2.
- **r1-esg.** Opt-in expected-return uncertainty (calibrated from forecaster dispersion) changes the
  facility by under $0.5k at any percentile: off. Opt-in GARCH volatility clustering lowered the
  20-80 band's historical coverage from 81% to 72%, but every history path started at the
  unconditional variance, which removes GARCH's only advantage for the 2031 quote. Round 2 tests it
  with the filtered state.

## Bridge change (2026-10-21)
At the user's request the loop skill gained a permanent memory watchdog: at yellow or red system
memory pressure the daemon stops every worker and holds delivery; the planner fixes the cause and
releases at green. COMMON.md rule 11 asks workers to keep peak memory under about 2 GB.

## Round 2 (dispatched 2026-10-21)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-taiwan | r2-taiwan | `docs/loop/r2_taiwan.md` | Persistent Taiwan cost process from today's 7.3% state; real cost paths in the replay |
| lgm-esg | r2-esg | `docs/loop/r2_esg.md` | Does GARCH help the 2031 quote when it starts from the filtered variance? |
| lgm-policy | r2-policy | `docs/loop/r2_policy.md` | Fix the 2031 scenario ranking; re-rank with a value on the 2031 promise |

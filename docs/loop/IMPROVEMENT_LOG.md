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

### Round 2 results (verified by the planner)
- **r2-esg (merged).** The GARCH variance filter recovers simulated variance paths exactly; today's
  state is 0.70 of the long-run variance. Starting each historical path from its own filtered 2031
  variance does not rescue GARCH: the 20-80 band's coverage is 73% (re-centred) against 81% for the
  baseline, and it ties or loses in every regime tercile (calm 89% vs 97%, normal 57% vs 72%,
  turbulent 74% vs 74%). The reason is structural: monthly persistence of 0.87 has a 5-month
  half-life, so 96% of what is known in Jan 2031 has washed out by 2033. GARCH stays off.
  Side observation (thin evidence, about 4 independent windows): after turbulent 2031 starts,
  outcomes landed above the 80th percentile 25-38% of the time, which looks like post-crash rebounds.
- **r2-policy (merged).** The ranking fix removes the $234k artifact: P2485 now secures $195.7k,
  in line with its $193.0k median floor. The planner then simplified the fix so every policy ranks on
  total Jan 2031 wealth before that month's floor move (identical for 2031-floor policies, and
  correct for ratchets too); `policy_search_top.csv` was generated before this change.
  On the full grid the IPS is on the efficient frontier: only three ratchet variants beat it on
  median, p5, CVaR5 and the 2031 secured amount at once, each by under $100. The real choice it
  leaves is a preference: P2361 (40% equity, 100% floor in 2031) gives up $3.9k of median for
  +$8.6k at p5, +$9.9k CVaR5, the same CE at gamma 4, and $195k secured in 2031 instead of $118k.

## Round 3 (dispatched 2026-10-21, while r2-taiwan is still running)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-esg | r3-strips | `docs/loop/r3_strips.md` | Real-world reserve with no reinvestment assumption: STRIPS and December maturities |
| lgm-policy | r3-robust | `docs/loop/r3_robust.md` | Does the policy choice survive pessimistic returns, vol, tails and rate shocks? |
| lgm-taiwan | r3-taiwan | `docs/loop/r3_taiwan.md` | Refit the Taiwan cost process on monthly changes; validate unconditional and conditional |

### r2-taiwan (merged, specification not adopted)
Plumbing merged: opt-in persistent process, state pass-through to `conditional_2031`, real DGBAS
cost paths in the historical replay (real median $169.9k against $155.1k with the 4% line, on the
same 184 paths). The specification is wrong: `tw_cost_phi = 0.97` is the AR(1) of the overlapping
12-month rate, which i.i.d. monthly noise already pushes to 0.92 (planner's simulation, 0.916), and
it is then applied to the instantaneous rate, giving a 72-month p5-p95 of -15% to +66% against
history's -0.3% to +44%. Monthly changes have autocorrelation 0.60 / 0.30 / 0.03 at lags 1 / 2 / 12,
and the k-month dispersion is 1.7x the i.i.d. scaling at every horizon from 12 to 72 months:
persistence lasts months, not years. So "the starting state dominates" is unproven. Round 3 refits.

### r3-robust (merged)
Seven shortlisted policies x 11 assumption shifts, common random numbers. Maximum regret across shifts
(gap to the best shortlisted policy under each shift):

| Policy | median | p5 | CVaR5 | CE gamma 4 | CE gamma 8 | secured 2031 |
|---|---:|---:|---:|---:|---:|---:|
| IPS (60/40, 60% floor 2031) | 39.6k | 16.6k | 19.6k | 6.8k | 12.5k | 92.1k |
| P2305 (40/60, no floor) | 41.3k | 9.7k | 10.9k | 4.4k | 6.8k | 231.2k |
| P2333 (40/60, 60% floor 2030) | 49.0k | 2.7k | 2.9k | 9.5k | 1.8k | 93.3k |
| P2361 (40/60, 100% floor 2031) | 50.3k | 4.3k | 4.9k | 11.1k | 3.7k | 0.8k |
| P2485 (40 to 0, 100% floor 2030) | 55.4k | 2.2k | 1.5k | 14.9k | 5.7k | 4.8k |
| P1729 (70/30, no floor, 75% lock) | 23.5k | 34.7k | 39.6k | 17.2k | 31.2k | 231.2k |
| P0964 (all equity, 50% lock) | 10.4k | 64.5k | 73.3k | 49.0k | 117.3k | 231.2k |

No policy is robust on every objective; the IPS is in the middle on each. Under the lowest-forecast
equity returns (-2.8 points), every 40%-equity policy beats the IPS on median as well.
Found in review: under `t_dof = 3`, one scenario's 5-year rate falls about 4.5 points in the two
months before the 2027 lock and ends $450 short for every policy, so all CE values in the
`tails_tdof3` rows are that artifact (about $27). Cause: the common Student-t mixing variable gives
rate shocks fat tails that history does not have (5-year zero, monthly change: history excess
kurtosis 0.6, worst month -0.81 pp; model at t5 worst month -1.99 pp; Gaussian rates -1.22 pp).

## Round 4
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-rates | r4-rates | `docs/loop/r4_rates.md` | Give rate shocks their own (thinner) tails, keep crash correlations, measure the effect |

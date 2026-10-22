# Agent brief r3-robust: does the policy choice survive wrong assumptions?

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), your findings
`docs/loop/r1_policy_findings.md` and `docs/loop/r2_policy_findings.md`, `scripts/policy_search.py`,
`scripts/report_numbers.py` (how it builds parameters, and its rate stresses with `beta_shift`),
`config/cma.yaml`.
**Your worktree:** branch `r3-robust`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed (verified by the planner)
Your r2-policy branch is merged. The planner then simplified your ranking fix: `conditional_2031`
now always ranks on `assets_2031` (identical for policies with no floor before 2031, and correct for
ratchets too). Do not change that. `reports/policy_search_top.csv` predates the change; regenerate
it if you use it. The planner's own check of `reports/policy_search.csv`: the IPS is on the
efficient frontier (only three ratchet variants beat it on median, p5, CVaR5 and secured at once,
each by under $100), and the real alternative is P2361 (40% equity, 100% floor in 2031): -$3.9k
median, +$8.6k p5, the same CE at gamma 4, $195k secured in 2031 against $118k.

## 1. The question
Every ranking so far uses one set of assumptions. A choice is only good if it survives the plausible
ways those assumptions are wrong. For a shortlist of policies, under each of a set of assumption
shifts, which policy wins on each objective, and by how much does the IPS lose when it is not the
winner? A policy that is never far from the best across every shift is the robust choice.

## 2. The shortlist
IPS, P2361, P2485, P2305, P2333, P1729, P0964, and the best policy for lambda 0.05 and 0.1 from your
r2 table (de-duplicate). Take the parameters from `reports/policy_search.csv`.

## 3. The shifts (one at a time, against the base case)
1. Equity expected returns: the median of the 13 firms (base), the 25th percentile firm, the
   lowest firm, and the highest firm in `config/cma.yaml`. Shift every equity asset's `eq_geo` by the
   same amount (the firm's US-equity forecast minus the 13-firm median). Say exactly how you applied it.
2. Equity volatility x0.8, x1.2 (`eq_vol_scale`).
3. Fatter tails: `t_dof` 3 and Gaussian (`None`), against today's 5.
4. Rates at the January 2027 lock -0.75 and +0.75 points, applied the way `report_numbers.py` does.
5. Bond return drag: IBTM expense ratio doubled (the model's only bond-cost knob), as a minor check.
Common random numbers within each shift (one scenario set for all shortlisted policies). Measure
one run first and size the total to fit within 20 minutes of compute.

## 4. Output
`scripts/policy_robust.py` writing `reports/policy_robust.csv`: one row per shift x policy with
median, p5, cvar5, CE at gamma 2/4/8, secured 2031 median, and that policy's regret on each objective
(its gap to the best shortlisted policy under that shift). Then a regret summary: for each policy,
the maximum regret across shifts per objective. Commit.

## 5. Findings `docs/loop/r3_robust_findings.md`
Per-shift winners and the max-regret table, per policy, not ranges across policies. Say plainly
which conclusions are robust and which flip, and under which shift. Recommendation marked as yours.

## Verify / acceptance
- [ ] `scripts/policy_robust.py` and `reports/policy_robust.csv` covering every shift x policy
- [ ] max-regret table per policy per objective
- [ ] `docs/loop/r3_robust_findings.md`
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes; `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`scripts/policy_robust.py`, `tests/test_policy_robust.py` (if useful), `reports/policy_robust.csv`,
`docs/loop/r3_robust_findings.md`. Read-only for everything in `src/` this round (other workers own
`esg.py`, `backtest.py`, `ladder.py`, `instruments.py`). If you need a library change, report
`question` with the exact change.

## Not yours to decide
Which policy the IPS adopts.

## Budget
About 1.5 hours and 20 minutes of compute. Keep peak memory low (COMMON.md rule 11).

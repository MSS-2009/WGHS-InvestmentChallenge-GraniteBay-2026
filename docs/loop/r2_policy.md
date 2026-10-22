# Agent brief r2-policy: fix the 2031 quote for early-floor policies, then re-rank honestly

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full), your round-1 findings
`docs/loop/r1_policy_findings.md`, `src/lgm/engine.py` (`run`, `conditional_2031`),
`scripts/policy_search.py`.
**Your worktree:** branch `r2-policy`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed last round (verified by the planner)
Your r1-policy branch is merged. The planner confirmed that defaults reproduce every report
byte-for-byte and that the IPS is within about $2.2k of the best certainty equivalent at gamma 4.

## 1. A bug the planner found in your results
Section 5C of your findings says the p5 winner (`P2485`: 100% floor in **2030**) "secures $234,363"
in 2031 with a $0-wide range, yet its own median facility is $192,033 and section 4 gives its secured
amount as $193,041. Cause: `conditional_2031` picks "the median 2031 scenario" by ranking
`out["growth_2031"]`, which counts growth assets only. For any policy whose floor moved before 2031,
growth assets are near zero in every scenario, so the "median" is an arbitrary one. The same
ranking is used by `scripts/report_numbers.py` and `scripts/policy_study.py`, so the fix must keep
their results identical for policies that floor in 2031 or later.

## 2. Task 1: fix the ranking
Rank the 2031 scenarios on what the client actually has in January 2031 (growth assets plus the
value of the floor already bought, at that month's prices), at least whenever the floor moved before
2031. Keep the existing ranking exactly where it already gives the right answer, so that
`scripts/run_all.py` still leaves every pre-existing report byte-identical; if you conclude that
cannot be done without changing an existing number, report `question` instead of changing it.
Add a test with a 2030-floor policy where the old ranking picks the wrong scenario and the new one
picks the true median. Commit.

## 3. Task 2: re-run the robustness table
Regenerate `reports/policy_search_top.csv` (and any summary it feeds) with the fix. Update your
findings in a NEW doc `docs/loop/r2_policy_findings.md`: the corrected 2031 quotes for every top
policy, and whether any conclusion in round 1 changes. Commit.

## 4. Task 3: one honest objective for the 2031 promise
Your round-1 point stands: CRRA over the 2033 facility ignores the value of what can be promised to
co-sponsors in January 2031. Add, as an extra reported column (not a replacement), a simple
two-part score: the CE at gamma 4 of the 2033 facility, plus `lambda` times the amount secured in
2031 (its median). Report the best policy for lambda in {0, 0.05, 0.1, 0.2, 0.5} and the IPS's rank
and gap at each. This shows how much weight on the promise would justify each policy; the weight
itself is the client's choice. Commit.

## Verify / acceptance
- [ ] ranking fixed, existing reports byte-identical, regression test added
- [ ] `reports/policy_search_top.csv` regenerated; `docs/loop/r2_policy_findings.md` with corrected 2031 quotes
- [ ] lambda table: best policy, IPS rank and gap per lambda
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the summary line verbatim)
- [ ] one commit per task

## Files you own
`src/lgm/engine.py` (except one or two additive lines another worker may add to
`conditional_2031`'s `start` dict; leave those alone if they appear), `src/lgm/strategies.py`,
`scripts/policy_search.py`, `tests/test_policy_search.py`, `reports/policy_search*.csv`,
`docs/loop/r2_policy_findings.md`. Do not edit `esg.py`, `backtest.py` or `calibrate.py`.

## Not yours to decide
Which policy the IPS adopts, and the value of lambda.

## Budget
About 1.5 hours and 20 minutes of compute. Keep peak memory low (COMMON.md rule 11).

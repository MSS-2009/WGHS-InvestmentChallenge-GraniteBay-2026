# Agent brief r8-adopt — make the January 2033 ladder top-up the engine's default

**Read first:** `docs/loop/COMMON.md` (rules apply in full), then `docs/loop/r8_reinvest_findings.md`,
`docs/loop/r8_topup_findings.md` and the verifier's notes (`git show r8-verify-topup:docs/loop/r8-verify-topup_verify.md`), then
`scripts/reinvest_risk.py` and `scripts/topup_2033.py`, then `src/lgm/engine.py` in full.
**Your worktree:** branch `r8-adopt`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Never run a command in the main checkout (COMMON rule 12).

## 0. The decision (made by the client, not yours to revisit)
The IPS adopts this rule, and the engine makes it the **default**:
1. January 2027: lock the reserve as today (cost `PMT * df * (1 + kappa0)`, `kappa0` = 1.8%, the 3%
   ladder).
2. January 2027 to January 2033: the ladder's coupons, maturities and fund distributions accumulate as
   reserve cash earning the path's 1-month rate floored at 0 (rule (c) of `scripts/reinvest_risk.py`).
3. January 2033, before the contribution is paid: buy the cheapest extra instruments from
   `wins_reserve_universe()`, priced on the path's own January 2033 curve, so that all ten payments are
   funded at **0%** reinvestment given the instruments held and the reserve cash. The cost comes out of
   the facility. After this the payments are certain by construction.

`scripts/topup_2033.py` (verified) computes this outside the engine: IPS median $195,570.1, 5th
percentile $144,164.1, against $196,989.2 / $146,101.9 today. COMMON rule 2 is lifted for this one
default: it is meant to change the numbers.

## 1. The hard constraint: speed
Many scripts call `engine.run` in loops (`run_all.py` takes about 100 s today). One exact LP per path
costs about 2.5 ms, about 50 s per 20,000-path run: not acceptable. Budgets:
- one `engine.run` on 20,000 scenarios: at most 0.5 s more than today (measure today's first);
- `run_all.py`: at most 130 s in total;
- accuracy: the top-up must match the exact per-path LP (`scripts/topup_2033.py`'s solver) within $1 on
  **every** one of the 20,000 headline paths. Exact methods are preferred to approximations.

A hint, not an instruction: the held ladder's flows and the payments are the same on every path; only
the instrument prices (from the path's curve) and the reserve cash differ. So the LP's constraint matrix
is shared, and the optimal basis probably takes few distinct values across paths. Solving each distinct
basis once and evaluating all paths against all bases, vectorised, may be exact and fast. Measure
before you build: time it, and count the distinct optimal bases on the 20,000 headline paths.

## 2. Tasks (commit after each)
1. **Measure:** today's `engine.run` time (median of 5) on the headline scenarios; the exact LP's time
   per path; the number of distinct optimal bases. Write them in `docs/loop/r8_adopt_findings.md`.
2. **Engine:** add `EngineConfig.topup_2033: bool = True`. `topup_2033=False` must reproduce today's
   numbers to the dollar. The ladder's dated flows are those of the 3% ladder `ladder.premium` solves on
   the headline curve (as in `scripts/reinvest_risk.py`), scaled to the engine's payments (`PMT` and the
   payment count) so that a WInS-scale run stays consistent. Put the schedule and solver in a module
   under `src/lgm/` (for example `src/lgm/topup.py`), not in a script. `run()` returns per path
   `topup_2033` (dollars) and `reserve_cash_2033`. The facility is net of the top-up.
3. **Nested simulations:** `conditional_2031` and any other path that starts the engine after January
   2027 (`m0 > 0`) must carry the reserve cash forward. Find every such caller (`grep -rn "m0\|conditional_2031" src scripts`),
   add the reserve-cash state to whatever the nested run starts from, and test that a nested run from
   January 2031 gives the same top-up as the full run on the same path when no new shocks are drawn
   (or explain with numbers why it cannot).
4. **Tests** in `tests/test_topup.py`:
   - (a) `topup_2033=False` reproduces today's plan median and 5th percentile exactly.
   - (b) The default matches `scripts/topup_2033.py`'s per-path top-up within $1 on all 20,000 headline paths.
   - (c) A constructed all-zero-rates path tops up by $8,256.53 (the verified figure).
   - (d) A path whose rates stay at 3% or more needs a top-up of at most $2,984.86 (the verified flat-3% figure).
   - (e) The facility equals the old facility minus the top-up, path by path.
5. **Speed check:** the two budgets in section 1, measured, in the findings doc.
6. **Run the pipeline:** `PYTHONPATH=<wt>/src PY scripts/run_all.py`. Reports WILL change. Do NOT run
   `doc_numbers.py --fix` and do NOT edit `docs/MODEL.md`, `docs/VALIDATION.md` or `README.md`: a
   separate step does that. Instead list, in the findings doc:
   - every report file that changed (`git status --short reports/`);
   - the new headline (`reports/report_numbers.json` plan median, p5, CVaR5, real median) next to the old;
   - the `doc_numbers.py` output line (how many figures are now missing). Commit the changed reports.

## You own
`src/lgm/engine.py`, the new module under `src/lgm/`, the nested-simulation callers you must touch,
`tests/test_topup.py`, `reports/` (regenerated), `docs/loop/r8_adopt_findings.md`. List every other file
you touch in the report.

## Acceptance criteria
- [ ] The two speed budgets are met, measured.
- [ ] Tests (a) to (e) pass; final pytest line pasted verbatim.
- [ ] The new headline median and 5th percentile are within $5 of $195,570.1 and $144,164.1, or the
      difference is explained with numbers.
- [ ] The findings doc lists the changed reports and the doc_numbers line.

## Not yours to decide
The docs' wording, and any change to the WInS ladder or orders. If the speed budget cannot be met
exactly, stop and report `question` with the measurements: do not ship an approximation unasked.

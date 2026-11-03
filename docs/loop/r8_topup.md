# Agent brief r8-topup — make the ladder certain in January 2033 instead of pricing it in 2027

**Read first:** `docs/loop/COMMON.md` (rules apply in full), then `docs/loop/r8_reinvest_findings.md`
and `scripts/reinvest_risk.py` (on branch `r8-reinvest`; read them with
`git show r8-reinvest:<path>`), then `src/lgm/ladder.py` (`solve` with its `fixed` and `minimum`
arguments, `wins_reserve_universe`, `payment_schedule`) and the January 2033 step of
`src/lgm/engine.py` (where the facility is what is left after buying any unlocked reserve).
**Your worktree:** branch `r8-topup`, based on `r8-reinvest`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Never run a command in the main checkout (COMMON rule 12).

## 0. What is settled, and the question
r8-reinvest (verified) holds the ladder bought in January 2027 for 3% reinvestment to 2042 with idle
cash earning each path's simulated 1-month rate floored at 0. On 20.4% of paths it misses a payment.
Making 99% of paths whole by buying more at the lock costs $3.8k (IPS median -$5.3k); full certainty at
0% from the start costs -$7.8k of median. **Question:** what does it cost to make the remaining payments
certain at 0% in **January 2033** instead, paying from the facility on that date, when the path's own
curve is known and part of the reinvestment period has already happened?

The policy, per path:
1. January 2027: buy the 3% ladder exactly as r8-reinvest does.
2. January 2027 to January 2033: hold it; idle cash earns the path's 1-month rate floored at 0 (rule (c)).
3. January 2033, before paying the contribution: given the instruments still held and the cash on hand,
   buy the cheapest extra instruments from `wins_reserve_universe()` (only those with cash flows after
   January 2033), priced on the path's own January 2033 curve (`Scenarios.curve(i, M_2033, date)`), so
   that all ten payments are funded at **0%** reinvestment. Use `ladder.solve` with the held amounts
   fixed (`fixed=`) and reinvest 0.0, or an equivalent LP; say which. The top-up cost comes out of the
   facility.
4. After January 2033 the ladder is certain at 0% by construction: no simulation needed after it.

## 1. Tasks (commit after each)
1. **Measure first:** time one LP solve on one path's 2033 curve. Multiply by the number of paths you
   intend to solve. If 20,000 takes more than about 30 minutes, use a stratified subset (for example
   every 10th path, 2,000 paths) and say so; state the standard error that implies for the mean cost.
2. **Script `scripts/topup_2033.py`**, writing `reports/topup_2033.csv`:
   - per path: cash on hand in January 2033, top-up cost, whether a top-up was needed;
   - summary rows: share of paths needing a top-up; mean, median, 95th and 99th percentile and maximum
     top-up cost; the IPS median and 5th percentile facility after the top-up (the engine's facility on
     the same scenarios and seed as `scripts/report_numbers.py`, minus each path's top-up; say how you
     matched paths between the engine run and the extended ESG run, and check it on one path).
   - Checks, printed: (i) on a path whose rates never fall below 3%, the top-up is zero or close to it;
     (ii) on a constructed path with all rates at 0 from 2027, the top-up equals what holding the 3%
     ladder at 0% falls short by, discounted at 0%, to the dollar, or explain the difference with numbers.
3. **Test `tests/test_topup_2033.py`:** a small toy case (two instruments, two payments) where the
   top-up can be computed by hand at 0%; the script's top-up function reproduces it to the cent.
4. **Findings `docs/loop/r8_topup_findings.md`:** the measurement, the checks, and one table comparing:

   | Policy | Certain? | IPS median | IPS 5th percentile |
   |---|---|---|---|
   | Ladder at 3% (today) | no: 20.4% of paths miss | | |
   | 99% priced at the lock (kappa0 3.11%) | no: 1% miss | | |
   | Certain at 0% priced at the lock | yes | | |
   | 3% ladder, topped up to 0% in January 2033 | yes | | |

   Fill every cell from scripts (the first three rows: `report_numbers.json` and an engine run with the
   kappa0 values in `docs/loop/r8_reinvest_findings.md`; print them). At most five sentences after it.
   Say plainly if the 2033 top-up is NOT cheaper than pricing 0% at the lock.

## You own
`scripts/topup_2033.py`, `reports/topup_2033.csv`, `tests/test_topup_2033.py`,
`docs/loop/r8_topup_findings.md`. Nothing else. Do not change the engine or its defaults.

## Acceptance criteria
- [ ] Task 1's timing is measured, and the path count used is stated with its standard error.
- [ ] Both checks in task 2 are printed and pass (or the difference is explained with numbers).
- [ ] Tests pass; final pytest line pasted verbatim.
- [ ] `run_all.py` leaves every pre-existing report byte-identical.
- [ ] Every cell of the comparison table is printed by a committed script.

## Not yours to decide
Which policy the plan adopts, and any change to MODEL.md, the engine or WInS. Report `blocked` with
partial results rather than guess.

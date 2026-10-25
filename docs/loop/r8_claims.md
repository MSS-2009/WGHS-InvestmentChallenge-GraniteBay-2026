# Agent brief r8-claims — read-only review: do the docs' sentences say what the numbers say?

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then
`scripts/doc_numbers.py`'s docstring.
**Your worktree:** branch `r8-claims`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Never run a command in the main checkout (COMMON rule 12).

## 0. Why
`scripts/doc_numbers.py` checks that 128 figures in `docs/MODEL.md` and `docs/VALIDATION.md` match the
reports that print them. Nothing checks the words around them: "because", "so", "the main driver",
"more cautious", "every", "only", "at most". On October 22 a draft said the worst historical path was
low because rates fell after the lock; the path's own numbers showed the lock was struck at low rates
(5-year zero rate 3.65% against 4.95% on the median path) with only 85% of the ladder locked. That kind
of error passes every figure check. Find the ones still in the docs.

## 1. Tasks
1. List every claim in `docs/MODEL.md`, `docs/VALIDATION.md` and `README.md` that asserts a cause, a
   direction, a ranking, a universal ("every", "never", "all", "none", "only") or a comparison ("more
   cautious", "dearer", "better", "at most"). One row each, with the file and line.
2. For each, find the evidence: the report file and field, or the script output, that supports or
   refutes it. Run the scripts when the report does not hold the number (they are all in `scripts/`;
   `run_all.py` takes about 100 s). Classify:
   - **contradicted**: a report or script output says otherwise;
   - **unsupported**: no report or script output in the repo shows it (it may still be true);
   - **supported**: name the field or output line;
   - **definitional**: true by construction (say what construction).
3. For every contradicted and unsupported row, write a reproducer: a command, or a short script in
   `docs/loop/r8_claims_repro.py`, whose output shows the evidence. For a contradicted claim, propose
   a replacement sentence that the evidence supports, with the numbers it rests on.
4. Write `docs/loop/r8_claims_findings.md`:
   - the contradicted and unsupported rows in full (claim, file:line, evidence, reproducer, proposed
     wording);
   - the supported and definitional rows as a compact table;
   - the totals, counted with a command (COMMON rule 14).

   Commit after each task.

Report per claim; do not summarise a group of claims as "mostly fine" (COMMON rule 8). A short list of
real contradictions is a good result. So is "none found" after a complete pass: say how many claims you
checked.

## You own
`docs/loop/r8_claims_findings.md`, `docs/loop/r8_claims_repro.py`. This is a read-only review: do not
edit `docs/`, `src/`, `scripts/`, `tests/` or `reports/` (if a script run changes a report, put it back
with `git restore reports/`).

## Acceptance criteria
- [ ] Every claim of the five kinds in the three files has a row (the count is in the findings doc).
- [ ] Every contradicted or unsupported row has a reproducer whose output is pasted next to it.
- [ ] `git diff improve --stat` touches only the two files you own.

## Not yours to decide
Which wording changes go into the docs: the planner decides and an integrator applies them.

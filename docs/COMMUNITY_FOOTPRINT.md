# Community Footprint Model

Added as a prospective extension to the qualitative model, November 21, 2026.

## Why it fits Laura

Laura Gao described organizing the Amazon HQ2 to Philadelphia student competition in 30 days, working with Wharton and the Philadelphia Department of Commerce. Her reflection emphasizes students contributing to their local community. Source: [Wharton Alumni, January 9, 2018](https://alumni.wharton.upenn.edu/story/not-plan-case-competition-30-days/).

The team interprets that involvement as a reason to consider companies' contributions to existing local residents. This is the team's proposed investment criterion, not a claim that Laura explicitly requested this screen. Do not describe it as having guided earlier competition trades.

**Question:** When a company puts down roots in a city, how does it make life better for people who already live there?

## Metric and scoring anchors

Community Footprint measures the strength of documented evidence about reviewed initiatives. It does not estimate causal impact, financial alpha, or the company's overall net social contribution.

Each initiative receives 0, 1, or 2 on four dimensions. The score is `50 × (0.25 Local + 0.35 Outcomes + 0.25 Corroboration + 0.15 Continuity)`.

| Dimension | Weight | 0 | 1 | 2 |
|---|---:|---|---|---|
| Benefit to existing local residents | 25% | Local beneficiaries not established | Named locality and residents served | Evidence identifies existing or underserved residents and how the initiative addresses their needs |
| Delivered outcomes | 35% | Announcement, pledge, event count or donation amount only | Delivered services or outputs, such as completed training | Numeric resident outcome, such as job placements or sustained employment, corroborated outside the company; measure, period and limitations recorded |
| External corroboration | 25% | Company account alone | Nonprofit, school or city partner confirms delivery/results; funding relationship disclosed | External evaluation or agency record verifies the specific outcome and describes a method beyond repeating the announcement |
| Continuity | 15% | One-off or only future support promised | Delivered support in at least two distinct years | Delivered support and tracked outcomes across at least three distinct years |

Weights and cutoffs are transparent analyst choices, not statistically estimated optimal parameters. No points arise merely from larger donations, more press releases, headquarters size, or more charity events. A completed review finding no qualifying evidence may yield 0; an unresearched company remains **not reviewed**, not 0.

## Evidence workflow

1. Scan company disclosures for candidate projects, grants, donations, charitable events, local training and school partnerships. `discover_candidates` is a paragraph keyword filter for downloaded text, not an autonomous verifier.
2. Record the company, initiative, locality, source URL, publication date and evidence passages. Merge multiple announcements about the same project into one initiative ID.
3. Read the implementing nonprofit's, school's or city's report. Confirm that it concerns the same project, locality, cohort and period. A recipient may depend on the donor's funding: record that relationship, and do not label the recipient wholly independent.
4. Separate **inputs** (money), **outputs** (people trained) and **outcomes** (jobs obtained or retained). Record units, time period, and a denominator where a rate is reported. Do not attribute all programme results to a donor when multiple funders or other causes contributed.
5. Check sustained support and adverse local effects. Unresolved or confirmed adverse impacts require a separate qualitative risk review; charity does not cancel displacement, labor harms, or environmental harms.
6. A reviewer assigns anchored levels with evidence notes and dates. Sources or reviews later than the requested research cutoff are excluded. The software validates the record, but a URL alone does not prove the claim.
7. Average the reviewed initiative scores equally, report identified/reviewed counts, and retain missing evidence. An incomplete review or adverse-impact flag prevents a positive tie-break. The average describes the reviewed projects only; use a consistent search protocol and disclose coverage to limit selective reporting.

## Comparing companies and using the score

Compare firms in similar industries with comparable business footprints and initiative types. For numeric outcomes, compare like units, populations and periods (for example, placements divided by completed trainees with the same follow-up interval). Never compare raw job counts against scholarships or meals. The score captures evidence quality; it does not substitute for these comparisons or establish a causal effect.

The community dimension is attached to the existing qualitative output without changing its financial score, suitability gates or Black–Litterman expected returns. An analyst must explicitly identify financially equivalent candidates based on Laura's goals, risk, diversification, liquidity and net costs. `qualitative.select(..., financial_equivalence_groups=...)` then prefers stronger community evidence within the same sector and declared community peer group, retaining sector caps. If either firm's research is incomplete, preserve the original order. Near-equal financial scores alone do not prove equivalence.

This is initially a company-level measure. Do not assign an ETF the sponsor's charitable score. A future ETF measure would require holdings-weighted issuer scores and disclosure of the share of fund assets covered by research.

## Files and reproduction

- `config/community_evidence.csv`: blank, source-backed review ledger; no real-company scores have been invented.
- `src/lgm/growth/community.py`: discovery, validation, scoring, evidence coverage and tie-breaking.
- `scripts/community_footprint.py`: produces initiative/company tables and a qualitative table with the added dimension.
- `tests/test_community.py`: synthetic examples only, covering missing research, future evidence, duplicate initiatives, gates and selection.

Run `PYTHONPATH=src .venv/bin/python scripts/community_footprint.py --as-of 2026-11-21`.

The model is implemented; company research and real scores remain to be populated. Keep future report language accurate: **we added a framework** is supported; **we verified community impact across our universe** is not yet supported.

## Report-ready explanation

Inspired by Laura's work bringing Penn students and Philadelphia together, we added Community Footprint to our qualitative framework. It evaluates evidence that company initiatives benefit existing local residents, produce measurable outcomes, receive external corroboration, and continue over time. Company announcements begin the research; nonprofit, school and city reports help establish what occurred. Among investments that meet Laura's financial goals equally well, we would favor stronger documented community contributions. Missing evidence remains unscored, and donations alone do not establish impact.

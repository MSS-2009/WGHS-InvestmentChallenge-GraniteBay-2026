"""Community Footprint: evidence of local benefits, used only as an approved tie-breaker.

This measures evidence strength, not causal impact or expected investment return.
Missing research is not a zero. Company donations alone cannot earn outcome credit.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlparse
import math
import re
import pandas as pd

# Analyst choices, not fitted or empirically validated weights.
WEIGHTS = {'local_benefit': .25, 'outcomes': .35, 'corroboration': .25, 'continuity': .15}
FIELDS = ['ticker', 'initiative_id', 'initiative', 'locality', 'peer_group', 'review_status',
          'reviewer', 'reviewed_at', 'company_url', 'company_published_at',
          'external_url', 'external_published_at', 'external_type', 'funding_relationship',
          'local_benefit', 'outcomes', 'corroboration', 'continuity',
          'local_evidence', 'outcome_evidence', 'corroboration_evidence', 'continuity_evidence',
          'outcome_measure', 'outcome_value', 'outcome_unit', 'outcome_period',
          'attribution_limits', 'adverse_impact_flag']
EVIDENCE = {'local_benefit':'local_evidence', 'outcomes':'outcome_evidence',
            'corroboration':'corroboration_evidence', 'continuity':'continuity_evidence'}
EXTERNAL_TYPES = {'nonprofit', 'school', 'city_agency', 'independent_evaluator'}


def _text(value):
    return '' if pd.isna(value) else str(value).strip()


def _url(value):
    p=urlparse(_text(value))
    return p.scheme in {'https','http'} and bool(p.netloc)


def score_initiatives(records: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Validate reviewed evidence, exclude future sources, calculate a 0–100 score.

    Each of four dimensions has anchored levels 0, 1, 2 (see docs/COMMUNITY_FOOTPRINT.md).
    Positive scores require recorded evidence. Level 2 outcomes require a numeric result
    and an external report; source presence never substitutes for a reviewer reading it.
    """
    cutoff=date.fromisoformat(as_of)
    missing=set(FIELDS)-set(records.columns)
    if missing: raise ValueError(f'Missing community evidence fields: {sorted(missing)}')
    out=records.copy()
    if out[['ticker','initiative_id']].duplicated().any():
        raise ValueError('Duplicate initiative for a company: consolidate sources in one record')
    scores=[]; statuses=[]
    for _,r in out.iterrows():
        if _text(r.review_status) != 'reviewed':
            scores.append(float('nan')); statuses.append('not_reviewed'); continue
        if not all(_text(r[k]) for k in ['ticker','initiative_id','initiative','peer_group','reviewer','attribution_limits']):
            raise ValueError('Reviewed initiatives require identity, peer group, reviewer and attribution limits')
        if not _url(r.company_url): raise ValueError('Reviewed initiative needs a company source URL')
        dates=[date.fromisoformat(_text(r[k])) for k in ['reviewed_at','company_published_at']]
        external=_url(r.external_url)
        if _text(r.external_url) and not external: raise ValueError('Invalid external source URL')
        if external:
            dates.append(date.fromisoformat(_text(r.external_published_at)))
            if _text(r.external_type) not in EXTERNAL_TYPES or not _text(r.funding_relationship):
                raise ValueError('External sources require type and funding relationship disclosure')
        levels={}
        for k in WEIGHTS:
            v=float(r[k])
            if not math.isfinite(v) or v not in (0,1,2): raise ValueError(f'{k} must be 0, 1 or 2')
            if v>0 and not _text(r[EVIDENCE[k]]): raise ValueError(f'{k} requires evidence notes')
            levels[k]=v
        if levels['local_benefit']>0 and not _text(r.locality):
            raise ValueError('Local benefit needs an identified locality')
        if levels['corroboration']>0 and not external:
            raise ValueError('Corroboration needs an external source')
        if levels['outcomes']==2:
            if not external or levels['corroboration']<1:
                raise ValueError('Measured outcomes need external corroboration')
            if not all(_text(r[k]) for k in ['outcome_measure','outcome_unit','outcome_period']):
                raise ValueError('Measured outcomes need measure, unit and period')
            if not math.isfinite(float(r.outcome_value)) or float(r.outcome_value)<0:
                raise ValueError('Outcome value must be a finite nonnegative number')
        flag=_text(r.adverse_impact_flag).lower()
        if flag not in {'none_identified','unresolved','confirmed'}:
            raise ValueError('Explicit adverse-impact review status required')
        if max(dates)>cutoff:
            scores.append(float('nan')); statuses.append('after_cutoff'); continue
        scores.append(50*sum(WEIGHTS[k]*levels[k] for k in WEIGHTS))
        statuses.append('risk_review_required' if flag!='none_identified' else 'reviewed')
    out['community_score']=scores; out['community_status']=statuses
    return out


def company_scores(initiatives: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight reviewed initiatives; report coverage, never silently score missing firms.

    Score describes reviewed projects only. It is not a company-wide impact estimate.
    An unresolved adverse flag prevents use as a positive tie-breaker.
    """
    rows=[]
    for ticker,g in initiatives.groupby('ticker',sort=True):
        peers=g.peer_group.dropna().unique()
        if len(peers)!=1: raise ValueError(f'{ticker}: use a single comparison peer group')
        valid=g.community_score.notna(); complete=bool(valid.all())
        risk=bool(g.community_status.eq('risk_review_required').any())
        rows.append({'ticker':ticker,'community_score':g.loc[valid,'community_score'].mean(),
                     'community_peer_group':peers[0], 'community_initiatives_identified':len(g),
                     'community_initiatives_reviewed':int(valid.sum()),
                     'community_status':'risk_review_required' if risk else ('reviewed' if complete else 'incomplete'),
                     'community_tiebreak_eligible':complete and not risk,
                     'community_scope':'reviewed initiatives only; not company-wide impact'})
    cols=['ticker','community_score','community_peer_group','community_initiatives_identified',
          'community_initiatives_reviewed','community_status','community_tiebreak_eligible','community_scope']
    return pd.DataFrame(rows,columns=cols).set_index('ticker')


def attach(scores: pd.DataFrame, community: pd.DataFrame) -> pd.DataFrame:
    """Add the dimension without changing financial scores, gates, or BL expected returns."""
    if not community.index.is_unique: raise ValueError('Duplicate community company scores')
    out=scores.join(community,how='left')
    out['community_status']=out.community_status.fillna('not_reviewed')
    out['community_tiebreak_eligible']=out.community_tiebreak_eligible.eq(True)
    return out


def order_ties(ranked: pd.DataFrame, equivalence_groups: dict[str,str] | None = None) -> pd.DataFrame:
    """Reorder only explicitly approved financial-equivalence groups within the same sector.

    Caller establishes equivalence on goals, risk, liquidity and net costs; no arbitrary
    numeric tolerance substitutes for that judgment. Missing evidence leaves order unchanged.
    Positions of all non-peer candidates are preserved, keeping existing sector caps effective.
    """
    if not equivalence_groups or 'community_score' not in ranked: return ranked
    order=list(ranked.index); buckets={}
    for pos,t in enumerate(order):
        if t not in equivalence_groups: continue
        r=ranked.loc[t]
        key=(equivalence_groups[t],r['sector'],r['community_peer_group'])
        buckets.setdefault(key,[]).append(pos)
    for positions in buckets.values():
        names=[order[p] for p in positions]; g=ranked.loc[names]
        if len(names)<2 or not g.community_tiebreak_eligible.all() or g.community_score.isna().any(): continue
        preferred=g.sort_values('community_score',ascending=False,kind='stable').index
        for pos,t in zip(positions,preferred): order[pos]=t
    return ranked.loc[order]


def discover_candidates(text: str) -> list[str]:
    """Extract paragraphs from downloaded disclosures for human review; never award points.

    This is a keyword discovery aid, not proof of a local outcome. Preserve the document
    URL, publication date and page/section when transferring a candidate to the ledger.
    """
    activity=re.compile(r'\b(donat\w*|charit\w*|volunteer\w*|grant\w*|job.train\w*|scholarship\w*|community project\w*)\b',re.I)
    local=re.compile(r'\b(local|resident\w*|neighbou?rhood\w*|communit\w*|school\w*|city|cities)\b',re.I)
    return [p.strip() for p in re.split(r'\n\s*\n',text) if activity.search(p) and local.search(p)]

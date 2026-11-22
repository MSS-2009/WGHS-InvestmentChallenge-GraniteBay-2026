import numpy as np
import pandas as pd
import pytest
from lgm.growth import community, qualitative


def record(**changes):
    r={key:'' for key in community.FIELDS}
    r.update(ticker='EXAMPLE',initiative_id='training-1',initiative='Synthetic training example',
        locality='Example city',peer_group='industrial_training',review_status='reviewed',
        reviewer='Test reviewer',reviewed_at='2026-11-21',company_url='https://example.com/disclosure',
        company_published_at='2025-01-01',external_url='https://example.org/outcomes',
        external_published_at='2026-10-01',external_type='nonprofit',funding_relationship='Recipient funded by donor',
        local_benefit=2,outcomes=2,corroboration=1,continuity=1,
        local_evidence='Residents in the local district',outcome_evidence='20 trainees placed',
        corroboration_evidence='Recipient reports placements',continuity_evidence='Delivery in 2024 and 2025',
        outcome_measure='job placements',outcome_value=20,outcome_unit='people',outcome_period='2025 cohort',
        attribution_limits='Multiple funders; no causal attribution to this donor',adverse_impact_flag='none_identified')
    return r|changes


def test_scoring_arithmetic_and_missing_research():
    rows=pd.DataFrame([record(),record(ticker='UNREVIEWED',review_status='not_reviewed')])
    scored=community.score_initiatives(rows,'2026-11-21')
    assert scored.iloc[0].community_score==pytest.approx(80)
    assert np.isnan(scored.iloc[1].community_score)
    companies=community.company_scores(scored)
    assert companies.loc['EXAMPLE','community_tiebreak_eligible']
    assert not companies.loc['UNREVIEWED','community_tiebreak_eligible']


def test_announcements_cannot_claim_verified_outcomes():
    with pytest.raises(ValueError,match='external'):
        community.score_initiatives(pd.DataFrame([record(external_url='')]),'2026-11-21')


def test_future_source_excluded_and_duplicates_rejected():
    r=record(external_published_at='2027-01-01')
    out=community.score_initiatives(pd.DataFrame([r]),'2026-11-21')
    assert out.iloc[0].community_status=='after_cutoff'
    assert np.isnan(out.iloc[0].community_score)
    with pytest.raises(ValueError,match='Duplicate'):
        community.score_initiatives(pd.DataFrame([record(),record()]),'2026-11-21')


def test_adverse_impacts_block_positive_preference():
    scored=community.score_initiatives(pd.DataFrame([record(adverse_impact_flag='unresolved')]),'2026-11-21')
    assert not community.company_scores(scored).iloc[0].community_tiebreak_eligible


def test_tie_break_requires_financial_equivalence_and_preserves_gates():
    d=pd.DataFrame({'combined':[3.,2.,1.,0.], 'accepted':[True,False,True,True],
        'sector':['Industrials']*4,'community_score':[20.,100.,80.,90.],
        'community_peer_group':['industrial_training']*4,'community_tiebreak_eligible':[True]*4},index=['A','REJECTED','B','C'])
    assert qualitative.select(d,1,1).index.tolist()==['A']
    groups={'A':'approved_pair','B':'approved_pair','REJECTED':'approved_pair'}
    assert qualitative.select(d,1,1,groups).index.tolist()==['B']
    d.loc['A','community_tiebreak_eligible']=False
    assert qualitative.select(d,1,1,groups).index.tolist()==['A']


def test_different_sectors_or_peer_groups_cannot_override():
    d=pd.DataFrame({'combined':[2.,1.],'sector':['A','B'],'community_score':[10.,90.],
        'community_peer_group':['p','p'],'community_tiebreak_eligible':[True,True]},index=['X','Y'])
    assert community.order_ties(d,{'X':'g','Y':'g'}).index.tolist()==['X','Y']
    d['sector']='A';d.loc['Y','community_peer_group']='different'
    assert community.order_ties(d,{'X':'g','Y':'g'}).index.tolist()==['X','Y']


def test_empty_evidence_produces_no_scores_and_no_candidate_invention():
    initiatives=community.score_initiatives(pd.DataFrame(columns=community.FIELDS),'2026-11-21')
    companies=community.company_scores(initiatives)
    out=community.attach(pd.DataFrame({'combined':[2.]},index=['A']),companies)
    assert np.isnan(out.loc['A','community_score'])
    assert out.loc['A','community_status']=='not_reviewed'
    assert community.discover_candidates('A donation helped local schools.\n\nQuarterly earnings rose.')==['A donation helped local schools.']

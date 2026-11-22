"""Build prospective community evidence reports or discover candidate disclosure paragraphs.

PYTHONPATH=src python scripts/community_footprint.py --as-of 2026-11-21
PYTHONPATH=src python scripts/community_footprint.py --scan disclosure.txt --as-of 2026-11-21
No trades, data downloads, or invented company scores.
"""
import argparse
from pathlib import Path
import pandas as pd
from lgm.growth.community import FIELDS, score_initiatives, company_scores, attach, discover_candidates
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--as-of',required=True,help='Research cutoff; later sources and reviews are excluded')
    ap.add_argument('--evidence',type=Path,default=ROOT/'config/community_evidence.csv')
    ap.add_argument('--scan',type=Path,help='Extract candidate paragraphs from a local text disclosure for review')
    ap.add_argument('--output',type=Path,default=ROOT/'reports/community')
    args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    if args.scan:
        candidates=discover_candidates(args.scan.read_text())
        pd.DataFrame([{'file':str(args.scan),'candidate':p,'review_status':'not_reviewed'} for p in candidates],
                     columns=['file','candidate','review_status']).to_csv(args.output/'discovery_candidates.csv',index=False)
        print(f'{len(candidates)} candidate paragraphs; no scores assigned.');return
    evidence=pd.read_csv(args.evidence,dtype=str).fillna('')
    initiatives=score_initiatives(evidence,args.as_of)
    companies=company_scores(initiatives)
    initiatives.to_csv(args.output/'initiative_scores.csv',index=False)
    companies.to_csv(args.output/'company_scores.csv')
    existing=ROOT/'reports/satellite_qualitative.csv'
    if existing.exists():
        base=pd.read_csv(existing,index_col=0)
        base=base.drop(columns=[c for c in base if c.startswith('community_')])
        attach(base,companies).to_csv(args.output/'qualitative_with_community.csv')
    print(f'{len(evidence)} initiatives; {len(companies)} companies researched. Missing evidence remains unscored.')

if __name__=='__main__':main()

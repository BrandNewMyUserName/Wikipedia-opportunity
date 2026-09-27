#!/usr/bin/env python3
"""Small-model map/spike acceptance check using a real, dated search evidence fixture."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from data import write_json
from spike_evidence import verify_spike

SOURCES = [
    {'url': 'https://science.nasa.gov/eclipses/future-eclipses/total-solar-eclipse-on-august-12-2026/',
     'publisher': 'NASA', 'event_date': '2026-08-12',
     'text': 'Total solar eclipse on August 12, 2026. A partial eclipse is visible over a broader area; NASA lists Kraków, Poland.'},
    {'url': 'https://polsa.gov.pl/wydarzenia/coz-to-bedzie-za-wieczor/',
     'publisher': 'Polish Space Agency', 'published': '2026-08-10', 'event_date': '2026-08-12',
     'text': 'Solar eclipse begins around 19:10 on August 12, with a deep partial eclipse visible from Poland.'},
    {'url': 'https://example.invalid/astronomy/meteor-shower', 'publisher': 'Distractor',
     'event_date': '2026-08-13', 'text': 'Perseid meteor shower peaks on August 13.'},
]


def ask(key, model, prompt):
    body = {'model': model, 'messages': [{'role':'user','content':prompt}],
            'temperature': 0, 'max_tokens': 1000,
            'response_format': {'type':'json_object'}}
    request = Request('https://openrouter.ai/api/v1/chat/completions',
                      data=json.dumps(body).encode(),
                      headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json',
                               'X-Title':'Wikipedia Topic Map Evaluation'})
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    return payload['choices'][0]['message']['content'], payload.get('usage', {})


def grade(answer, case):
    try:
        obj = json.loads(answer)
    except (ValueError, TypeError):
        return {'valid_json': False}, None
    if not isinstance(obj, dict):
        return {'valid_json': False}, None
    sources = obj.get('source_urls', [])
    if case == 'uncorroborated':
        checks = {'valid_json': True,
                  'rejects_wrong_date_sources': sources == [],
                  'does_not_invent_event': obj.get('event_name') in (None, '', 'unknown', 'unverified'),
                  'marks_cause_unverified': obj.get('causality') == 'unverified',
                  'does_not_infer_reader_country': obj.get('reader_country_known') is False}
        return checks, obj
    text = json.dumps(obj, ensure_ascii=False).lower()
    checks = {
        'valid_json': True,
        'correct_event_date': obj.get('event_date') == '2026-08-12',
        'correct_event': 'eclipse' in text or 'затемнен' in text or 'zaćmieni' in text,
        'two_relevant_sources': isinstance(sources, list) and SOURCES[0]['url'] in sources and SOURCES[1]['url'] in sources,
        'rejects_distractor': SOURCES[2]['url'] not in sources and 'perseid' not in str(obj.get('event_name','')).lower(),
        'does_not_infer_reader_country': obj.get('reader_country_known') is False,
        'states_pl_vs_uk_growth': obj.get('pl_growth_pct') == 27.0 and obj.get('uk_growth_pct') == -50.4,
        'recognizes_spike_sensitive_growth': obj.get('pl_peak_excluded_growth_pct') == -23.2
                                            and obj.get('pl_sustained_growth') is False,
        'marks_cause_inference': obj.get('causality') in ('plausible_not_proven', 'plausible, not proven'),
    }
    return checks, obj


def guarded_result(topic_map, case):
    language, day = ('pl','2026-08-12') if case == 'corroborated' else ('uk','2025-09-07')
    annotated = [{**source, 'matched_qids':['Q3887']} for source in SOURCES[:2]]
    gate = verify_spike(topic_map, language, day, annotated)
    rows = {row['language']:row for row in topic_map['languages']}
    supported = gate['status'] == 'plausible_not_proven'
    return {'event_name':'solar eclipse' if supported else None,
            'event_date':day if supported else None,
            'source_urls':[source['url'] for source in gate['accepted_sources']] if supported else [],
            'reader_country_known':False,
            'pl_growth_pct':round(rows['pl']['growth_pct'],1),
            'uk_growth_pct':round(rows['uk']['growth_pct'],1),
            'pl_peak_excluded_growth_pct':round(rows['pl']['peak_month_excluded_growth_pct'],1),
            'pl_sustained_growth':False,
            'causality':gate['status'],
            'conclusion':'Possible event match; traffic causation unproven.' if supported else 'Cause unverified.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', action='append', required=True)
    parser.add_argument('--map', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--case', choices=('corroborated','uncorroborated'))
    parser.add_argument('--variant', choices=('baseline','improved'))
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
    except ImportError:
        parser.error('Install python-dotenv for evaluation; the key must be loaded into OPEN_ROUTER_API_KEY')
    load_dotenv()
    key = os.environ.get('OPEN_ROUTER_API_KEY')
    if not key:
        parser.error('OPEN_ROUTER_API_KEY is not set; no model call made')
    full = json.loads(Path(args.map).read_text())
    brief = {'period':[full['start'],full['end']],
             'languages':[{k:v[k] for k in ('language','growth_pct','share_growth_pct',
                                           'peak_month_excluded_growth_pct','positive_yoy_months',
                                           'coverage','missing_qids')}
                          | {'concepts':[{k:c.get(k) for k in ('qid','label','latest_views','growth_pct','latest_basket_share_pct')}
                                          for c in v['concepts']],
                             'top_spike':v['spikes'][0] if v['spikes'] else None}
                          for v in full['languages']]}
    base = ('Summarize this Wikipedia topic map and explain the specified spike using only these search results. '
            'Return a JSON object with event_name, event_date, source_urls, reader_country_known, '
            'pl_growth_pct, uk_growth_pct, pl_peak_excluded_growth_pct, pl_sustained_growth, '
            'causality, conclusion.\nMAP '+json.dumps(brief,ensure_ascii=False)
            +'\nSPIKE_DATE 2026-08-12\nSEARCH_RESULTS '+json.dumps(SOURCES,ensure_ascii=False))
    improved = ('Follow this verification procedure: compare spike UTC date with event_date, check that the leading QID '
                'is the event topic, cite two independent relevant source URLs, reject date-only distractors, '
                'and call the event a plausible explanation rather than proven traffic cause. '
                'If no result matches both the event date and topic, set event_name to null, source_urls to [], '
                'and causality to unverified. Otherwise set causality to plausible_not_proven. '
                'Language edition does not reveal reader country. Round map growth to one decimal. '
                'If Polish raw growth is positive but peak-month-excluded growth is negative, set '
                'pl_sustained_growth to false and explain that growth is spike-sensitive. '
                'Set reader_country_known to false. '
                'Do not add unverified claims.\n') + base
    uncorroborated = base.replace('SPIKE_DATE 2026-08-12', 'SPIKE_DATE 2025-09-07').replace(
        'SEARCH_RESULTS '+json.dumps(SOURCES,ensure_ascii=False),
        'SEARCH_RESULTS '+json.dumps(SOURCES[:2],ensure_ascii=False))
    improved_uncorroborated = improved.replace('SPIKE_DATE 2026-08-12', 'SPIKE_DATE 2025-09-07').replace(
        'SEARCH_RESULTS '+json.dumps(SOURCES,ensure_ascii=False),
        'SEARCH_RESULTS '+json.dumps(SOURCES[:2],ensure_ascii=False))
    results = []
    for model in args.model:
        for case, variant, prompt in [('corroborated','baseline',base),
                                      ('corroborated','improved',improved),
                                      ('uncorroborated','baseline',uncorroborated),
                                      ('uncorroborated','improved',improved_uncorroborated)]:
            if args.case and case != args.case:
                continue
            if args.variant and variant != args.variant:
                continue
            print(f'Checking {model} {case} {variant}', flush=True)
            try:
                content, usage = ask(key, model, prompt)
            except Exception as exc:
                results.append({'model':model,'case':case,'variant':variant,
                                'error':type(exc).__name__})
                write_json(args.out, {'sources':SOURCES,'results':results})
                continue
            checks, obj = grade(content, case)
            guarded = guarded_result(full, case)
            guarded_checks, _ = grade(json.dumps(guarded), case)
            results.append({'model':model,'case':case,'variant':variant,'checks':checks,
                            'score':sum(checks.values()),'total':len(checks),
                            'guarded_checks':guarded_checks,'guarded_score':sum(guarded_checks.values()),
                            'usage':usage,'answer':obj if obj is not None else content})
            write_json(args.out, {'sources':SOURCES,'results':results})
    write_json(args.out, {'sources': SOURCES, 'results':results})
    print(json.dumps([{k:v for k,v in row.items() if k not in ('answer','usage')}
                      for row in results], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Agent-facing CLI. JSON stdout, concise errors on stderr, immutable run folders."""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from data import Client, DataError, default_window, write_json
from analysis import analyze, validate_config
from topic_map import collect_map, analyze_map

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(Path(path).read_text())

def prepare_output(path):
    out = Path(path)
    if out.exists() and any(out.iterdir()):
        raise DataError(f'Output must be empty: {out}; use a new run folder')
    out.mkdir(parents=True, exist_ok=True)
    return out

def plan(client, args):
    if not all(re.fullmatch(r'Q[1-9][0-9]*', q) for q in args.qids):
        raise DataError('Invalid QID')
    if len(set(args.qids)) != len(args.qids) or not 1 <= len(args.qids) <= 6:
        raise DataError('Use 1 to 6 unique QIDs')
    entities = client.entities(args.qids)
    series, missing = [], []
    for lang in args.languages:
        articles = []
        for qid in args.qids:
            entity = entities[qid]
            link = entity.get('sitelinks', {}).get(lang.replace('-', '_') + 'wiki')
            # Most codes match dbnames; uncommon exceptions require explicit verified titles.
            if not link:
                missing.append({'language': lang, 'qid': qid})
            else:
                articles.append({'qid': qid, 'title': link['title']})
        if len(articles) == len(args.qids):
            series.append({'id':lang, 'label':lang + ': ' + ', '.join(args.qids),
                           'language': lang, 'articles': articles})
    if missing:
        raise DataError('Missing sitelinks; do not treat as zero demand. Choose comparable proxies or explicitly narrow languages. ' + json.dumps(missing))
    start, end = default_window()
    config = {'schema_version':1, 'question':args.question, 'start':args.start or start,
              'end':args.end or end, 'series':series, 'criteria':{}}
    validate_config(config)
    path = Path(args.out)
    if path.exists():
        raise DataError('Plan already exists; choose a new filename')
    write_json(path, config)
    write_json(path.with_suffix('.mapping.json'), {'entities':entities, 'sources':list(client.sources.values())})
    return {'config':str(path), 'series':series, 'start':config['start'], 'end':config['end'],
            'next':'Review concept fit and titles, then run with --config. Mapping alone does not establish buying intent.'}

def collect(client, config):
    validate_config(config)
    data = []
    for series in config['series']:
        articles = []
        canonical = set()
        for article in series['articles']:
            a = client.validate_article(series['language'], article, config['start'])
            if a['pageid'] in canonical:
                raise DataError('Two input articles resolve to the same canonical page')
            canonical.add(a['pageid'])
            a['daily'] = client.series(series['language'], a['title'], config['start'], config['end'])
            articles.append(a)
        data.append({**series, 'articles':articles,
                     'project_totals':client.totals(series['language'], config['start'], config['end'])})
    retrieved = sorted(x['fetched_at'] for x in client.sources.values())
    return {'schema_version':1, 'created_at':datetime.now(timezone.utc).isoformat(),
            'source_retrieval_window':[retrieved[0],retrieved[-1]], 'config':config, 'series':data}

def execute(args):
    client = Client(args.cache, args.offline, args.refresh)
    if args.command == 'discover':
        return {'candidates':client.search(args.query,args.search_language),
                'next':'Choose the semantic match by label/description; use plan --qids. Do not assume the first result is correct.'}
    if args.command == 'plan':
        return plan(client, args)
    if args.command == 'map':
        qids = [args.root_qid, *args.qids]
        if len(set(qids)) != len(qids) or not 2 <= len(qids) <= 12 or not all(re.fullmatch(r'Q[1-9][0-9]*', q) for q in qids):
            raise DataError('Map needs 2 to 12 unique QIDs, including the root')
        if (len(set(args.languages)) != len(args.languages) or not 1 <= len(args.languages) <= 6
                or not all(re.fullmatch(r'[a-z][a-z0-9-]{0,19}', language) for language in args.languages)):
            raise DataError('Map needs 1 to 6 unique valid Wikipedia languages')
        start, end = default_window()
        start, end = args.start or start, args.end or end
        validate_config({'schema_version':1,'question':'Topic map','start':start,'end':end,
                         'series':[{'id':'validation','label':'validation','language':args.languages[0],
                                    'articles':[{'qid':args.root_qid,'title':'validation'}]}]})
        out = prepare_output(args.out)
        snapshot = collect_map(client, qids, args.languages, start, end)
        analysis = analyze_map(snapshot)
        write_json(out/'topic-map-snapshot.json', snapshot)
        write_json(out/'topic-map.json', analysis)
        write_json(out/'topic-map-provenance.json', {'schema_version':1,
                   'snapshot_sha256':Client.digest(snapshot), 'sources':list(client.sources.values()),
                   'cache_hits':client.hits, 'http_requests':client.requests})
        from topic_map import render_map
        render_map(analysis, out/'topic-map.md')
        return {'out':str(out.resolve()), 'map':str((out/'topic-map.json').resolve()),
                'languages':[{k:row[k] for k in ('language','coverage','growth_pct','share_growth_pct','missing_qids')}
                             for row in analysis['languages']],
                'cross_language_comparable':analysis['cross_language_comparable'],
                'cache_hits':client.hits,'http_requests':client.requests}
    if args.command == 'verify-spike':
        from spike_evidence import verify_spike
        result = verify_spike(load(args.map), args.language, args.date, load(args.evidence))
        if args.out:
            path = Path(args.out)
            if path.exists():
                raise DataError('Evidence output exists; use a new filename')
            write_json(path, result)
        return result
    if args.command == 'run':
        config = load(args.config)
        validate_config(config)
        out = prepare_output(args.out)
        snapshot = collect(client, config)
        write_json(out/'snapshot.json', snapshot)
        counters = {'cache_hits':client.hits, 'http_requests':client.requests}
        provenance = {'schema_version':2, 'code_version':'1.0.1', 'created_at':snapshot['created_at'],
                      'source_acquisition':counters.copy(),
                      'current_run':{'operation':'run', **counters},
                      'sources':list(client.sources.values()), 'snapshot_sha256':Client.digest(snapshot)}
    else:
        out = prepare_output(args.out)
        snapshot = load(Path(args.run)/'snapshot.json')
        provenance = load(Path(args.run)/'provenance.json')
        if provenance.get('snapshot_sha256') != Client.digest(snapshot):
            raise DataError('Snapshot hash mismatch; rerun from the source config')
        acquisition = provenance.get('source_acquisition')
        if acquisition is None:
            acquisition = {key:provenance.get(key) for key in ('cache_hits','http_requests')}
        provenance = {key:value for key,value in provenance.items()
                      if key not in ('cache_hits','http_requests','source_acquisition','current_run')}
        provenance.update({'schema_version':2, 'code_version':'1.0.1',
                           'source_acquisition':acquisition,
                           'current_run':{'operation':'reanalyze', 'cache_hits':client.hits,
                                          'http_requests':client.requests},
                           'parent_run':str(Path(args.run).resolve()),
                           'reanalysis_at':datetime.now(timezone.utc).isoformat()})
        if args.criteria:
            snapshot['config']['criteria'] = {**snapshot['config'].get('criteria',{}), **load(args.criteria)}
        write_json(out/'snapshot.json',snapshot)
        provenance['snapshot_sha256'] = Client.digest(snapshot)
    result = analyze(snapshot)
    from report import render
    render(result,out)
    write_json(out/'provenance.json',provenance)
    return {'out':str(out.resolve()), 'report_pdf':str((out/'report.pdf').resolve()),
            'research_order':result['research_order'], 'comparable_baskets':result['comparable_baskets'],
            'series':[{k:s[k] for k in ('id','latest_views','growth_pct','share_growth_pct','peak_excluded_growth_pct','signal','warnings')} for s in result['series']],
            'cache_hits':client.hits, 'http_requests':client.requests}

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--cache', default=str(ROOT/'.cache'))
    common.add_argument('--offline', action='store_true',help='Read cache only; fail on miss; retain original retrieval dates')
    common.add_argument('--refresh', action='store_true',help='Refetch every used response')
    d = sub.add_parser('discover',parents=[common]); d.add_argument('--query',required=True); d.add_argument('--search-language',default='en')
    m = sub.add_parser('plan',parents=[common]); m.add_argument('--qids',nargs='+',required=True); m.add_argument('--languages',nargs='+',required=True)
    m.add_argument('--question',required=True); m.add_argument('--start'); m.add_argument('--end'); m.add_argument('--out',required=True)
    t = sub.add_parser('map',parents=[common]); t.add_argument('--root-qid',required=True)
    t.add_argument('--qids',nargs='+',required=True); t.add_argument('--languages',nargs='+',required=True)
    t.add_argument('--start'); t.add_argument('--end'); t.add_argument('--out',required=True)
    v = sub.add_parser('verify-spike',parents=[common]); v.add_argument('--map', required=True)
    v.add_argument('--language', required=True); v.add_argument('--date', required=True)
    v.add_argument('--evidence', required=True); v.add_argument('--out')
    r = sub.add_parser('run',parents=[common]); r.add_argument('--config',required=True); r.add_argument('--out',required=True)
    a = sub.add_parser('reanalyze',parents=[common]); a.add_argument('--run',required=True); a.add_argument('--criteria'); a.add_argument('--out',required=True)
    return p

def main():
    args = parser().parse_args()
    try:
        if args.offline and args.refresh:
            raise DataError('--offline and --refresh are mutually exclusive')
        print(json.dumps(execute(args),ensure_ascii=False,indent=2,allow_nan=False))
    except (DataError, OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'error':str(e),'hint':'Correct the input or retry online; never replace missing observations with zero.'}),file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())

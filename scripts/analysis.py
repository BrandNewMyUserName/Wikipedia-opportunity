"""Deterministic descriptive evidence, never a forecast of paying customers."""
from __future__ import annotations
import calendar
import math
import re
import statistics
from datetime import date, datetime, timezone
from data import DataError, days, months

DEFAULT_CRITERIA = {'min_baseline_views': 1000, 'min_growth_pct': 10,
                    'min_share_growth_pct': 0, 'min_robust_growth_pct': 0,
                    'min_positive_months': 8, 'max_top7_share': 0.15}

def validate_config(c):
    if c.get('schema_version') != 1:
        raise DataError('schema_version must be 1')
    try:
        start, end = date.fromisoformat(c['start']), date.fromisoformat(c['end'])
    except (KeyError, ValueError, TypeError) as e:
        raise DataError('start/end must be ISO dates') from e
    if start.day != 1 or end.day != calendar.monthrange(end.year, end.month)[1]:
        raise DataError('Use full calendar months only')
    if start < date(2015, 7, 1) or end >= datetime.now(timezone.utc).date().replace(day=1):
        raise DataError('Window must be completed months since 2015-07')
    if not 24 <= len(months(c['start'], c['end'])) <= 60:
        raise DataError('Use 24 to 60 months; annual comparison needs 24')
    if not isinstance(c.get('question'), str) or not 1 <= len(c['question']) <= 500:
        raise DataError('question must contain 1 to 500 characters')
    series = c.get('series', [])
    if not 1 <= len(series) <= 6:
        raise DataError('Use 1 to 6 series per one-page report')
    ids = set()
    for s in series:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', s.get('id', '')) or s['id'] in ids:
            raise DataError('Series IDs must be unique ASCII identifiers, max 40 chars')
        ids.add(s['id'])
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,19}', s.get('language', '')):
            raise DataError('Invalid Wikipedia language code')
        if not isinstance(s.get('label'), str) or not 1 <= len(s['label']) <= 100:
            raise DataError('Each series needs a label, max 100 chars')
        if not 1 <= len(s.get('articles', [])) <= 6:
            raise DataError('Each series needs 1 to 6 articles')
        qids, titles = set(), set()
        for a in s['articles']:
            if not re.fullmatch(r'Q[1-9][0-9]*', a.get('qid', '')):
                raise DataError('Each article needs a Wikidata QID')
            if not isinstance(a.get('title'), str) or not 1 <= len(a['title']) <= 250:
                raise DataError('Each article needs a valid title')
            if a['qid'] in qids or a['title'] in titles:
                raise DataError('Duplicate article in basket')
            qids.add(a['qid']); titles.add(a['title'])
    criteria = {**DEFAULT_CRITERIA, **c.get('criteria', {})}
    if set(criteria) != set(DEFAULT_CRITERIA):
        raise DataError('Unknown criteria field')
    for k, v in criteria.items():
        if type(v) not in (int, float) or not math.isfinite(v):
            raise DataError(f'Invalid criterion: {k}')
    if criteria['min_baseline_views'] < 0 or not 0 <= criteria['max_top7_share'] <= 1:
        raise DataError('Invalid baseline or spike threshold')
    if type(criteria['min_positive_months']) is not int or not 0 <= criteria['min_positive_months'] <= 12:
        raise DataError('min_positive_months must be an integer from 0 to 12')
    return criteria

def growth(a, b):
    return (b / a - 1) * 100 if a and b is not None else None

def assess(series, start, end, criteria):
    expected = days(start, end)
    month_keys = months(start, end)
    daily = {day: (sum(a['daily'][day] for a in series['articles'])
                   if all(day in a['daily'] for a in series['articles']) else None) for day in expected}
    monthly = []
    for m in month_keys:
        vals = [v for d, v in daily.items() if d.startswith(m)]
        total = sum(vals) if all(v is not None for v in vals) else None
        denom = series['project_totals'].get(m)
        monthly.append({'month': m, 'views': total, 'project_views': denom,
                        'views_per_million': total / denom * 1e6 if total is not None and denom else None})
    pairs = monthly[-24:]
    before, after = pairs[:12], pairs[12:]
    complete = all(x['views'] is not None for x in pairs)
    normalized = complete and all(x['project_views'] for x in pairs)
    base = sum(x['views'] for x in before) if complete else None
    latest = sum(x['views'] for x in after) if complete else None
    raw_growth = growth(base, latest)
    share_growth = None
    if normalized:
        share_growth = growth(base / sum(x['project_views'] for x in before), latest / sum(x['project_views'] for x in after))
    yoy = [growth(a['views'], b['views']) for a, b in zip(before, after)] if complete else []
    positive = sum(x is not None and x > 0 for x in yoy)
    median_yoy = statistics.median([x for x in yoy if x is not None]) if any(x is not None for x in yoy) else None
    robust = None
    if complete:
        peak = max(range(12), key=lambda i: after[i]['views'])
        robust = growth(base - before[peak]['views'], latest - after[peak]['views'])
    last_days = [(d, v) for d, v in daily.items() if d[:7] >= after[0]['month'] and v is not None]
    peak_days = sorted(last_days, key=lambda x: x[1], reverse=True)[:7]
    top7 = sum(v for _, v in peak_days) / latest if latest else None
    warnings = []
    if not complete: warnings.append('missing_article_days')
    if not normalized: warnings.append('missing_project_totals')
    if len([v for v in daily.values() if v is None]): warnings.append('incomplete_chart_history')
    if base is not None and base < criteria['min_baseline_views']: warnings.append('small_baseline')
    if raw_growth is None: warnings.append('growth_undefined')
    if top7 is not None and top7 > criteria['max_top7_share']: warnings.append('spike_concentration')
    if raw_growth is not None and raw_growth > 0 and (robust is None or robust <= 0): warnings.append('peak_month_sensitive')
    for a in series['articles']: warnings.extend(a.get('warnings', []))
    warnings = sorted(set(warnings))
    if not complete or not normalized or raw_growth is None:
        signal = 'insufficient_data'
    elif any(w in warnings for w in ('small_baseline','spike_concentration','peak_month_sensitive','page_move_in_window')):
        signal = 'fragile'
    elif (raw_growth >= criteria['min_growth_pct'] and share_growth >= criteria['min_share_growth_pct']
          and robust is not None and robust >= criteria['min_robust_growth_pct'] and positive >= criteria['min_positive_months']):
        signal = 'research_next'
    else:
        signal = 'no_clear_growth'
    return {'id': series['id'], 'label': series['label'], 'language': series['language'],
            'articles': [{k:v for k,v in a.items() if k != 'daily'} for a in series['articles']],
            'monthly': monthly, 'baseline_views': base, 'latest_views': latest,
            'growth_pct': raw_growth, 'share_growth_pct': share_growth,
            'peak_excluded_growth_pct': robust, 'median_month_yoy_pct': median_yoy,
            'positive_yoy_months': positive, 'top7_share': top7, 'top7_days': peak_days,
            'coverage': sum(v is not None for v in daily.values()) / len(daily),
            'warnings': warnings, 'signal': signal}

def analyze(snapshot, criteria_override=None):
    config = snapshot['config']
    if criteria_override:
        config = {**config, 'criteria': {**config.get('criteria', {}), **criteria_override}}
    criteria = validate_config(config)
    results = [assess(s, config['start'], config['end'], criteria) for s in snapshot['series']]
    baskets = {tuple(sorted(a['qid'] for a in s['articles'])) for s in snapshot['series']}
    comparable = len(baskets) == 1
    rank = sorted((s for s in results if s['signal'] == 'research_next'),
                  key=lambda s: (s['share_growth_pct'], s['latest_views']), reverse=True) if comparable else []
    return {'schema_version': 1, 'question': config['question'], 'start': config['start'], 'end': config['end'],
            'comparison_window': months(config['start'], config['end'])[-24:],
            'criteria': criteria, 'source_retrieval_window':snapshot.get('source_retrieval_window', []), 'comparable_baskets': comparable,
            'research_order': [s['id'] for s in rank], 'series': results,
            'caveats': ['Pageviews measure attention, not people, intent, real-world prevalence or market size.',
                        'Wikipedia language editions are not countries; audiences can overlap.',
                        'Current titles only: redirect traffic and complete page-move history are not merged.',
                        'User agent filtering is imperfect; seasonality, news, search and bot changes can affect views.',
                        'Single articles are narrow proxies; basket views are not deduplicated readers.',
                        'Signals are descriptive heuristics, not statistical confidence or causal evidence.']}

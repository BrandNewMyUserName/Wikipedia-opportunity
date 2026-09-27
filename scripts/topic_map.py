"""Auditable, QID-aligned topic map across Wikipedia language editions."""
from __future__ import annotations

import calendar
import statistics
from datetime import date, timedelta

from analysis import growth
from data import DataError, days, months


def month_total(daily, month):
    keys = [day for day in daily if day.startswith(month)]
    expected = calendar.monthrange(*map(int, month.split('-')))[1]
    return sum(daily[day] for day in keys) if len(keys) == expected else None


def collect_map(client, qids, languages, start, end):
    entities = client.entities(qids)
    concepts = []
    for qid in qids:
        entity = entities.get(qid, {})
        if 'missing' in entity or not entity:
            raise DataError(f'Unknown Wikidata item: {qid}')
        concepts.append({'qid': qid, 'label': entity.get('labels', {}).get('en', {}).get('value', qid)})
    rows = []
    totals = {}
    for language in languages:
        total = client.totals(language, start, end)
        totals[language] = total
        for concept in concepts:
            qid = concept['qid']
            link = entities[qid].get('sitelinks', {}).get(language.replace('-', '_') + 'wiki')
            if not link:
                rows.append({'language': language, **concept, 'status': 'missing_sitelink'})
                continue
            page = client.validate_article(language, {'qid': qid, 'title': link['title']}, start)
            page['daily'] = client.series(language, page['title'], start, end)
            rows.append({'language': language, **concept, 'status': 'available', **page})
        if not total:
            raise DataError(f'Missing edition totals: {language}')
    return {'schema_version': 1, 'qids': qids, 'languages': languages,
            'start': start, 'end': end, 'concepts': concepts, 'rows': rows,
            'project_totals': totals}


def analyze_map(snapshot):
    keys = months(snapshot['start'], snapshot['end'])[-24:]
    all_days = days(snapshot['start'], snapshot['end'])
    output = []
    for language in snapshot['languages']:
        rows = [r for r in snapshot['rows'] if r['language'] == language]
        available = [r for r in rows if r['status'] == 'available']
        missing = [r['qid'] for r in rows if r['status'] != 'available']
        per_concept = []
        for row in rows:
            if row['status'] != 'available':
                per_concept.append({k: row[k] for k in ('qid', 'label', 'status')})
                continue
            monthly = [month_total(row['daily'], m) for m in keys]
            first = sum(monthly[:12]) if all(v is not None for v in monthly[:12]) else None
            last = sum(monthly[12:]) if all(v is not None for v in monthly[12:]) else None
            per_concept.append({'qid': row['qid'], 'label': row['label'], 'status': 'available',
                                'title': row['title'], 'url': row['url'], 'pageid': row['pageid'],
                                'warnings': row['warnings'], 'baseline_views': first,
                                'latest_views': last, 'growth_pct': growth(first, last),
                                'monthly': dict(zip(keys, monthly))})
        # A basket is complete only when every selected article has every observation.
        basket = {m: sum(c['monthly'][m] for c in per_concept if c['status'] == 'available')
                  if available and all(c['monthly'][m] is not None for c in per_concept if c['status'] == 'available')
                  else None for m in keys}
        prior = sum(basket[m] for m in keys[:12]) if all(basket[m] is not None for m in keys[:12]) else None
        latest = sum(basket[m] for m in keys[12:]) if all(basket[m] is not None for m in keys[12:]) else None
        paired_growth = ([growth(basket[old], basket[new]) for old, new in zip(keys[:12], keys[12:])]
                         if prior is not None and latest is not None else [])
        positive_months = sum(value is not None and value > 0 for value in paired_growth)
        peak_month_excluded = None
        if prior is not None and latest is not None:
            peak_index = max(range(12), key=lambda i: basket[keys[12+i]])
            peak_month_excluded = growth(prior-basket[keys[peak_index]],
                                         latest-basket[keys[12+peak_index]])
        denominators = snapshot['project_totals'][language]
        norm_prior = sum(denominators[m] for m in keys[:12]) if all(denominators.get(m) for m in keys[:12]) else None
        norm_latest = sum(denominators[m] for m in keys[12:]) if all(denominators.get(m) for m in keys[12:]) else None
        share_growth = growth(prior / norm_prior, latest / norm_latest) if prior is not None and latest is not None and norm_prior and norm_latest else None
        for concept in per_concept:
            if concept['status'] == 'available':
                concept['latest_basket_share_pct'] = (100 * concept['latest_views'] / latest
                    if concept['latest_views'] is not None and latest else None)
        yearly_days = [d for d in all_days if d[:7] >= keys[12]]
        peaks = []
        for day in yearly_days:
            if not available or any(day not in r['daily'] for r in available):
                continue
            views = sum(r['daily'][day] for r in available)
            baseline = [sum(r['daily'][day_before] for r in available)
                        for day_before in ((date.fromisoformat(day)-timedelta(days=i)).isoformat() for i in range(1,29))
                        if all(day_before in r['daily'] for r in available)]
            if len(baseline) < 14:
                continue
            median = statistics.median(baseline)
            if views >= max(100, 3 * median):
                top = sorted(((r['qid'], r['daily'][day]) for r in available), key=lambda x: x[1], reverse=True)[:3]
                leader = next(r for r in available if r['qid'] == top[0][0])
                english = next(c['label'] for c in snapshot['concepts'] if c['qid'] == top[0][0])
                peaks.append({'date': day, 'views': views, 'prior_28d_median': median,
                              'leading_qids': [q for q, _ in top],
                              'search_queries': [f'"{leader["title"]}" {day}', f'"{english}" {day}'],
                              'evidence_status': 'unverified_search_required'})
        selected = []
        for peak in sorted(peaks, key=lambda x: x['views'], reverse=True):
            if all(abs((date.fromisoformat(peak['date']) - date.fromisoformat(old['date'])).days) > 3
                   for old in selected):
                selected.append(peak)
            if len(selected) == 5:
                break
        output.append({'language': language, 'missing_qids': missing,
                       'coverage': {'available': len(available), 'selected': len(rows)},
                       'baseline_views': prior, 'latest_views': latest,
                       'growth_pct': growth(prior, latest), 'share_growth_pct': share_growth,
                       'peak_month_excluded_growth_pct': peak_month_excluded,
                       'positive_yoy_months': positive_months,
                       'largest_spike_day_share_pct': (100 * selected[0]['views'] / latest
                                                        if selected and latest else None),
                       'monthly': basket, 'concepts': per_concept,
                       'spikes': selected})
    return {'schema_version': 1, 'start': snapshot['start'], 'end': snapshot['end'],
            'qids': snapshot['qids'], 'languages': output,
            'cross_language_comparable': all(not row['missing_qids'] and row['baseline_views'] is not None
                                              and row['latest_views'] is not None for row in output),
            'limits': ['Language edition is not reader geography.',
                       'Basket pageviews are not unique people.',
                       'Missing sitelink or observation is unknown, never zero.',
                       'Spike search queries are leads, not explanations.']}


def render_map(analysis, path):
    def fmt(value):
        return 'unknown' if value is None else f'{value:+.1f}%'
    lines = ['# Wikipedia topic map',
             f'{analysis["start"]} to {analysis["end"]}; last 12 complete months versus prior 12.',
             '', 'QIDs define the same concepts across editions. Missing articles remain explicit.', '']
    for language in analysis['languages']:
        lines += [f'## {language["language"]}',
                  f'Coverage: {language["coverage"]["available"]}/{language["coverage"]["selected"]}; '
                  f'basket YoY {fmt(language["growth_pct"])}; edition share YoY {fmt(language["share_growth_pct"])}; '
                  f'peak-month-excluded YoY {fmt(language["peak_month_excluded_growth_pct"])}; '
                  f'positive matched months {language["positive_yoy_months"]}/12.',
                  '', '| QID | Concept | Article | Latest 12m views | YoY | Basket share |',
                  '|---|---|---|---:|---:|---:|']
        for concept in language['concepts']:
            if concept['status'] == 'available':
                article = f'[{concept["title"]}]({concept["url"]})'
                count = str(concept['latest_views']) if concept['latest_views'] is not None else 'unknown'
                share = ('unknown' if concept['latest_basket_share_pct'] is None
                         else f'{concept["latest_basket_share_pct"]:.1f}%')
            else:
                article, count, share = 'missing sitelink', 'unknown', 'unknown'
            lines.append(f'| {concept["qid"]} | {concept["label"]} | {article} | {count} | {fmt(concept.get("growth_pct"))} | {share} |')
        lines += ['', '### Spike leads', 'Search by exact date and leading concept names; verify an event with dated independent sources.']
        for spike in language['spikes']:
            lines.append(f'- {spike["date"]}: {spike["views"]} views vs prior median {spike["prior_28d_median"]:g}; search `{spike["search_queries"][0]}` (also English and nearby dates); cause unverified.')
        if not language['spikes']:
            lines.append('- No days met the configured descriptive spike rule.')
        lines.append('')
    lines += ['Cross-language comparison: ' + ('same selected QID coverage' if analysis['cross_language_comparable']
               else 'partial coverage; do not rank full topic totals across editions'),
              '', *['- ' + x for x in analysis['limits']]]
    path.write_text('\n'.join(lines) + '\n')

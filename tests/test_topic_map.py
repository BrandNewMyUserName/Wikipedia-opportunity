from datetime import date, timedelta

from topic_map import analyze_map, collect_map
from spike_evidence import verify_spike


def daily(start, end, value):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return {(first + timedelta(days=n)).isoformat(): value for n in range((last-first).days+1)}


def test_map_preserves_missing_sitelink_and_aligns_qids():
    class FakeClient:
        def entities(self, qids):
            return {'Q1': {'labels': {'en': {'value': 'Root'}}, 'sitelinks': {
                        'enwiki': {'title': 'Root'}, 'ukwiki': {'title': 'Корінь'}}},
                    'Q2': {'labels': {'en': {'value': 'Child'}}, 'sitelinks': {
                        'enwiki': {'title': 'Child'}}}}
        def totals(self, language, start, end):
            return {m: 100000 for m in [f'{year}-{month:02d}' for year in (2023, 2024) for month in range(1, 13)]}
        def validate_article(self, language, article, start):
            return {**article, 'pageid': 1 if article['qid']=='Q1' else 2,
                    'url': 'https://example.org/wiki/'+article['title'], 'warnings': []}
        def series(self, language, title, start, end):
            return daily(start, end, 1 if title in ('Root', 'Корінь') else 2)
    snapshot = collect_map(FakeClient(), ['Q1', 'Q2'], ['en', 'uk'], '2023-01-01', '2024-12-31')
    result = analyze_map(snapshot)
    en, uk = result['languages']
    assert [x['qid'] for x in en['concepts']] == [x['qid'] for x in uk['concepts']] == ['Q1','Q2']
    assert uk['missing_qids'] == ['Q2']
    assert uk['coverage'] == {'available': 1, 'selected': 2}
    assert result['cross_language_comparable'] is False
    assert uk['concepts'][1]['status'] == 'missing_sitelink'
    assert uk['concepts'][1].get('latest_views') is None
    assert en['latest_views'] > uk['latest_views']


def test_incomplete_days_suppress_topic_growth():
    d = daily('2023-01-01', '2024-12-31', 5)
    del d['2024-02-01']
    snapshot = {'start':'2023-01-01','end':'2024-12-31','qids':['Q1'],
                'languages':['en'],'concepts':[{'qid':'Q1','label':'Topic'}],
                'rows':[{'language':'en','qid':'Q1','label':'Topic','status':'available',
                         'title':'Topic','url':'https://example.org','pageid':1,'warnings':[],
                         'daily':d}],
                'project_totals':{'en':{f'{year}-{month:02d}':100000 for year in (2023,2024) for month in range(1,13)}}}
    row = analyze_map(snapshot)['languages'][0]
    assert row['monthly']['2024-02'] is None
    assert row['latest_views'] is None
    assert row['growth_pct'] is None
    assert row['concepts'][0]['latest_views'] is None


def test_spike_evidence_needs_matching_date_topic_and_independent_hosts():
    topic = {'languages':[{'language':'pl','spikes':[{'date':'2026-08-12','leading_qids':['Q3887']}]}]}
    candidates = [
        {'url':'https://nasa.gov/eclipse','publisher':'NASA','event_date':'2026-08-12','matched_qids':['Q3887']},
        {'url':'https://polsa.gov.pl/eclipse','publisher':'POLSA','event_date':'2026-08-12','matched_qids':['Q3887']},
        {'url':'https://nasa.gov/other','event_date':'2026-08-12','matched_qids':['Q3887']},
        {'url':'https://science.nasa.gov/other','publisher':'NASA','event_date':'2026-08-12','matched_qids':['Q3887']},
        {'url':'https://example.org/old','event_date':'2025-08-12','matched_qids':['Q3887']},
        {'url':'https://example.org/unrelated','event_date':'2026-08-12','matched_qids':['Q1']}]
    result = verify_spike(topic,'pl','2026-08-12',candidates)
    assert result['status'] == 'plausible_not_proven'
    assert len(result['accepted_sources']) == 2
    assert result['rejected_source_count'] == 4
    assert verify_spike(topic,'pl','2026-08-12',candidates[:1])['status'] == 'unverified'


def test_peak_month_can_reverse_topic_growth():
    d = daily('2023-01-01','2024-12-31',1)
    d['2024-08-12'] = 10000
    snapshot = {'start':'2023-01-01','end':'2024-12-31','qids':['Q1'],
                'languages':['en'],'concepts':[{'qid':'Q1','label':'Topic'}],
                'rows':[{'language':'en','qid':'Q1','label':'Topic','status':'available',
                         'title':'Topic','url':'https://example.org','pageid':1,'warnings':[],
                         'daily':d}],
                'project_totals':{'en':{f'{year}-{month:02d}':100000 for year in (2023,2024) for month in range(1,13)}}}
    result = analyze_map(snapshot)['languages'][0]
    assert result['growth_pct'] > 0
    assert abs(result['peak_month_excluded_growth_pct']) < 1
    assert result['largest_spike_day_share_pct'] > 50

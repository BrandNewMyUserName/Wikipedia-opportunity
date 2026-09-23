"""Wikimedia client: bounded retries, content-addressed cache and provenance."""
from __future__ import annotations
import calendar
import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

AQS = 'https://wikimedia.org/api/rest_v1/metrics/pageviews'
WD = 'https://www.wikidata.org/w/api.php'

class DataError(Exception):
    pass

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)

class Client:
    def __init__(self, cache, offline=False, refresh=False):
        self.cache = Path(cache)
        self.offline, self.refresh = offline, refresh
        self.sources = {}
        self.hits = self.requests = 0

    def get(self, url, params=None, ttl=None, missing_ok=False):
        if params:
            url += '?' + urlencode(sorted(params.items()))
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache / (key + '.json')
        record = None
        if path.exists():
            try:
                record = json.loads(path.read_text())
                if record['url'] != url or record['sha256'] != self.digest(record['data']):
                    raise DataError(f'Corrupt cache: {path}; remove it and retry online')
            except (ValueError, KeyError) as e:
                raise DataError(f'Invalid cache: {path}') from e
        fresh = record and (ttl is None or time.time() - record['fetched_epoch'] < ttl)
        if record and (self.offline or (fresh and not self.refresh)):
            self.hits += 1
        else:
            if self.offline:
                raise DataError(f'Offline cache miss: {url}')
            record = self.fetch(url, missing_ok)
            write_json(path, record)
        self.sources[key] = {k: v for k, v in record.items() if k != 'data'}
        self.sources[key]['cache_file'] = path.name
        return record['data']

    @staticmethod
    def digest(data):
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def fetch(self, url, missing_ok):
        ua = os.environ.get('WIKIMEDIA_USER_AGENT', 'WikipediaOpportunity/1.0 (B2C research; local CLI)')
        for attempt in range(4):
            delay = min(2 ** attempt, 8)
            try:
                self.requests += 1
                with urlopen(Request(url, headers={'User-Agent': ua, 'Accept': 'application/json'}), timeout=30) as response:
                    data = json.load(response)
                if 'error' in data:
                    raise DataError(f'API error: {url}: {data["error"]}')
                return self.record(url, data, 200)
            except HTTPError as e:
                if e.code == 404 and missing_ok:
                    return self.record(url, {'items': [], 'missing': True}, 404)
                if e.code not in (429, 500, 502, 503, 504):
                    raise DataError(f'HTTP {e.code}: {url}') from e
                retry = e.headers.get('Retry-After', '')
                if retry.isdigit():
                    if int(retry) > 60:
                        raise DataError(f'Rate limited; retry in {retry}s') from e
                    delay = max(delay, int(retry))
            except (URLError, TimeoutError) as e:
                if attempt == 3:
                    raise DataError(f'Network error: {url}: {e}') from e
            except (ValueError, OSError) as e:
                raise DataError(f'Invalid response: {url}: {e}') from e
            if attempt < 3:
                time.sleep(delay)
        raise DataError(f'Retries exhausted: {url}')

    def record(self, url, data, status):
        return {'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                'fetched_epoch': time.time(), 'status': status, 'sha256': self.digest(data), 'data': data}

    def api(self, language, **params):
        return self.get(f'https://{language}.wikipedia.org/w/api.php',
                        {'format': 'json', 'formatversion': 2, **params}, ttl=86400)

    def search(self, query, language='en'):
        d = self.get(WD, {'action': 'wbsearchentities', 'search': query, 'language': language,
                          'format': 'json', 'limit': 6}, ttl=86400)
        return [{k: x.get(k) for k in ('id', 'label', 'description')} for x in d['search']]

    def entities(self, qids):
        return self.get(WD, {'action': 'wbgetentities', 'ids': '|'.join(qids),
                            'props': 'labels|descriptions|sitelinks', 'languages': 'en',
                            'format': 'json'}, ttl=86400)['entities']

    def validate_article(self, lang, article, start):
        d = self.api(lang, action='query', prop='pageprops|info', inprop='url',
                     titles=article['title'], redirects=1)
        pages = d.get('query', {}).get('pages', [])
        if len(pages) != 1 or 'missing' in pages[0] or 'invalid' in pages[0]:
            raise DataError(f'Missing article: {lang}:{article["title"]}')
        p = pages[0]
        if p.get('ns') != 0 or 'disambiguation' in p.get('pageprops', {}):
            raise DataError(f'Not a topic article: {lang}:{p["title"]}')
        if p.get('pageprops', {}).get('wikibase_item') != article['qid']:
            raise DataError(f'Wikidata mismatch for {lang}:{p["title"]}; rediscover the topic')
        warnings = []
        if d['query'].get('redirects'):
            warnings.append('input_redirect_resolved')
        moves = self.api(lang, action='query', list='logevents', letype='move',
                         letitle=p['title'], leend=start + 'T00:00:00Z', lelimit=1)
        # Source-title logs cannot guarantee that earlier titles were discovered.
        if moves.get('query', {}).get('logevents'):
            warnings.append('page_move_in_window')
        return {**article, 'title': p['title'], 'pageid': p['pageid'],
                'url': p['fullurl'], 'warnings': warnings}

    def range_items(self, build_url, start, end):
        """Batch contiguous cache misses; monthly indexes reference real raw responses."""
        records, absent, loaded = {}, [], {}
        def edges(m):
            first = date.fromisoformat(m + '-01')
            return first, date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        def key(url):
            return hashlib.sha256(url.encode()).hexdigest()
        for m in months(start,end):
            first,last = edges(m)
            url = build_url(first,last)
            index = self.cache/'index'/(key(url)+'.json')
            source = url
            if index.exists() and not self.refresh:
                source = json.loads(index.read_text())['source_url']
                prefix = url.rsplit('/',2)[0]+'/'
                if not re.fullmatch(re.escape(prefix)+r'\d{10}/\d{10}',source):
                    raise DataError('Invalid range-cache source reference')
            raw = self.cache/(key(source)+'.json')
            if raw.exists() and not self.refresh:
                if source not in loaded:
                    # A range can include recent observations; its end controls freshness.
                    source_end = datetime.strptime(source.rsplit('/',1)[1][:8],'%Y%m%d').date()
                    loaded[source] = self.get(source,ttl=86400 if (date.today()-source_end).days<60 else None,missing_ok=True)
                payload = loaded[source]
                if not isinstance(payload.get('items'),list):
                    raise DataError('API response has no items array')
                records[m] = [x for x in payload['items'] if x['timestamp'].startswith(m.replace('-',''))]
            else:
                absent.append(m)
        if self.offline and absent:
            raise DataError('Offline cache miss for months: '+', '.join(absent))
        # Gaps already represented by valid cached responses must remain gaps, not zeros.
        groups=[]
        for m in absent:
            if groups:
                previous = groups[-1][-1]
                y,mo = map(int,previous.split('-'))
                contiguous = m == f'{y+mo//12:04d}-{mo%12+1:02d}'
            else:
                contiguous=False
            if contiguous: groups[-1].append(m)
            else: groups.append([m])
        for group in groups:
            first,_ = edges(group[0]); _,last = edges(group[-1])
            source = build_url(first,last)
            payload = self.get(source,missing_ok=True,ttl=86400 if (date.today()-last).days<60 else None)
            if not isinstance(payload.get('items'),list):
                raise DataError('API response has no items array')
            for x in payload['items']:
                if not f'{first:%Y%m%d}' <= x['timestamp'][:8] <= f'{last:%Y%m%d}':
                    raise DataError('Out-of-window API observation')
            for m in group:
                records[m]=[x for x in payload['items'] if x['timestamp'].startswith(m.replace('-',''))]
                monthly_url=build_url(*edges(m))
                write_json(self.cache/'index'/(key(monthly_url)+'.json'),{'source_url':source})
        return [x for m in months(start,end) for x in records[m]]

    def series(self, language, title, start, end):
        result = {}
        def url(first,last):
            return f'{AQS}/per-article/{language}.wikipedia.org/all-access/user/{quote(title.replace(" ", "_"), safe="")}/daily/{first:%Y%m%d}00/{last:%Y%m%d}00'
        for x in self.range_items(url,start,end):
            day = datetime.strptime(x['timestamp'][:8], '%Y%m%d').date().isoformat()
            if day in result:
                raise DataError(f'Duplicate day: {day}')
            value = x['views']
            if type(value) is not int or value < 0:
                raise DataError(f'Invalid views at {day}')
            result[day] = value
        return result

    def totals(self, language, start, end):
        result = {}
        def url(first,last):
            return f'{AQS}/aggregate/{language}.wikipedia.org/all-access/user/monthly/{first:%Y%m%d}00/{last:%Y%m%d}00'
        for x in self.range_items(url,start,end):
            m = x['timestamp'][:4] + '-' + x['timestamp'][4:6]
            if m in result or type(x['views']) is not int or x['views'] <= 0:
                raise DataError(f'Invalid project total for {language}:{m}')
            result[m] = x['views']
        return result

def months(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while (a.year, a.month) <= (b.year, b.month):
        out.append(a.strftime('%Y-%m'))
        a = date(a.year + a.month // 12, a.month % 12 + 1, 1)
    return out

def days(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b-a).days + 1)]

def default_window():
    today = datetime.now(timezone.utc).date()
    end = today.replace(day=1) - timedelta(days=1)
    start = date(end.year - 2 + end.month // 12, end.month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()

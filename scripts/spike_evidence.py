"""Deterministic gate for agent-researched explanations of Wikipedia spikes."""
from __future__ import annotations

from urllib.parse import urlparse

from data import DataError


def verify_spike(topic_map, language, day, candidates):
    edition = next((x for x in topic_map['languages'] if x['language'] == language), None)
    if edition is None:
        raise DataError(f'Language not in topic map: {language}')
    spike = next((x for x in edition['spikes'] if x['date'] == day), None)
    if spike is None:
        raise DataError(f'Spike date not in topic map: {language}:{day}')
    lead = spike['leading_qids'][0]
    accepted, hosts, publishers = [], set(), set()
    for source in candidates:
        url = source.get('url', '')
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower().removeprefix('www.')
        publisher = (source.get('publisher') or '').strip().casefold()
        if (parsed.scheme != 'https' or not host or host in hosts
                or (publisher and publisher in publishers)
                or source.get('event_date') != day or lead not in source.get('matched_qids', [])):
            continue
        hosts.add(host)
        if publisher:
            publishers.add(publisher)
        accepted.append({'url': url, 'event_date': day, 'matched_qids': source['matched_qids'],
                         'publisher': source.get('publisher')})
    return {'language': language, 'spike_date': day, 'leading_qid': lead,
            'status': 'plausible_not_proven' if len(accepted) >= 2 else 'unverified',
            'accepted_sources': accepted, 'rejected_source_count': len(candidates)-len(accepted),
            'limits': 'The gate checks supplied dates, QIDs and independent hosts; the agent must inspect source content. Coincidence does not prove traffic causation.'}

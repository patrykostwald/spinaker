"""Badania pomocnicze: nie zmieniają werdyktu ani nie zastępują oceny dowodów."""
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests
from django.core.cache import cache
from django.utils import timezone

from news.loaded_words import loaded_data

logger = logging.getLogger(__name__)
HF_MODELS = {'sentiment': 'Voicelab/herbert-base-cased-sentiment',
             'hate_speech': 'dkleczek/Polish-Hate-Speech-Detection-Herbert-Large'}
TIMEOUT = (3, 10)


def _key(name):
    key = os.environ.get(name, '').strip()
    if not key:
        logger.debug('clinic lab %s skipped: missing key', name)
    return key


def _cached(name, payload, operation):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    key = f'clinic-lab:{name}:{digest}'
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        value = operation()
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError, AttributeError):
        # Nie logujemy URL z kluczem ani treści odpowiedzi dostawcy.
        logger.warning('clinic lab %s unavailable', name)
        value = {'status': 'brak odpowiedzi'}
    cache.set(key, value, 300 if isinstance(value, dict) and value.get('status') == 'brak odpowiedzi' else 86400)
    return value


def _json_request(method, url, **kwargs):
    response = requests.request(method, url, timeout=TIMEOUT, allow_redirects=False, **kwargs)
    response.raise_for_status()
    if response.status_code >= 300:
        raise ValueError('redirect')
    return response.json()


def classify(text, kind):
    key = _key('HF_TOKEN')
    if not key:
        return {'status': 'pominięto'}
    model = HF_MODELS[kind]

    def operation():
        # Bez tokenizera na serwerze: krótki prefiks mieści się w oknie HerBERT-a.
        # API klasyfikacji nie dokumentuje parametru truncation.
        sample = text.encode('utf-8')[:480].decode('utf-8', errors='ignore')
        rows = _json_request('POST', f'https://router.huggingface.co/hf-inference/models/{model}',
                             headers={'Authorization': f'Bearer {key}'}, json={'inputs': sample})
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        best = max(rows, key=lambda r: float(r['score']))
        score = float(best['score'])
        if not math.isfinite(score) or not 0 <= score <= 1 or not isinstance(best['label'], str):
            raise ValueError('invalid classification')
        return {'status': 'ok', 'model': model, 'label': best['label'], 'confidence': score,
                'truncated': len(sample) < len(text), 'analyzed_chars': len(sample)}

    return _cached(kind, [model, text], operation)


def public_url(url):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return False
        host = parts.hostname.lower()
        if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except (TypeError, ValueError):
        return False


def fact_checks(claim):
    key = _key('FACTCHECK_API_KEY')
    if not key:
        return []

    def operation():
        data = _json_request('GET', 'https://factchecktools.googleapis.com/v1alpha1/claims:search',
                             params={'key': key, 'query': claim, 'languageCode': 'pl', 'pageSize': 5})
        return [{'type': 'istniejący fact-check', 'publisher': review.get('publisher', {}).get('name', ''),
                 'rating': review.get('textualRating', ''), 'url': review['url'],
                 'title': review.get('title', ''), 'reviewed_claim': item.get('text', '')}
                for item in data.get('claims', []) for review in item.get('claimReview', [])
                if public_url(review.get('url'))][:10]

    return _cached('factcheck', claim, operation)


def gus_sources(claim):
    key = _key('GUS_BDL_KEY')
    # Klucz włącza integrację. Dopasowujemy tylko jednoznaczny rok, kraj i nazwę zmiennej.
    years = re.findall(r'\b(?:19|20)\d{2}\b', claim)
    metrics = [name for name in ('stopa bezrobocia rejestrowanego', 'przeciętne miesięczne wynagrodzenia brutto')
               if name in claim.lower()]
    if not key or len(set(years)) != 1 or len(metrics) != 1 or not re.search(r'\b(?:Polsce|Polska|Polski)\b', claim, re.I):
        return []
    metric, year = metrics[0], int(years[0])

    def operation():
        headers = {'X-ClientId': key}
        base = 'https://bdl.stat.gov.pl/api/v1'
        data = _json_request('GET', base + '/variables/search', headers=headers,
                             params={'name': metric, 'lang': 'pl', 'format': 'json', 'page-size': 100})
        matches = [v for v in data.get('results', []) if str(v.get('n1', '')).casefold() == metric.casefold()
                   and all(str(v.get(k) or '').casefold() in ('', 'ogółem', 'ogolem') for k in ('n2', 'n3', 'n4', 'n5'))]
        if len(matches) != 1 or data.get('totalRecords', len(data.get('results', []))) > 100:
            return []
        variable = matches[0]
        url = f"{base}/data/by-variable/{int(variable['id'])}"
        values = _json_request('GET', url, headers=headers,
                               params={'unit-level': 0, 'year': year, 'format': 'json', 'lang': 'pl'})
        rows = [r for r in values.get('results', []) if r.get('name', '').casefold() == 'polska']
        if len(rows) != 1:
            return []
        observations = [v for v in rows[0].get('values', []) if int(v['year']) == year and v.get('val') is not None]
        if len(observations) != 1:
            return []
        return [{'type': 'GUS BDL', 'publisher': 'GUS', 'title': metric, 'variable_id': variable['id'],
                 'unit': variable.get('measureUnitName', ''), 'territory': 'Polska', 'year': year,
                 'value': observations[0]['val'], 'attribute_id': observations[0].get('attrId'),
                 'url': f'{url}?unit-level=0&year={year}&format=json'}]

    return _cached('gus', claim, operation)


def scrape_quote(url, quote):
    key = _key('FIRECRAWL_API_KEY')
    if not key or not public_url(url) or not quote:
        return {'status': 'pominięto', 'url': url}

    def operation():
        # Wspólny licznik kredytów: rezerwacja przed wysłaniem, także nieudana próba zużywa limit.
        budget_key = f'clinic-lab:firecrawl:{timezone.now():%Y-%m}'
        cache.add(budget_key, 0, timeout=32 * 86400)
        if cache.incr(budget_key) > 1000:
            return {'status': 'limit', 'url': url}
        data = _json_request('POST', 'https://api.firecrawl.dev/v1/scrape',
                             headers={'Authorization': f'Bearer {key}'},
                             json={'url': url, 'formats': ['markdown']})
        if data.get('success') is not True or not isinstance(data.get('data', {}).get('markdown'), str):
            raise ValueError('missing markdown')
        markdown = data['data']['markdown']
        found = ' '.join(quote.split()).casefold() in ' '.join(markdown.split()).casefold()
        return {'status': 'ok', 'url': url, 'quote': quote, 'quote_found': found}

    return _cached('firecrawl', [url, quote], operation)


def run_lab(text, claims, words=None):
    jobs = {'sentiment': lambda: classify(text, 'sentiment'),
            'hate_speech': lambda: classify(text, 'hate_speech')}
    for index, claim in enumerate(claims):
        jobs[f'factcheck:{index}'] = lambda c=claim: fact_checks(c['claim'])
        jobs[f'gus:{index}'] = lambda c=claim: gus_sources(c['claim'])
    quotes = []
    for claim in claims:
        for source in claim.get('sources', []):
            quote = source.get('quote') or claim.get('quote')
            if not quote:
                match = re.search(r'[„"]([^”"]{12,600})[”"]', claim.get('explanation', ''))
                quote = match[1] if match else ''
            pair = (source.get('url', ''), quote)
            if quote and public_url(pair[0]) and pair not in quotes:
                quotes.append(pair)
    for index, (url, quote) in enumerate(quotes[:3]):
        jobs[f'quote:{index}'] = lambda u=url, q=quote: scrape_quote(u, q)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = dict(zip(jobs, pool.map(lambda fn: fn(), jobs.values())))
    for value in (v for k, v in values.items() if k.startswith('quote:') and v.get('status') == 'ok'):
        for claim in claims:
            for source in claim.get('sources', []):
                if source.get('url') == value['url']:
                    source['quote_check'] = {'quote': value['quote'], 'found': value['quote_found']}
    for index, claim in enumerate(claims):
        sources = claim.setdefault('sources', [])
        for kind in ('factcheck', 'gus'):
            found = values[f'{kind}:{index}']
            if isinstance(found, list):
                sources.extend(s for s in found if s['url'] not in {s.get('url') for s in sources})
    return {'loaded_words': loaded_data(text, words), **values}


def queue_archive(post):
    if post.archive_url or not (_key('IA_S3_ACCESS') and _key('IA_S3_SECRET')):
        return
    from news.tasks import clinic_archive_task
    pending_key = f'clinic-archive:queued:{post.pk}'
    if not cache.add(pending_key, 1, timeout=3600):
        return
    try:
        clinic_archive_task.apply_async(args=[post.pk], queue='clinic_archive')
    except Exception:
        # Awaria brokera nie może cofnąć ukończonej diagnozy.
        logger.warning('clinic archive queue unavailable')
        cache.delete(pending_key)


def archive_request(url, job_id=''):
    access, secret = _key('IA_S3_ACCESS'), _key('IA_S3_SECRET')
    if not access or not secret or not public_url(url):
        return {'status': 'pominięto'}
    headers = {'Authorization': f'LOW {access}:{secret}', 'Accept': 'application/json'}
    if job_id:
        if not re.fullmatch(r'[A-Za-z0-9-]+', job_id):
            raise ValueError('invalid job')
        return _json_request('GET', f'https://web.archive.org/save/status/{job_id}', headers=headers)
    return _cached('wayback', url, lambda: _json_request('POST', 'https://web.archive.org/save',
                                                      headers=headers, data={'url': url}))

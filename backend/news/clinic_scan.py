"""Dane wykresów bez zapytań do bazy i bez generowania treści."""
import hashlib
import json
import re
from urllib.parse import urlsplit

from news.x_share import diagnosis_url, shorten, weight

from news.loaded_words import loaded_data
from news.social_content import checked_claims
from news.techniques import DISPLAY_NAMES, FAMILIES, normalized, technique_category, technique_family


def model_label(model):
    name = str(model or '').split('/')[-1]
    lower = name.lower()
    size = re.search(r'(\d+)b(?:\b|$)', lower)
    suffix = f' {size[1]}B' if size else ''
    if 'gpt-oss' in lower:
        return 'gpt-oss' + suffix
    if 'qwen' in lower:
        return 'Qwen' + suffix
    if 'gemini' in lower:
        return 'Gemini' + (' Flash' if 'flash' in lower else ' Pro' if 'pro' in lower else '')
    if 'claude' in lower:
        return 'Claude'
    return name


def synthesis_fingerprint(row):
    return hashlib.sha256(json.dumps([row.claims, row.x_thread], sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()


def merge_claims(items):
    """Spójne grupy podobieństwa; puste teksty pozostają osobnymi pozycjami."""
    groups = []
    rank = {'contradicted': 3, 'misleading': 2, 'supported': 1}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        tokens = set(normalized(item.get('claim', '')).split())
        matches = [group for group in groups if tokens and any(
            other and (tokens <= other or other <= tokens or len(tokens & other) / len(tokens | other) >= .6)
            for other in group['tokens'])]
        merged = {'items': [dict(item)], 'tokens': [tokens]}
        for group in matches:
            merged['items'].extend(group['items'])
            merged['tokens'].extend(group['tokens'])
            groups.remove(group)
        groups.append(merged)
    result = []
    for group in groups:
        items = group['items']
        checked = checked_claims(items)
        best = max(checked or items, key=lambda c: rank.get(c.get('assessment'), 0))
        sources = {source['url']: source for c in items for source in c.get('sources') or []
                   if isinstance(source, dict) and source.get('url')}
        result.append({**best, 'sources': [sources[url] for url in sorted(sources)]})
    return result


def scope_data(post):
    kinds = {item.get('type', 'photo') for item in post.media or [] if isinstance(item, dict)}
    image = bool(kinds & {'photo', 'image'})
    video = bool(kinds & {'video', 'animated_gif', 'amplify_video_thumb'})
    return {'text': True, 'image': image, 'video': False,
            'analyzed': ['tekst'] + (['obraz'] if image else []),
            'not_analyzed': ['film'] if video else []}


def single_share(row, synthesis):
    tail = f'Cytaty, źródła i ograniczenia: {diagnosis_url(row.pk)}'
    author = row.post.account.display_name or row.post.account.handle
    head = f'Analiza AI wpisu {author}'
    if weight(head + '. ' + tail) > 220:
        head = 'Analiza AI wpisu'
    lead = shorten((synthesis or {}).get('lead', ''), 220 - weight(head + ':  ' + tail))
    return (head + ': ' + lead if lead else head + '.') + ' ' + tail


def scan_data(row):
    families = dict.fromkeys(FAMILIES, 0)
    techniques, seen = [], set()
    for item in row.techniques or []:
        if not isinstance(item, dict):
            continue
        category = technique_category(item)
        if category in seen:
            continue
        seen.add(category)
        family = technique_family(category)
        families[family] += 1
        techniques.append({'category': category, 'family': family,
                           'name': DISPLAY_NAMES[category], 'quote': item.get('quote', '')})
    distinct = merge_claims(row.claims)
    checked = checked_claims(distinct)
    claims = {key: sum(c.get('assessment') == key for c in checked)
              for key in ('supported', 'misleading', 'contradicted')}
    opinions = sum(c.get('assessment') == 'unverified' and not c.get('sources') for c in distinct)
    claims.update(checked=len(checked), opinions=opinions, distinct=len(distinct),
                  unverified=len(distinct) - len(checked) - opinions)
    sources = set()
    for claim in checked:
        for source in claim.get('sources') or []:
            try:
                url = urlsplit(source.get('url', ''))
                if url.scheme in ('http', 'https') and url.hostname:
                    sources.add(url.hostname.lower().removeprefix('www.'))
            except ValueError:
                continue
    council = (row.usage or {}).get('council') or {}
    votes = [{'model': model_label(m.get('model')), 'verdict': m.get('verdict'),
              'intensity': m.get('intensity')} for m in council.get('members') or []]
    thread = row.x_thread or []
    safe = (not (claims['unverified'] + claims['opinions']) or
            (row.usage or {}).get('scan_synthesis') == synthesis_fingerprint(row))
    synthesis = {'lead': thread[0], 'points': thread[1:]} if thread and safe else None
    scores = [v['intensity'] for v in votes if isinstance(v['intensity'], (int, float))]
    agreement = f"{sum(v['verdict'] == row.verdict for v in votes)}/{len(votes)}" if votes else None
    return {'loaded': loaded_data(row.post.text, (row.usage or {}).get('loaded_words')),
            'families': {key: {'technique_types': count} for key, count in families.items()}, 'techniques': techniques[:6], 'claims': claims, 'sources': len(sources), 'source_domains': sorted(sources)[:5],
            'scope': scope_data(row.post), 'share': {'single': single_share(row, synthesis)},
            'diagnosed_at': row.diagnosed_at,
            'council': {'models': len(votes), 'verdict_agreement': agreement,
                        'range': [min(scores), max(scores)] if scores else None,
                        'method': ('Mediana ocen modeli z rozstrzygniętym werdyktem; dla „bez spinu” maksymalnie 20.'
                                   if votes else 'Ocena modelu diagnozującego; brak danych konsylium.'), 'agreement': council.get('agreement'), 'votes': votes,
                        'chair': model_label(council.get('chair')), 'escalated': bool(council.get('escalated')),
                        'reviewed': isinstance(council.get('review'), dict)
                                    and isinstance(council['review'].get('ok'), bool)},
            'synthesis': synthesis}

"""Dane wykresów bez zapytań do bazy i bez generowania treści."""
import hashlib
import json
import re

from news.social_content import checked_claims
from news.techniques import FAMILIES, technique_category, technique_family


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
                           'name': item.get('name') or category, 'quote': item.get('quote', '')})
    checked = checked_claims(row.claims)
    claims = {key: sum(c.get('assessment') == key for c in checked)
              for key in ('supported', 'misleading', 'contradicted')}
    claims.update(checked=len(checked), unverified=len(row.claims or []) - len(checked))
    sources = {s['url'] for c in checked for s in c.get('sources') or []
               if s.get('url', '').startswith(('https://', 'http://'))}
    council = (row.usage or {}).get('council') or {}
    votes = [{'model': model_label(m.get('model')), 'verdict': m.get('verdict'),
              'intensity': m.get('intensity')} for m in council.get('members') or []]
    thread = row.x_thread or []
    safe = (not claims['unverified'] or
            (row.usage or {}).get('scan_synthesis') == synthesis_fingerprint(row))
    synthesis = {'lead': thread[0], 'points': thread[1:]} if thread and safe else None
    return {'families': families, 'techniques': techniques[:6], 'claims': claims, 'sources': len(sources),
            'council': {'models': len(votes), 'agreement': council.get('agreement'), 'votes': votes,
                        'chair': model_label(council.get('chair')), 'escalated': bool(council.get('escalated')),
                        'reviewed': isinstance(council.get('review'), dict)
                                    and isinstance(council['review'].get('ok'), bool)},
            'synthesis': synthesis}

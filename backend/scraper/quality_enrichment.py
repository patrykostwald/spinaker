"""Bounded deterministic quality enrichment. It never deletes or merges articles."""
from hashlib import sha256
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from news.models import (Article, ArticleQualityProfile, ArticleRelation,
                         QualityIssue, SourceQualityState)

RULES_VERSION = 'quality-v1'
TRACKING_KEYS = {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref', 'source'}
SAMPLE_SIZE = 100


def canonicalize_url(value):
    parts = urlsplit(value.strip())
    host = (parts.hostname or '').lower().removeprefix('www.')
    port = parts.port
    netloc = host if port is None or (parts.scheme == 'http' and port == 80) or (parts.scheme == 'https' and port == 443) else f'{host}:{port}'
    path = re.sub('/+', '/', parts.path or '/').rstrip('/') or '/'
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if k.lower() not in TRACKING_KEYS and not k.lower().startswith('utm_')))
    return urlunsplit(((parts.scheme or 'https').lower(), netloc, path, query, ''))


def _digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def _title_key(value):
    return ' '.join(re.findall(r'\w+', value.casefold(), flags=re.UNICODE))


def _profile_values(article):
    canonical = canonicalize_url(article.url)
    content = article.content if hasattr(article, 'content') else None
    content_hash = content.response_sha256 if content else ''
    provenance = {
        'has_source': bool(article.source_id), 'has_url': bool(article.url),
        'has_published_date': article.published_date is not None,
        'has_author': bool(article.author.strip()), 'has_content_record': content is not None,
        'ingestion_method': article.ingestion_method,
        'content_method': content.method if content else '',
    }
    return canonical, {'canonical_url': canonical, 'canonical_sha256': _digest(canonical),
        'title_sha256': _digest(_title_key(article.title)), 'content_sha256': content_hash,
        'provenance': provenance, 'rules_version': RULES_VERSION, 'checked_at': timezone.now()}


def _update_duplicate_flag(article, profile, now):
    matches = list(ArticleQualityProfile.objects.filter(
        article__source_id=article.source_id, canonical_sha256=profile.canonical_sha256
    ).exclude(article_id=article.pk).order_by('article_id').values_list('article_id', flat=True)[:20])
    issue, _ = QualityIssue.objects.get_or_create(article=article, code='canonical_duplicate', defaults={
        'active': bool(matches), 'evidence': {}, 'first_detected': now, 'last_checked': now})
    issue.active = bool(matches); issue.last_checked = now
    if matches:
        issue.evidence = {'other_article_ids': matches, 'canonical_url': profile.canonical_url,
                          'rules_version': RULES_VERSION}
    issue.save(update_fields=['active', 'evidence', 'last_checked'])


def _link_cross_source(article, profile, now):
    candidates = ArticleQualityProfile.objects.filter(
        Q(content_sha256=profile.content_sha256) if profile.content_sha256 else Q(title_sha256=profile.title_sha256),
    ).exclude(article__source_id=article.source_id).exclude(article_id=article.pk).select_related('article')[:20]
    for candidate in candidates:
        same_content = bool(profile.content_sha256 and profile.content_sha256 == candidate.content_sha256)
        if not same_content:
            left_date, right_date = article.published_date, candidate.article.published_date
            if not left_date or not right_date or abs((left_date - right_date).total_seconds()) > 172800:
                continue
        left_id, right_id = sorted((article.pk, candidate.article_id))
        ArticleRelation.objects.update_or_create(left_id=left_id, right_id=right_id,
            relation_type='similar_publication', defaults={'score': '1.0000' if same_content else '0.9000',
            'evidence': {'basis': 'exact_content_sha256' if same_content else 'exact_normalized_title_within_48h',
                         'rules_version': RULES_VERSION}, 'rules_version': RULES_VERSION, 'checked_at': now})


def _refresh_source_state(source_id):
    rows = list(Article.objects.filter(source_id=source_id).select_related('content').order_by('-pk')[:SAMPLE_SIZE])
    total = len(rows)
    def rate(predicate): return round(sum(1 for row in rows if predicate(row)) / total, 4) if total else 0.0
    metrics = {'date_rate': rate(lambda a: a.published_date is not None),
               'author_rate': rate(lambda a: bool(a.author.strip())),
               'content_rate': rate(lambda a: hasattr(a, 'content') and bool(a.content.text)),
               'valid_url_rate': rate(lambda a: bool(urlsplit(a.url).hostname))}
    state, created = SourceQualityState.objects.get_or_create(source_id=source_id, defaults={
        'sample_size': total, 'metrics': metrics, 'baseline_metrics': metrics,
        'drift': {}, 'rules_version': RULES_VERSION})
    baseline = state.baseline_metrics or metrics
    drift = {key: {'baseline': baseline.get(key), 'current': value}
             for key, value in metrics.items() if total >= 20 and baseline.get(key, value) - value >= 0.25}
    if not created:
        state.sample_size = total; state.metrics = metrics; state.drift = drift
        state.rules_version = RULES_VERSION; state.checked_at = timezone.now()
        state.save(update_fields=['sample_size', 'metrics', 'drift', 'rules_version', 'checked_at'])
    return bool(drift)


def enrich_quality(*, limit=200, after_pk=0):
    if not 1 <= limit <= 1000:
        raise ValueError('limit must be 1..1000')
    articles = list(Article.objects.filter(pk__gt=after_pk).select_related('content').order_by('pk')[:limit])
    source_ids = set()
    for article in articles:
        now = timezone.now(); canonical, values = _profile_values(article)
        with transaction.atomic():
            profile, _ = ArticleQualityProfile.objects.update_or_create(article=article, defaults=values)
            _update_duplicate_flag(article, profile, now)
            _link_cross_source(article, profile, now)
        source_ids.add(article.source_id)
    drifted = sum(_refresh_source_state(source_id) for source_id in source_ids)
    return {'status': 'ok', 'checked': len(articles), 'last_pk': articles[-1].pk if articles else after_pk,
            'sources_checked': len(source_ids), 'sources_drifted': drifted, 'rules_version': RULES_VERSION}

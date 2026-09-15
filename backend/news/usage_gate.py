"""Fail-closed use decisions for already stored source material."""

from urllib.parse import urlsplit

from django.utils import timezone

from news.models import SourceUsageDecision


def _host(url):
    return (urlsplit(url or '').hostname or '').lower().removeprefix('www.')


def effective_uses(article):
    """Return allowed uses for one existing article without performing I/O.

    Missing, suspended, expired, malformed, post-cutoff or host-mismatched
    decisions return an empty set.  A fetch instruction cannot authorize a
    post-ingestion use.
    """
    source = getattr(article, 'source', None)
    if source is None:
        return frozenset()
    decision = SourceUsageDecision.objects.filter(source=source).order_by('-version').first()
    if decision is None or decision.status != SourceUsageDecision.Status.APPROVED:
        return frozenset()
    if decision.valid_until and decision.valid_until < timezone.now():
        return frozenset()
    if article.scraped_at > decision.applies_until_acquired_at:
        return frozenset()
    if not decision.frozen_host or decision.frozen_host.casefold() != _host(source.url):
        return frozenset()
    allowed = decision.allowed_uses
    if not isinstance(allowed, list) or any(item not in SourceUsageDecision.Use.values for item in allowed):
        return frozenset()
    return frozenset(allowed)

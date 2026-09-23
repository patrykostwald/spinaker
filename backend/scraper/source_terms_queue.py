"""Shared, read-only queue for reuse-terms discovery across all inactive sources."""

from news.models import ImportState, Source
from scraper.management.commands.source_review_queue import hostname


def terms_discovery_candidates():
    """Return every inactive candidate not already covered by an active host.

    A source with a working RSS or an unknown channel still needs its published
    reuse conditions checked.  Excluding it here would turn a technical audit
    into an unsupported legal conclusion.
    """
    candidates = list(Source.objects.select_related('review_decision').filter(
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    ).order_by('pk'))
    states = dict(ImportState.objects.filter(
        name__in=[f'source-check:{source.pk}' for source in candidates]
    ).values_list('name', 'cursor'))
    active_hosts = {
        hostname(source.url) for source in Source.objects.filter(
            catalog_stage='configured', is_active=True, scrape_enabled=True,
        ) if hostname(source.url)
    }
    return [source for source in candidates if hostname(source.url) not in active_hosts], states

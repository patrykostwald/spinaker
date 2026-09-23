"""One shared definition of sources awaiting later publisher confirmation."""
from news.models import ImportState, Source, SourceReviewDecision
from scraper.management.commands.source_review_queue import hostname, review_bucket


def contact_candidates():
    """Return inactive sources that belong in the later-contact register.

    This is read-only and shared by reports and discovery commands so their
    totals cannot diverge.
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
    rows = []
    for source in candidates:
        if hostname(source.url) in active_hosts:
            continue
        result = states.get(f'source-check:{source.pk}', {}) or {}
        decision = getattr(source, 'review_decision', None)
        requires_contact = decision and decision.decision == SourceReviewDecision.Decision.CONTACT_REQUIRED
        if requires_contact or review_bucket(source, result) == '04_wydawca_lub_organizacja_wymaga_zgody':
            rows.append(source)
    return rows, states

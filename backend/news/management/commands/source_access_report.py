"""Read-only report: which sources are not harvested and why.

Nothing is changed, approved or fetched.  One line per source that has a feed
or a homepage but no working approved access card, so a human can decide the
next step (published re-use terms, publisher consent, or leave excluded).
"""
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand

from news.models import Source

PUBLIC_DOMAINS = ('gov.pl', 'nbp.pl', 'sejm.gov.pl', 'senat.gov.pl', 'nik.gov.pl', 'policja.pl', 'imgw.pl', 'niw.gov.pl',
                  'trybunal.gov.pl', 'sn.pl', 'nsa.gov.pl', 'prezydent.pl', 'uw.edu.pl', 'edu.pl')


def kind(host: str) -> str:
    """Rodzaj nadawcy po domenie: urzędy (gov.pl, BIP, samorządy) albo media i pozostali."""
    public = host.startswith('bip.') or '.bip.' in host or any(host == d or host.endswith('.' + d) for d in PUBLIC_DOMAINS)
    return 'publiczne' if public else 'media/inne'


def latest(source):
    return max(source.access_instructions.all(), key=lambda card: card.version, default=None)


class Command(BaseCommand):
    help = 'Raport (tylko odczyt): źródła bez działającej karty dostępu — id, etap, rodzaj, kanał, stan karty, kontakt, błąd.'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Także źródła wykluczone z katalogu.')
        parser.add_argument('--no-feed', action='store_true', help='Także źródła bez adresu RSS (sama strona).')

    def handle(self, *args, **options):
        sources = Source.objects.prefetch_related('access_instructions', 'contact_cards').order_by('pk')
        if not options['all']:
            sources = sources.exclude(catalog_stage='excluded')
        rows, counts = [], {}
        for source in sources:
            card = latest(source)
            runnable = (card and card.status == 'approved' and card.daily_request_cap > 0 and source.is_active
                        and source.scrape_enabled and source.catalog_stage == 'configured')
            if runnable or not (source.rss_url or (options['no_feed'] and source.url)):
                continue
            host = urlsplit(source.rss_url or source.url).hostname or ''
            contact = next((c.contact_email for c in source.contact_cards.all() if c.contact_email), '')
            state = f'{card.status}/{card.channel}/cap{card.daily_request_cap}' if card else 'brak karty'
            group = kind(host)
            counts[group] = counts.get(group, 0) + 1
            rows.append('|'.join(str(v) for v in (
                source.pk, source.catalog_stage, group, source.name[:60], host, source.rss_url or '-', state,
                contact or '-', (source.last_error or '-')[:60])))
        self.stdout.write('id|etap|rodzaj|nazwa|host|rss|karta|kontakt|błąd')
        self.stdout.write('\n'.join(rows))
        self.stdout.write(f'Razem: {len(rows)} — ' + ', '.join(f'{k}: {v}' for k, v in sorted(counts.items())))

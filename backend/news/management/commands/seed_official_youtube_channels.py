"""Oficjalne kanały YouTube instytucji i partii — każdy z dowodem: strona podmiotu, która sama linkuje kanał.

Lista sprawdzona 27.09.2026 (link do kanału znaleziony w stopce albo danych strony podanej jako dowód).
Komenda ustala niezmienny identyfikator kanału w YouTube Data API (1 jednostka na kanał), a z --apply
zapisuje kanał jako potwierdzony przez wskazanego członka zespołu i włącza pobieranie metadanych filmów.
Pozycje z verified=False (np. strona zablokowana dla automatu) trafiają tylko do przeglądu, bez pobierania.
"""
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news import youtube_collect
from news.models import Source
from news.political_models import OfficialVideoChannel

# (nazwa, link do kanału ze strony-dowodu, strona-dowód, zweryfikowany automatycznie)
CHANNELS = [
    ('Kancelaria Premiera', 'https://www.youtube.com/premierRP', 'https://www.gov.pl/web/premier', True),
    ('Kancelaria Prezydenta RP', 'https://www.youtube.com/user/wwwprezydentpl', 'https://www.prezydent.pl/', True),
    ('Senat RP', 'https://www.youtube.com/channel/UCQN_0-_3vSySNyF4uDa4Zbw', 'https://www.senat.gov.pl/', True),
    # Sejm: stopka sejm.gov.pl sprawdzona ręcznie przez zespół 27.09.2026 (automat widzi CAPTCHA).
    ('Sejm RP', 'https://www.youtube.com/@SejmRP_PL', 'https://www.sejm.gov.pl/', True),
    ('Ministerstwo Obrony Narodowej', 'https://www.youtube.com/user/dpimon', 'https://www.gov.pl/web/obrona-narodowa', True),
    ('Ministerstwo Spraw Zagranicznych', 'https://www.youtube.com/@MinSprawZagranicznych', 'https://www.gov.pl/web/dyplomacja', True),
    ('Ministerstwo Finansów', 'https://www.youtube.com/user/MinisterstwoFinansow', 'https://www.gov.pl/web/finanse', True),
    ('Ministerstwo Zdrowia', 'https://www.youtube.com/channel/UCTZL6hGYpx8VovtxLxhP88A', 'https://www.gov.pl/web/zdrowie', True),
    ('MSWiA', 'https://www.youtube.com/MSWiARP', 'https://www.gov.pl/web/mswia', True),
    ('Ministerstwo Sprawiedliwości', 'https://www.youtube.com/channel/UCf-rbZlITkNVr0piNqADHTQ', 'https://www.gov.pl/web/sprawiedliwosc', True),
    ('Koalicja Obywatelska', 'https://www.youtube.com/@KObywatelska', 'https://koalicjaobywatelska.pl/', True),
    ('Prawo i Sprawiedliwość', 'https://www.youtube.com/user/pisorgpl', 'https://pis.org.pl/', True),
    ('PSL', 'https://www.youtube.com/@nowePSL', 'https://www.psl.pl/', True),
    ('Lewica', 'https://www.youtube.com/user/TVSLD', 'https://lewica.org.pl/', True),
    ('Polska 2050', 'https://www.youtube.com/@Polska2050Oficjalny', 'https://polska2050.pl/', True),
    ('Konfederacja', 'https://www.youtube.com/c/Konfederacja_Oficjalny', 'https://konfederacja.pl/kontakt/', True),
    # Media dodane decyzją zespołu (27.09.2026); strony Onetu blokują automatyczne sprawdzanie.
    ('Onet', 'https://www.youtube.com/@onet', 'https://www.onet.pl/', True),
    ('Stan Wyjątkowy (Onet i „Newsweek”)', 'https://www.youtube.com/@stan_wyjatkowy',
     'https://www.press.pl/tresc/86433,podcast-onetu-i-_newsweeka_-_stan-wyjatkowy_-dwa-razy-w-tygodniu_-_w-kampanii-dzieje-sie-tak-duzo_', True),
]


def lookups(url: str) -> list[dict]:
    """Sposoby ustalenia identyfikatora kanału z linku: /channel/UC…, /@uchwyt, /user/nazwa, /c/nazwa, /nazwa."""
    parts = [part for part in urlsplit(url).path.split('/') if part]
    if not parts:
        return []
    if parts[0] == 'channel':
        return [{'id': parts[1]}]
    if parts[0].startswith('@'):
        return [{'forHandle': parts[0]}]
    name = parts[1] if parts[0] in ('user', 'c') and len(parts) > 1 else parts[0]
    order = [{'forUsername': name}, {'forHandle': '@' + name}] if parts[0] == 'user' else [{'forHandle': '@' + name}, {'forUsername': name}]
    return order


def resolve(url: str) -> tuple[str, str]:
    for params in lookups(url):
        items = youtube_collect.api('channels', part='snippet', **params).get('items') or []
        if items:
            return items[0]['id'], items[0]['snippet'].get('title', '')
    return '', ''


class Command(BaseCommand):
    help = 'Potwierdza oficjalne kanały YouTube z listy (z dowodem) i włącza pobieranie metadanych. Bez --apply: podgląd.'

    def add_arguments(self, parser):
        parser.add_argument('--staff', required=True, help='Login członka zespołu, który potwierdza kanały.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, staff, apply, **options):
        if not youtube_collect.enabled():
            raise CommandError('YouTube wyłączony: ustaw YOUTUBE_ENABLED=true i YOUTUBE_API_KEY.')
        reviewer = get_user_model().objects.filter(username=staff, is_staff=True, is_active=True).first()
        if reviewer is None:
            raise CommandError('Nie ma aktywnego konta zespołu o takim loginie.')
        source_type = ContentType.objects.get_for_model(Source)
        for name, link, evidence, verified in CHANNELS:
            channel_id, title = resolve(link)
            if not channel_id:
                self.stdout.write(f'NIE USTALONO  {name}  {link} — do ręcznego sprawdzenia')
                continue
            label = 'POTWIERDZONY' if verified else 'DO PRZEGLĄDU'
            self.stdout.write(f'{label}  {name}  →  {title}  ({channel_id})  dowód: {evidence}')
            if not apply:
                continue
            channel_url = f'https://www.youtube.com/channel/{channel_id}'
            row = OfficialVideoChannel.objects.filter(channel_id=channel_id).first() or OfficialVideoChannel(channel_id=channel_id)
            row.channel_url, row.display_name, row.evidence_url, row.source_checked_at = channel_url, name, evidence, timezone.now()
            row.subject_content_type = source_type
            # Podmiotem jest źródło kanału (tworzone aktywne dopiero przy potwierdzeniu).
            if verified:
                row.subject_object_id = youtube_collect.channel_source(row).pk
                row.status, row.reviewed_by, row.reviewed_at, row.collection_enabled = 'confirmed', reviewer, timezone.now(), True
            else:
                source, _ = Source.objects.get_or_create(url=channel_url, defaults={
                    'name': name, 'source_type': 'portal', 'scrape_enabled': False, 'is_active': False, 'catalog_stage': 'candidate'})
                row.subject_object_id = source.pk
                row.status, row.collection_enabled = 'pending_review', False
            row.full_clean()
            row.save()
        if not apply:
            self.stdout.write('Podgląd — uruchom z --apply, żeby zapisać.')

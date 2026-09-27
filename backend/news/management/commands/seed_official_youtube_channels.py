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
    # Największe kanały informacyjne i publicystyczne (decyzja zespołu 27.09.2026, identyfikatory sprawdzone w API).
    ('TVN24', 'https://www.youtube.com/channel/UC3R8278fJUWn2ysrOCJrmAQ', 'https://tvn24.pl/', True),
    ('Polsat News', 'https://www.youtube.com/channel/UCb7O4-iI4pEO5UZPlOBr0Ug', 'https://www.polsatnews.pl/', True),
    ('Polsat', 'https://www.youtube.com/channel/UCkNOjcTcgLaNL0-XNoe4gtw', 'https://www.polsat.pl/', True),
    ('TVP Info', 'https://www.youtube.com/channel/UCzQZbOb86WvhOPoR7jgAfsA', 'https://www.tvp.info/', True),
    ('TVP World', 'https://www.youtube.com/channel/UCBjUPsHj7bXt24SUWNoZ0zA', 'https://tvpworld.com/', True),
    ('TV Republika', 'https://www.youtube.com/channel/UCc282c_TN8xIba_Z6GaDnQw', 'https://tvrepublika.pl/', True),
    ('wPolsce24', 'https://www.youtube.com/channel/UCPiu4CZlknkTworskK79CPg', 'https://wpolsce24.tv/', True),
    ('Kanał Zero', 'https://www.youtube.com/channel/UClhEl4bMD8_escGCCTmRAYg', 'https://kanalzero.pl/', True),
    ('Rymanowski Live', 'https://www.youtube.com/channel/UC4uWtFsAryV2p_UDvu0rraA', 'https://www.youtube.com/@RymanowskiLive', True),
    ('RMF24', 'https://www.youtube.com/channel/UCkC9YgH_FlqOhOIoTDFt4CA', 'https://www.rmf24.pl/', True),
    ('RMF FM', 'https://www.youtube.com/channel/UCoiRZbfYK3ztTX4LWuaA3fQ', 'https://www.rmf.fm/', True),
    ('Radio ZET', 'https://www.youtube.com/channel/UCvHFbkohgX29NhaUtmkzLmg', 'https://www.radiozet.pl/', True),
    ('Radio TOK FM', 'https://www.youtube.com/channel/UCUlZzs-r5LDqARiq1xPkQlw', 'https://www.tokfm.pl/', True),
    ('Radio 357', 'https://www.youtube.com/channel/UCPLkBO2r54diEmw0wpJLmiw', 'https://radio357.pl/', True),
    ('Radio Nowy Świat', 'https://www.youtube.com/channel/UCNbblJZzeZUe4sL3tXeN0gQ', 'https://nowyswiat.online/', True),
    ('Wirtualna Polska', 'https://www.youtube.com/channel/UC-wh71MEZ4KAx94aZyoG_qg', 'https://www.wp.pl/', True),
    ('Interia', 'https://www.youtube.com/channel/UC0DpwRtGw4K9tNLnUJqx9qA', 'https://www.interia.pl/', True),
    ('Interia Rozmowy', 'https://www.youtube.com/channel/UCr8b33W30PoW4NhKI-ySRbg', 'https://www.interia.pl/', True),
    ('Gazeta.pl', 'https://www.youtube.com/channel/UCU8ueU3NrJdum0m94TJSdkw', 'https://www.gazeta.pl/', True),
    ('Onet Rano', 'https://www.youtube.com/channel/UCjkNubkfecaFLZbHnnsz6pw', 'https://www.onet.pl/', True),
    ('Rzeczpospolita', 'https://www.youtube.com/channel/UCpchzx2u5Ab8YASeJsR1WIw', 'https://www.rp.pl/', True),
    ('Polska Agencja Prasowa', 'https://www.youtube.com/channel/UClnMSAg4RVYdSLx6098RI-Q', 'https://www.pap.pl/', True),
    ('Super Express', 'https://www.youtube.com/channel/UCJ33TxiuEEYWLZ4ahILb0zQ', 'https://www.se.pl/', True),
    ('Fakt', 'https://www.youtube.com/channel/UCR06R8uZqcwfBOlWf-3OWoA', 'https://www.fakt.pl/', True),
    ('OKO.press', 'https://www.youtube.com/channel/UCgL0f77U3iEPSSU-Mv5yV5g', 'https://oko.press/', True),
    ('Newsweek Polska', 'https://www.youtube.com/channel/UCMvBXVa0KUO-IaeXzUtbuHA', 'https://www.newsweek.pl/', True),
    ('Tygodnik Polityka', 'https://www.youtube.com/channel/UC-et1mpYeABxvgAniUhrrIw', 'https://www.polityka.pl/', True),
    ('Tygodnik Do Rzeczy', 'https://www.youtube.com/channel/UCbG7jYj1nN32cnvhgbOMcZA', 'https://dorzeczy.pl/', True),
    ('Tygodnik Powszechny', 'https://www.youtube.com/channel/UCaimA2iBrOHG0-1nfW3awGQ', 'https://www.tygodnikpowszechny.pl/', True),
    ('Krytyka Polityczna', 'https://www.youtube.com/channel/UCHWB1dvebBlXIHUSuUQSrxQ', 'https://krytykapolityczna.pl/', True),
    ('Business Insider Polska', 'https://www.youtube.com/channel/UCMrYJLhVrZAPZj8pxotN5aA', 'https://businessinsider.com.pl/', True),
    ('Bankier.pl', 'https://www.youtube.com/channel/UCeCGxJV5ECqBQEydmeLmY4w', 'https://www.bankier.pl/', True),
    ('Polskie Radio', 'https://www.youtube.com/channel/UC_jYNCh6rV-wl8KNR3uVooA', 'https://www.polskieradio.pl/', True),
    ('TVP Info Publicystyka', 'https://www.youtube.com/channel/UC4QyTpuQKpBFWbA5mKqLUPA', 'https://www.tvp.info/', True),
    # Autorskie kanały dziennikarzy (decyzja zespołu 27.09.2026).
    ('SEKIELSKI', 'https://www.youtube.com/channel/UCmuaurR3Fl5ugr6Bi066tHA', 'https://www.youtube.com/@sekielski', True),
    ('Kanał Otwarty (Igor Janke)', 'https://www.youtube.com/channel/UCuAOJnMr905iKjURUsffDgA', 'https://ukladotwarty.pl/', True),
    ('Rafał Ziemkiewicz', 'https://www.youtube.com/channel/UCqXzykyeNdMNwiXTvfUOSNQ', 'https://www.youtube.com/@R_A_Ziemkiewicz', True),
    ('Jan Piński', 'https://www.youtube.com/channel/UCaTcgqhFqYzhrLQzaibPyeA', 'https://wiesci24.pl/', True),
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
                channel_source = youtube_collect.channel_source(row)
                if channel_source.name != name:  # na kartach nazwa redakcji, nie domena
                    channel_source.name = name[:255]
                    channel_source.save(update_fields=['name'])
                row.subject_object_id = channel_source.pk
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

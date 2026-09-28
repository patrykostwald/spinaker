"""Source groups shown to readers: Publiczne, Media, Top media.

One definition for the API (``portal_group`` on every serialized source), the
home page filters and the daily summary (``/api/feed/?mode=top``):

* ``top`` — the editorial list of leading national news brands below: the
  widest reach, a mix of formats (portals, TV, radio, the national agency and
  a daily) and both sides of the political spectrum on television;
* ``publiczne`` — public institutions (ministries, BIP, parliament, courts,
  registries), i.e. ``source_type == institution``;
* ``media`` — every other publisher.

Membership in ``TOP_MEDIA`` is matched by the exact catalog name of the feed
source, so renaming a source requires updating this list.
"""
from news.models import SourceType

TOP_MEDIA = (
    # portale
    'Onet Wiadomości', 'Wirtualna Polska', 'Interia', 'Gazeta.pl',
    # telewizja
    'TVN24', 'Polsat News', 'TVP Info', 'TV Republika',
    # radio
    'RMF24', 'Radio ZET',
    # agencja i dziennik
    'pap.pl', 'Rzeczpospolita',
)


# Oficjalne kanały YouTube wiodących mediów (identyfikator → nazwa z TOP_MEDIA), sprawdzone 27.09.2026.
# Kanał należy do „top” tylko przez ten wpis — nigdy przez podobną nazwę (kanał „TV Republika” bez wpisu nie przejmie sekcji).
TOP_MEDIA_CHANNELS = {
    'UC_vMDcmkuEvw0N-gaP35wTA': 'Onet Wiadomości',   # Onet
    'UC-wh71MEZ4KAx94aZyoG_qg': 'Wirtualna Polska',  # Wirtualna Polska News
    'UC0DpwRtGw4K9tNLnUJqx9qA': 'Interia',           # INTERIA
    'UCU8ueU3NrJdum0m94TJSdkw': 'Gazeta.pl',
    'UC3R8278fJUWn2ysrOCJrmAQ': 'TVN24',
    'UCb7O4-iI4pEO5UZPlOBr0Ug': 'Polsat News',       # polsatnews.pl
    'UCzQZbOb86WvhOPoR7jgAfsA': 'TVP Info',
    'UCc282c_TN8xIba_Z6GaDnQw': 'TV Republika',      # Telewizja Republika
    'UCkC9YgH_FlqOhOIoTDFt4CA': 'RMF24',
    'UCvHFbkohgX29NhaUtmkzLmg': 'Radio ZET',
    'UClnMSAg4RVYdSLx6098RI-Q': 'pap.pl',            # Polska Agencja Prasowa
    'UCpchzx2u5Ab8YASeJsR1WIw': 'Rzeczpospolita',
}
YOUTUBE_CHANNEL = 'https://www.youtube.com/channel/'


def top_channel_id(source) -> str:
    url = source.url or ''
    return url[len(YOUTUBE_CHANNEL):].strip('/') if url.startswith(YOUTUBE_CHANNEL) else ''


def portal_group(source):
    if top_channel_id(source) in TOP_MEDIA_CHANNELS:
        return 'top'
    # Strona wydawcy z listy top (kanał YouTube — tylko przez TOP_MEDIA_CHANNELS, nie po nazwie).
    if source.name in TOP_MEDIA and 'youtube.com' not in (source.url or ''):
        return 'top'
    if source.source_type == SourceType.INSTITUTION:
        return 'publiczne'
    return 'media'

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


def portal_group(source):
    if source.name in TOP_MEDIA:
        return 'top'
    if source.source_type == SourceType.INSTITUTION:
        return 'publiczne'
    return 'media'

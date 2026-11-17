"""Podmioty z doniesień medialnych przy osobie publicznej (6.11.2026, decyzja właściciela).

Pokazujemy: kategorię doniesienia, podmiot z naszej bazy (KRS) i źródło (link, tytuł, redakcja, data, krótki cytat).
Nie opisujemy charakteru powiązania. Wzmianka w mediach nie jest dowodem powiązania. Tylko pozycje opublikowane po przeglądzie
zespołu (status „published”); dopasowanie po numerze KRS/NIP albo oznaczone jako niepotwierdzone (tylko nazwa).
"""
from django.db.models import Q

from news import krs
from news.political_models import MEDIA_MENTION_CATEGORIES, PublicFigureMediaMention

NOTICE = ('Wzmianka w mediach nie jest dowodem powiązania. Pokazujemy, gdzie i w jakim kontekście podmiot został wymieniony '
          'obok tej osoby, bez oceny, czy relacja istnieje. Błąd zgłosisz na stronie „Poprawki”.')
LABELS = dict(MEDIA_MENTION_CATEGORIES)
ORDER = [key for key, _ in MEDIA_MENTION_CATEGORIES]


def official_extract_url(org):
    """Bezpośredni link do urzędowego odpisu aktualnego tego podmiotu (API KRS MS); bez rejestru P/S w danych: ogólna wyszukiwarka."""
    if org.register in ('P', 'S'):
        return krs.API.format(kind='OdpisAktualny', krs=org.krs_number) + f'?rejestr={org.register}&format=json'
    return org.official_register_url


def mentions_for(figure, limit=100):
    rows = list(PublicFigureMediaMention.objects.filter(public_figure=figure, status='published').filter(Q(organisation__isnull=True) | Q(organisation__archived=False))
                .select_related('organisation').order_by('-published_on', '-pk')[:limit])
    rows.sort(key=lambda m: ORDER.index(m.category) if m.category in ORDER else len(ORDER))
    def entity(m):
        if m.organisation_id is None:      # podmiot bez KRS: nazwa, identyfikator i link do właściwego rejestru (bez strony spółki i bez rejestr.io)
            return {'name': m.entity_name, 'krs_number': '', 'kind': 'other', 'url': '', 'register_url': m.entity_register_url, 'extra_url': '',
                    'identifier': m.entity_identifier, 'no_krs': True}
        org = m.organisation
        return {'name': org.name, 'krs_number': org.krs_number, 'kind': org.kind, 'url': f'/przeszlosc/spolka/{org.krs_number}',
                'register_url': official_extract_url(org), 'extra_url': krs.extra_register_url(org.krs_number), 'identifier': '', 'no_krs': False}
    results = [{
        'id': m.pk, 'category': m.category, 'category_label': LABELS.get(m.category, m.category),
        'organisation': entity(m),
        'unconfirmed': m.match_basis == 'name_only',
        'source': {'url': m.source_url, 'title': m.source_title, 'outlet': m.source_outlet,
                   'date': m.published_on.isoformat() if m.published_on else None},
        'quote': m.quote,
    } for m in rows]
    return {'count': len(results), 'notice': NOTICE, 'results': results,
            'by_category': {key: sum(1 for r in results if r['category'] == key) for key in ORDER}}

"""Podmioty z doniesień medialnych przy osobie publicznej (6.11.2026, decyzja właściciela).

Pokazujemy: kategorię doniesienia, podmiot z naszej bazy (KRS) i źródło (link, tytuł, redakcja, data, krótki cytat).
Nie opisujemy charakteru powiązania. Wzmianka w mediach nie jest dowodem powiązania. Tylko pozycje opublikowane po przeglądzie
zespołu (status „published”); dopasowanie po numerze KRS/NIP albo oznaczone jako niepotwierdzone (tylko nazwa).
"""
from news.political_models import MEDIA_MENTION_CATEGORIES, PublicFigureMediaMention

NOTICE = ('Wzmianka w mediach nie jest dowodem powiązania. Pokazujemy, gdzie i w jakim kontekście podmiot został wymieniony '
          'obok tej osoby, bez oceny, czy relacja istnieje. Błąd zgłosisz na stronie „Poprawki”.')
LABELS = dict(MEDIA_MENTION_CATEGORIES)
ORDER = [key for key, _ in MEDIA_MENTION_CATEGORIES]


def mentions_for(figure, limit=100):
    rows = list(PublicFigureMediaMention.objects.filter(public_figure=figure, status='published', organisation__archived=False)
                .select_related('organisation').order_by('-published_on', '-pk')[:limit])
    rows.sort(key=lambda m: ORDER.index(m.category) if m.category in ORDER else len(ORDER))
    results = [{
        'id': m.pk, 'category': m.category, 'category_label': LABELS.get(m.category, m.category),
        'organisation': {'name': m.organisation.name, 'krs_number': m.organisation.krs_number, 'kind': m.organisation.kind,
                         'url': f'/przeszlosc/spolka/{m.organisation.krs_number}', 'register_url': m.organisation.official_register_url},
        'unconfirmed': m.match_basis == 'name_only',
        'source': {'url': m.source_url, 'title': m.source_title, 'outlet': m.source_outlet,
                   'date': m.published_on.isoformat() if m.published_on else None},
        'quote': m.quote,
    } for m in rows]
    return {'count': len(results), 'notice': NOTICE, 'results': results,
            'by_category': {key: sum(1 for r in results if r['category'] == key) for key in ORDER}}

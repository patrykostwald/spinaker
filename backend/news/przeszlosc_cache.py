"""Cache i rozgrzewanie przeszłość.today (Śledczy R1, P1-9: p95 poniżej 2 s dla /osoba/ i /temat/).

Zasada: ten sam ładunek dla każdego czytelnika (bez danych użytkownika w kluczu), dostęp i wzmianki dokładane
w widoku. Gorący zbiór (tematy dnia, kandydaci na tematy, osoby z tych tematów) jest przeliczany co godzinę
w tle, wszyscy posłowie raz w nocy po imporcie; wpis z cache żyje dłużej niż odstęp między rozgrzewaniami,
więc zimny odczyt zdarza się tylko dla tematu, którego nikt wcześniej nie liczył.
Cache działa na Postgresie (produkcja); w testach na SQLite każdy odczyt liczy od nowa (PRZESZLOSC_CACHE wymusza).
"""
import os
import time

import django.db
from django.core.cache import cache

TOPIC_SECONDS = 2 * 3600         # temat wpisany przez czytelnika
TOPIC_HOT_SECONDS = 3 * 3600     # temat z gorącego zbioru, odświeżany co godzinę
TOPIC_EMPTY_SECONDS = 3600       # pusty wynik też kosztuje pełne skany (Śledczy: 11 s dla „xqzw”)
VOTES_SECONDS = 3600
PROFILE_SECONDS = 3 * 3600
PROFILE_HOT_SECONDS = 4 * 3600
WARM_BUDGET_SECONDS = 20 * 60
TOPIC_KEY = 'przeszlosc:temat:v3:'
VOTES_KEY = 'przeszlosc:glosowania:v1:'
PROFILE_KEY = 'przeszlosc:osoba:v2:'  # ten sam klucz i kształt ładunku co dotąd w person_view (testy wzmianek na nim polegają)
LAST_WARM_KEY = 'przeszlosc:rozgrzewanie:ostatnie'


def active():
    """PRZESZLOSC_CACHE=always|never nadpisuje domyślną regułę (Postgres tak, SQLite nie)."""
    forced = os.environ.get('PRZESZLOSC_CACHE', '').lower()
    if forced in ('always', '1', 'true'):
        return True
    if forced in ('never', '0', 'false'):
        return False
    return django.db.connection.vendor == 'postgresql'  # odczyt w chwili wywołania (testy podmieniają django.db.connection)


def normalized(query):
    return ' '.join((query or '').lower().split())


def topic_key(query):
    return TOPIC_KEY + normalized(query)


def person_key(figure):
    return f'{PROFILE_KEY}{figure.pk}'


def topic_payload(query):
    """Pełny ładunek /temat/: graf, pierwsza strona głosowań z liczbą wszystkich i zakresem dat, dotacje UE, krawędzie głosów."""
    from news.przeszlosc import eu_funds, link_votes, topic_graph, topic_votes_page
    data = topic_graph(query)
    page = topic_votes_page(query)
    data['votes'] = page['results']
    data['votes_total'] = page['total']
    data['votes_range'] = page['range']
    data['eu_funds'] = eu_funds(query)
    link_votes(data)
    if page['total']:
        data['counts']['vote'] = page['total']
    return data


def is_empty(data):
    return not data.get('nodes') and not data.get('votes')


def cached_topic(query, seconds=None):
    if not active():
        return topic_payload(query)
    key = topic_key(query)
    data = cache.get(key)
    if data is None:
        data = topic_payload(query)
        cache.set(key, data, seconds or (TOPIC_EMPTY_SECONDS if is_empty(data) else TOPIC_SECONDS))
    return data


def cached_topic_votes(query, page, per_page, since, until):
    from news.przeszlosc import topic_votes_page
    if not active():
        return topic_votes_page(query, page, per_page, since, until)
    key = f'{VOTES_KEY}{normalized(query)}:{page}:{per_page}:{since or ""}:{until or ""}'
    data = cache.get(key)
    if data is None:
        data = topic_votes_page(query, page, per_page, since, until)
        cache.set(key, data, VOTES_SECONDS)
    return data


def person_payload(figure):
    """Profil bez wzmianek i bez dostępu: wzmianki (media_mentions) i uprawnienia dokłada widok przy każdym żądaniu."""
    from news.przeszlosc_osoba import denominators, profile
    data = profile(figure, include_mentions=False)
    data['denominators'] = denominators(figure)
    return data


def cached_person(figure, seconds=None):
    if not active():
        return person_payload(figure)
    key = person_key(figure)
    data = cache.get(key)
    if data is None:
        data = person_payload(figure)
        cache.set(key, data, seconds or PROFILE_SECONDS)
    return data


def forget_person(figure):
    cache.delete(person_key(figure))


# --- rozgrzewanie w tle ---
def hot_topics(limit=24):
    """Tematy dnia i kandydaci z ostatnich dni (ta sama lista, którą pokazuje strona główna) - bez zapytań czytelników."""
    from news.przeszlosc import auto_topics, candidates
    pool = [t['topic'] for t in auto_topics()] + candidates()
    return list(dict.fromkeys(t for t in pool if t))[:limit]


def hot_people(topics, limit=60):
    """Osoby z historii tematów dnia (remember_topics) dla gorących tematów."""
    from news.political_models import PublicFigure
    from news.przeszlosc_osoba import topic_history
    wanted = {normalized(t) for t in topics}
    ids = []
    for row in topic_history():
        if normalized(row['topic']) in wanted:
            ids.extend(row['people'])
    ids = list(dict.fromkeys(ids))[:limit]
    return list(PublicFigure.objects.filter(pk__in=ids, archived=False, merged_into__isnull=True))


def all_mps():
    """Wszyscy posłowie z mandatem (oficjalny identyfikator Sejmu) - rozgrzewani raz w nocy."""
    from news.political_models import PublicFigure
    return list(PublicFigure.objects.filter(archived=False, merged_into__isnull=True, parliamentary_roster_entry__source='sejm')
                .select_related('parliamentary_roster_entry').order_by('pk'))


def warm(scope='hot', budget_seconds=WARM_BUDGET_SECONDS, now=time.monotonic):
    """Przelicza i zapisuje ładunki: scope='hot' (tematy dnia + ich osoby, co godzinę) albo 'all' (dodatkowo wszyscy
    posłowie, w nocy). Mieści się w budżecie czasu; to, czego nie zdążył, zostaje na następny raz.
    Zwraca statystyki do raportu pętli."""
    started = now()
    stats = {'scope': scope, 'topics': 0, 'people': 0, 'skipped': 0, 'errors': 0}
    if not active():
        stats['disabled'] = True
        return stats
    topics = hot_topics()
    people = hot_people(topics)
    if scope == 'all':
        seen = {f.pk for f in people}
        people += [f for f in all_mps() if f.pk not in seen]
    for query in topics:
        if now() - started > budget_seconds:
            stats['skipped'] += 1
            continue
        try:
            cache.set(topic_key(query), topic_payload(query), TOPIC_HOT_SECONDS)
            stats['topics'] += 1
        except Exception:  # noqa: BLE001 - jeden zły temat nie zatrzymuje rozgrzewania
            stats['errors'] += 1
    for figure in people:
        if now() - started > budget_seconds:
            stats['skipped'] += 1
            continue
        try:
            cache.set(person_key(figure), person_payload(figure), PROFILE_HOT_SECONDS)
            stats['people'] += 1
        except Exception:  # noqa: BLE001
            stats['errors'] += 1
    stats['seconds'] = round(now() - started, 1)
    cache.set(LAST_WARM_KEY, stats, 24 * 3600)
    return stats

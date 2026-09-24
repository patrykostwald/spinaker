"""Editorial topic vocabulary matches exact publisher tags, never headline guesses."""
TOPICS = {
    'polityka': ('Polityka', ('polityka', 'polityka krajowa', 'polityka zagraniczna')),
    'polska': ('Polska', ('polska', 'kraj', 'wiadomości krajowe')),
    'swiat': ('Świat', ('świat', 'wiadomości ze świata', 'zagranica')),
    'zdrowie': ('Zdrowie', ('zdrowie', 'medycyna')),
    'dom': ('Dom', ('dom', 'dom i ogród', 'wnętrza')),
    'dziecko': ('Dziecko', ('dziecko', 'dzieci', 'rodzicielstwo')),
    'gry': ('Gry', ('gry', 'gry komputerowe', 'gry wideo')),
    'biznes': ('Biznes', ('biznes', 'gospodarka', 'ekonomia', 'finanse')),
    'technologia': ('Technologia', ('technologia', 'technologie', 'nowe technologie')),
    'sport': ('Sport', ('sport',)),
    'kultura': ('Kultura', ('kultura', 'kultura i sztuka')),
    'nauka': ('Nauka', ('nauka',)),
    'motoryzacja': ('Motoryzacja', ('motoryzacja',)),
}


def topic_choices():
    return [{'value': key, 'label': value[0]} for key, value in TOPICS.items()]


def topic_clause(values):
    # JSON index transforms decode both escaped SQLite JSON and PostgreSQL JSON.
    # Publisher tags are capped at 12 at ingestion. Match entire tags, not parts
    # such as 'sport' inside 'transport'. SQLite regex provides Unicode casefold.
    import re
    from django.db import connection
    from django.db.models import Q
    aliases = {tag for key in values for tag in TOPICS[key][1]}
    clause = Q(pk__in=[])
    for index in range(12):
        if connection.vendor == 'sqlite':
            pattern = '^(?:' + '|'.join(re.escape(tag) for tag in sorted(aliases)) + ')$'
            clause |= Q(**{f'tags__{index}__iregex': pattern})
        else:
            for alias in aliases:
                clause |= Q(**{f'tags__{index}__iexact': alias})
    return clause

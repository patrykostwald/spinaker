"""Pomiar szybkości API przeszłość.today (P1-9) na syntetycznej kopii danych w SQLite, bez sieci i bez produkcji.

Użycie (z katalogu repo, dowolne drzewo robocze):
  python scripts/przeszlosc_bench.py --db C:/tmp/bench.sqlite3 --seed          # raz: tworzy bazę i dane
  python scripts/przeszlosc_bench.py --db C:/tmp/bench.sqlite3 --runs 10 --out przed.json
Te same dane i ten sam skrypt uruchomione na dwu gałęziach dają porównanie „przed / po”.
Rozmiary są mniejsze niż produkcja (525 tys. artykułów), więc liczą się proporcje, nie wartości bezwzględne.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

# BENCH_ROOT wskazuje inne drzewo robocze (np. gałąź bazową), żeby zmierzyć „przed” tym samym skryptem.
ROOT = Path(os.environ.get('BENCH_ROOT') or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / 'backend'))

TOPIC_WORDS = ['VAT', 'CPK', 'Turów', 'energia', 'KPO', 'budżet', 'szpital', 'kolej', 'podatek', 'obrona']
FILLER = ('rząd sejm komisja projekt ustawa debata minister poseł głosowanie samorząd gmina powiat województwo '
          'inwestycja program fundusz raport kontrola wniosek odpowiedź pytanie spotkanie konferencja oświadczenie').split()


def setup(db_path):
    os.environ['USE_SQLITE'] = 'true'
    os.environ['SQLITE_DATABASE_PATH'] = str(db_path)
    os.environ['PRZESZLOSC_ENABLED'] = 'true'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    os.environ.setdefault('SECRET_KEY', 'bench-only')
    import django
    django.setup()
    from django.test.utils import setup_test_environment
    setup_test_environment()


def sentence(rng, topic=None):
    words = rng.sample(FILLER, 6)
    if topic:
        words.insert(rng.randrange(len(words)), topic)
    return ' '.join(words).capitalize() + '.'


def seed(sizes, rng):
    from django.core.management import call_command
    from django.utils import timezone
    from news.models import Article, Ballot, ParliamentaryVoting, Source
    from news.political_models import (ParliamentaryRosterEntry, PoliticalAccount, PoliticalPost, PublicFigure,
                                       PublicFigureOrganisationRelation, RegisteredOrganisation)
    from news.public_records_models import PublicRecord, PublicRecordPerson
    call_command('migrate', verbosity=0)
    now = timezone.now()
    source = Source.objects.create(name='Redakcja', url='https://media.example')
    sejm = Source.objects.create(name='Sejm', url='https://api.sejm.gov.pl')
    print('artykuły...', flush=True)
    Article.objects.bulk_create([
        Article(source=source, title=sentence(rng, rng.choice(TOPIC_WORDS) if rng.random() < .03 else None),
                description=sentence(rng, rng.choice(TOPIC_WORDS) if rng.random() < .03 else None),
                url=f'https://media.example/a/{i}', published_date=now - timedelta(minutes=i))
        for i in range(sizes['articles'])], batch_size=5000)
    print('posłowie...', flush=True)
    clubs = ['KO', 'PiS', 'PSL', 'Polska2050', 'Lewica', 'Konfederacja']
    figures = []
    for mp_id in range(1, sizes['mps'] + 1):
        entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id=str(mp_id), full_name=f'Poseł {mp_id} Nazwisko{mp_id}',
                                                        term=10, source_url='https://api.sejm.gov.pl/sejm/term10/MP')
        figures.append(PublicFigure.objects.create(canonical_name=f'Poseł{mp_id} Nazwisko{mp_id}', role_category='parliamentary',
                                                   role_title='Poseł na Sejm RP', evidence_url='https://sejm.gov.pl',
                                                   parliamentary_roster_entry=entry))
    print('wpisy...', flush=True)
    accounts = [PoliticalAccount.objects.create(user_id=str(1000 + i), handle=f'konto{i}', display_name=f'Konto {i}',
                                                camp=rng.choice(['government', 'opposition'])) for i in range(60)]
    PoliticalPost.objects.bulk_create([
        PoliticalPost(account=rng.choice(accounts), post_id=str(i), url=f'https://x.com/k/status/{i}',
                      text=sentence(rng, rng.choice(TOPIC_WORDS) if rng.random() < .05 else None) + ' ' + sentence(rng),
                      published_at=now - timedelta(minutes=3 * i), camp_at_collection='government')
        for i in range(sizes['posts'])], batch_size=5000)
    print('dokumenty Sejmu...', flush=True)
    records = PublicRecord.objects.bulk_create([
        PublicRecord(source='sejm', kind=rng.choice(['print', 'interpellations', 'statement', 'committee_sitting']),
                     external_id=f'10/{i}', source_url=f'https://api.sejm.gov.pl/r/{i}', response_sha256='b' * 64,
                     response_url='https://api.sejm.gov.pl', term=10, date=(now - timedelta(days=i % 700)).date(),
                     title=sentence(rng, rng.choice(TOPIC_WORDS) if rng.random() < .04 else None),
                     text=' '.join(sentence(rng) for _ in range(40)))
        for i in range(sizes['records'])], batch_size=2000)
    PublicRecordPerson.objects.bulk_create([
        PublicRecordPerson(record=r, term=10, mp_id=rng.randrange(1, sizes['mps'] + 1), figure=None)
        for r in records if rng.random() < .3], batch_size=5000)
    print('głosowania...', flush=True)
    for n in range(sizes['votings']):
        topic = rng.choice(TOPIC_WORDS) if rng.random() < .1 else None
        article = Article.objects.create(source=sejm, title=f'Pkt {n}. {sentence(rng, topic)}', url=f'https://sejm.example/v/{n}',
                                         published_date=now - timedelta(hours=6 * n))
        voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=1 + n // 20, number=1 + n % 20,
                                                    motion=sentence(rng, topic), kind='ELECTRONIC', counts={'yes': 230, 'no': 200})
        Ballot.objects.bulk_create([
            Ballot(voting=voting, mp_id=mp_id, name=f'Poseł {mp_id} Nazwisko{mp_id}', club=clubs[mp_id % len(clubs)],
                   vote=rng.choice(['YES', 'YES', 'NO', 'NO', 'ABSTAIN', 'ABSENT']))
            for mp_id in range(1, sizes['mps'] + 1)], batch_size=2000)
    print('KRS...', flush=True)
    for i in range(sizes['orgs']):
        org = RegisteredOrganisation.objects.create(name=f'Spółka {i} {rng.choice(TOPIC_WORDS)}', krs_number=f'{i:010d}', nip=f'{5260250000 + i}')
        PublicFigureOrganisationRelation.objects.create(public_figure=figures[i % len(figures)], organisation=org,
                                                        verification_status='confirmed', organ='zarząd')
    from news.models import ImportState
    from news.przeszlosc import TOPICS_STATE
    state, _ = ImportState.objects.get_or_create(name=TOPICS_STATE)
    state.cursor = {'at': now.isoformat(), 'topics': [{'topic': t, 'edges': 10, 'score': 50, 'counts': {}} for t in TOPIC_WORDS[:6]]}
    state.save(update_fields=['cursor'])
    print('gotowe:', {k: v for k, v in sizes.items()}, 'ballots', Ballot.objects.count())


def measure(urls, runs, cold):
    from django.core.cache import cache
    from django.test import Client
    client = Client()
    out = {}
    for label, url in urls:
        times = []
        for _ in range(runs):
            if cold:
                cache.clear()
            start = time.perf_counter()
            response = client.get(url)
            times.append(time.perf_counter() - start)
            assert response.status_code == 200, (url, response.status_code, response.content[:200])
        times.sort()
        out[label] = {'median': round(statistics.median(times), 3), 'p95': round(times[max(0, int(len(times) * .95) - 1)], 3),
                      'min': round(times[0], 3), 'runs': runs}
        print(f'{label:<28} {"zimno" if cold else "ciepło"}  mediana {out[label]["median"]:.2f} s  p95 {out[label]["p95"]:.2f} s', flush=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--seed', action='store_true')
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--out')
    parser.add_argument('--articles', type=int, default=60000)
    parser.add_argument('--posts', type=int, default=15000)
    parser.add_argument('--records', type=int, default=20000)
    parser.add_argument('--votings', type=int, default=800)
    parser.add_argument('--mps', type=int, default=460)
    parser.add_argument('--orgs', type=int, default=200)
    args = parser.parse_args()
    setup(Path(args.db))
    rng = random.Random(7)
    if args.seed:
        seed({k: getattr(args, k) for k in ('articles', 'posts', 'records', 'votings', 'mps', 'orgs')}, rng)
        return
    from news.political_models import PublicFigure
    figure = PublicFigure.objects.filter(parliamentary_roster_entry__external_id='1').first()
    urls = [('temat VAT', '/api/przeszlosc/temat/?q=VAT'), ('temat Turów', '/api/przeszlosc/temat/?q=Turów'),
            ('temat pusty (xqzw)', '/api/przeszlosc/temat/?q=xqzw'),
            ('osoba (poseł)', f'/api/przeszlosc/osoba/{figure.pk}/'),
            ('przeplyw osoba', f'/api/przeszlosc/przeplyw/osoba:{figure.pk}/')]
    result = {'cold': measure(urls, args.runs, cold=True), 'warm': measure(urls, max(3, args.runs // 2), cold=False)}
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    main()

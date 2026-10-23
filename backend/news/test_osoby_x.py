import csv

import pytest
from django.core.management import call_command

from news import osoby_x
from news.political_models import ParliamentaryRosterEntry, PublicFigure, SocialHandleEvidence


JAKUBIAK = 'parliamentary:sejm:139'
# Konta w testach to dane przykładowe dla atrapy Wikidata, nie twierdzenie o prawdziwym koncie.
HANDLE = 'KontoTestowe1'


class Response:
    def __init__(self, bindings):
        self.bindings = bindings

    def raise_for_status(self):
        pass

    def json(self):
        return {'results': {'bindings': self.bindings}}


def uri(value):
    return {'type': 'uri', 'value': value}


def literal(value):
    return {'type': 'literal', 'value': value}


def binding(qid, handle=None, label='', pl=True, pos=True, ep='', url='', end='', rank='NormalRank'):
    row = {'item': uri(f'http://www.wikidata.org/entity/{qid}'), 'label': literal(label),
           'pl': literal(str(pl).lower()), 'pos': literal(str(pos).lower()), 'party': literal('false')}
    if handle:
        row.update(x=literal(handle), rank=uri(f'http://wikiba.se/ontology#{rank}'))
    if ep:
        row['ep'] = literal(ep)
    if url:
        row['url'] = uri(url)
    if end:
        row['end'] = literal(end)
    return row


def fake_wikidata(names=(), ep=(), sejm=()):
    def post(url, data, **kwargs):
        assert url == osoby_x.WIKIDATA
        query = data['query']
        if 'P1186' in query:
            return Response(list(ep))
        if 'P973' in query:
            return Response(list(sejm))
        return Response([row for row in names if f'"{row["label"]["value"]}"@pl' in query])
    return post


def jakubiak_people():
    return [p for p in osoby_x.people_from_repo() if p.osoba_id == JAKUBIAK]


def test_jakubiak_is_in_repo_people():
    people = jakubiak_people()
    assert [p.name for p in people] == ['Marek Jakubiak']
    assert any('X kadencja (obecnie)' in role for role in people[0].roles)


def test_jakubiak_gets_account_from_wikidata_by_name():
    post = fake_wikidata(names=[binding('Q1', HANDLE, label='Marek Jakubiak')])
    rows, ambiguous = osoby_x.collect(jakubiak_people(), post=post, today='2026-10-23', pause=0)
    assert ambiguous == []
    assert rows == [{
        'imie_nazwisko': 'Marek Jakubiak', 'osoba_id': JAKUBIAK, 'konto': HANDLE,
        'zrodlo': 'https://www.wikidata.org/wiki/Q1', 'data_sprawdzenia': '2026-10-23', 'pewnosc': 'wysoka',
        'stan_konta': 'aktualne',
        'uwagi': 'Wikidata P2002; dopasowanie: imię i nazwisko (jedyny polityk z obywatelstwem PL o tym nazwisku w Wikidata)',
    }]


def test_name_match_ignores_polish_letters_and_case():
    assert osoby_x.fold('Marek JAKUBIAK') == osoby_x.fold('marek jakubiak')
    assert osoby_x.fold('Władysław Kosiniak-Kamysz') == osoby_x.fold('Wladyslaw Kosiniak Kamysz')
    assert osoby_x.display_name('Janusz LEWANDOWSKI') == 'Janusz Lewandowski'
    person = osoby_x.Person('parliamentary:sejm:1', 'Żaneta ŁĄCKA')
    post = fake_wikidata(names=[binding('Q2', HANDLE, label='Żaneta Łącka')])
    rows, _ = osoby_x.collect([person], post=post, pause=0)
    assert [row['osoba_id'] for row in rows] == ['parliamentary:sejm:1']


def test_namesake_without_politics_is_ignored_but_two_politicians_are_ambiguous():
    person = jakubiak_people()[0]
    namesake = binding('Q9', None, label='Marek Jakubiak', pl=True, pos=False)
    rows, _ = osoby_x.collect([person], post=fake_wikidata(names=[binding('Q1', HANDLE, label='Marek Jakubiak'), namesake]), pause=0)
    assert len(rows) == 1
    twins = [binding('Q1', HANDLE, label='Marek Jakubiak'), binding('Q3', 'InneKonto', label='Marek Jakubiak')]
    rows, ambiguous = osoby_x.collect([person], post=fake_wikidata(names=twins), pause=0)
    assert rows == []
    assert ambiguous == [(person, ['Q1', 'Q3'])]


def test_former_and_deprecated_accounts_are_marked_not_dropped():
    names = [binding('Q1', 'StareKonto', label='Marek Jakubiak', end='2020-01-01T00:00:00Z'),
             binding('Q1', 'Zawieszone', label='Marek Jakubiak', rank='DeprecatedRank'),
             binding('Q1', HANDLE, label='Marek Jakubiak')]
    rows, _ = osoby_x.collect(jakubiak_people(), post=fake_wikidata(names=names), pause=0)
    assert {row['konto']: row['stan_konta'] for row in rows} == {
        'StareKonto': 'byłe', 'Zawieszone': 'byłe', HANDLE: 'aktualne'}


def test_exact_ep_and_sejm_ids_win_over_names():
    mep = osoby_x.Person('parliamentary:ep:23781', 'Janusz Lewandowski')
    mp = osoby_x.Person(JAKUBIAK, 'Marek Jakubiak')
    post = fake_wikidata(ep=[binding('Q5', 'KontoPE', ep='23781')],
                         sejm=[binding('Q6', HANDLE, url='https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id=139&type=A')])
    rows, _ = osoby_x.collect([mep, mp], post=post, pause=0)
    assert {(row['osoba_id'], row['konto'], row['pewnosc']) for row in rows} == {
        ('parliamentary:ep:23781', 'KontoPE', 'wysoka'), (JAKUBIAK, HANDLE, 'wysoka')}


def test_merge_keeps_official_rows_and_refreshes_wikidata():
    official = {'osoba_id': 'a', 'konto': 'A', 'zrodlo': 'https://www.gov.pl/web/a'}
    stale = {'osoba_id': 'b', 'konto': 'B', 'zrodlo': 'https://www.wikidata.org/wiki/Q1'}
    fresh = {'osoba_id': 'b', 'konto': 'C', 'zrodlo': 'https://www.wikidata.org/wiki/Q1'}
    assert osoby_x.merge([official, stale], [fresh]) == [official, fresh]


def test_coverage_lists_jakubiak_until_he_has_an_account():
    people = jakubiak_people()
    assert osoby_x.coverage(people, [])['braki'] == people
    row = {'osoba_id': JAKUBIAK, 'konto': HANDLE, 'stan_konta': 'aktualne'}
    assert osoby_x.coverage(people, [row])['z_kontem'] == 1
    assert osoby_x.coverage(people, [dict(row, stan_konta='byłe')])['bez_konta'] == 1


def test_repo_csv_has_a_source_for_every_account():
    rows = osoby_x.read_rows()
    assert rows
    keys = set()
    for row in rows:
        assert list(row) == osoby_x.FIELDS
        assert row['zrodlo'].startswith('https://')
        assert osoby_x.HANDLE.fullmatch(row['konto'])
        assert row['pewnosc'] in ('wysoka', 'średnia') and row['stan_konta'] in ('aktualne', 'byłe')
        assert (row['osoba_id'], row['konto'].casefold()) not in keys
        keys.add((row['osoba_id'], row['konto'].casefold()))


def write_osoby_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=osoby_x.FIELDS)
        writer.writeheader()
        writer.writerows({name: row.get(name, '') for name in osoby_x.FIELDS} for row in rows)


def jakubiak_row(**changes):
    row = {'imie_nazwisko': 'Marek Jakubiak', 'osoba_id': JAKUBIAK, 'konto': HANDLE,
           'zrodlo': 'https://www.wikidata.org/wiki/Q1', 'data_sprawdzenia': '2026-10-23', 'pewnosc': 'wysoka',
           'stan_konta': 'aktualne'}
    row.update(changes)
    return row


@pytest.mark.django_db
def test_import_links_jakubiak_by_exact_key_and_is_idempotent(tmp_path):
    figure = PublicFigure.objects.create(canonical_name='Marek Jakubiak', role_category='parliament',
        role_title='Poseł na Sejm RP', import_key=JAKUBIAK, evidence_url='https://api.sejm.gov.pl/sejm/term10/MP/139')
    PublicFigure.objects.create(canonical_name='Marek Jakubiak', role_category='government',
        role_title='Inna osoba o tym samym nazwisku', evidence_url='https://other.example/mj')
    path = tmp_path / 'osoby_x.csv'
    write_osoby_csv(path, [jakubiak_row(), jakubiak_row(konto='StareKonto', stan_konta='byłe'),
                           jakubiak_row(konto='Niepewne', pewnosc='średnia')])

    call_command('import_public_figure_x_csv', str(path), apply=True)
    call_command('import_public_figure_x_csv', str(path), apply=True)

    evidence = SocialHandleEvidence.objects.get()
    assert (evidence.subject, evidence.handle, evidence.status) == (figure, HANDLE, 'pending_review')
    assert evidence.evidence_url == 'https://www.wikidata.org/wiki/Q1'
    assert evidence.extracted_url == f'https://x.com/{HANDLE}'


@pytest.mark.django_db
def test_import_skips_account_already_stored_for_the_mandate(tmp_path):
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='139', full_name='Marek Jakubiak',
        source_url='https://api.sejm.gov.pl/sejm/term10/MP/139')
    PublicFigure.objects.create(canonical_name='Marek Jakubiak', role_category='parliament', role_title='Poseł',
        import_key=JAKUBIAK, evidence_url='https://api.sejm.gov.pl/sejm/term10/MP/139', parliamentary_roster_entry=entry)
    SocialHandleEvidence.objects.create(roster_entry=entry, handle=HANDLE.lower(),
        evidence_url='https://www.wikidata.org/wiki/Q1', extracted_url=f'https://x.com/{HANDLE.lower()}')
    path = tmp_path / 'osoby_x.csv'
    write_osoby_csv(path, [jakubiak_row()])

    call_command('import_public_figure_x_csv', str(path), apply=True)

    assert SocialHandleEvidence.objects.count() == 1


@pytest.mark.django_db
def test_pokrycie_command_reports_repo_data(capsys):
    call_command('osoby_x_pokrycie', repo=True)
    out = capsys.readouterr().out
    assert 'Osoby publiczne (repo):' in out
    assert 'Marek Jakubiak · parliamentary:sejm:139' in out

"""Sprint 1 przeszłość.today: profil osoby, wyszukiwanie, Wspólne mianowniki, dopinanie dokumentów Sejmu."""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news.clinic_models import SpinDiagnosis
from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import (ParliamentaryRosterEntry, PoliticalAccount, PoliticalAccountCandidate, PoliticalPost,
                                   PublicFigure, PublicFigureOrganisationRelation, PublicFigureRole, RegisteredOrganisation,
                                   SocialHandleEvidence)
from news.przeszlosc_osoba import denominators, fold, mp_identities, profile, remember_topics, resolve, search, slug
from news.public_records_models import PublicRecord, PublicRecordPerson

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def mp(name, mp_id, term=10):
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id=str(mp_id), full_name=name, term=term,
                                                    source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    return PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł na Sejm RP',
                                       evidence_url='https://sejm.gov.pl', parliamentary_roster_entry=entry)


def x_account(figure, handle, user_id):
    staff, _ = get_user_model().objects.get_or_create(username='redaktor', defaults={'is_staff': True})
    candidate = PoliticalAccountCandidate.objects.create(handle=handle, display_name=figure.canonical_name, classification='independent',
                                                         confirmation_url='https://sejm.gov.pl', confirmation_note='Link z profilu.')
    account = PoliticalAccount.objects.create(user_id=user_id, handle=handle, display_name=figure.canonical_name, camp='government',
                                              confirmation_url='https://sejm.gov.pl', confirmation_note='Potwierdzone.')
    account.confirm(staff)
    candidate.resolved_account = account
    candidate.save(update_fields=['resolved_account'])
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk,
                                        handle=handle, evidence_url='https://sejm.gov.pl/profil', extracted_url=f'https://x.com/{handle}',
                                        candidate=candidate, status='candidate_created')
    return account


def x_post(account, key, text, days_ago=1):
    return PoliticalPost.objects.create(account=account, post_id=key, url=f'https://x.com/{account.handle}/status/{key}', text=text,
                                        published_at=timezone.now() - timedelta(days=days_ago), response_sha256='a' * 64,
                                        camp_at_collection=account.camp)


def record(n, title, people, kind='interpellations'):
    r = PublicRecord.objects.create(source=kind, kind=kind, external_id=f'10/{n}', source_url=f'https://api.sejm.gov.pl/sejm/term10/{kind}/{n}',
                                    response_sha256='b' * 64, response_url='https://api.sejm.gov.pl', term=10, date=date(2026, 9, 1 + n),
                                    title=title, data={'replies': [{'key': 'x'}]})
    for mp_id, figure in people:
        PublicRecordPerson.objects.create(record=r, term=10, mp_id=mp_id, figure=figure)
    return r


def voting(n, ballots):
    source, _ = Source.objects.get_or_create(url='https://api.sejm.gov.pl', defaults={'name': 'Sejm'})
    article = Article.objects.create(source=source, title=f'Głosowanie {n}: ustawa o VAT', url=f'https://sejm.example/v{n}',
                                     published_date=timezone.now() - timedelta(days=n))
    v = ParliamentaryVoting.objects.create(article=article, term=10, sitting=40, number=n, motion='całość projektu', kind='ELECTRONIC')
    for mp_id, name, club, vote in ballots:
        Ballot.objects.create(voting=v, mp_id=mp_id, name=name, club=club, vote=vote)
    return v


def test_fold_and_fuzzy_search_without_diacritics_and_with_typo():
    target = mp('Łukasz Śliwiński', 101)
    mp('Anna Kowalska', 102)
    PublicFigure.objects.create(canonical_name='Łukasz Archiwalny', role_category='political', role_title='x', evidence_url='https://e.pl', archived=True)
    assert fold('Łukasz Śliwiński') == 'lukasz sliwinski'
    assert [r['id'] for r in search('lukasz sliwinski')] == [target.pk]
    assert search('sliwisnki')[0]['id'] == target.pk  # literówka
    assert search('ŚLIW')[0]['slug'] == f'{target.pk}-lukasz-sliwinski'
    assert all(r['name'] != 'Łukasz Archiwalny' for r in search('lukasz'))
    assert search('ab') == []


def test_people_endpoint_gated_and_validated(monkeypatch):
    mp('Anna Kowalska', 102)
    client = APIClient()
    assert client.get('/api/przeszlosc/osoby/?q=kowalska').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/osoby/?q=ko').status_code == 400
    assert client.get('/api/przeszlosc/osoby/?q=kowalska').json()['results'][0]['name'] == 'Anna Kowalska'


def test_resolve_slug_and_merged_profile():
    target = mp('Jan Nowak', 103)
    old = PublicFigure.objects.create(canonical_name='Jan Nowak (stary)', role_category='government', role_title='Minister',
                                      evidence_url='https://gov.pl', archived=True, merged_into=target)
    assert resolve(slug(target)) == target and resolve(str(target.pk)) == target
    assert resolve(f'{old.pk}-jan-nowak') == target
    assert resolve('kowalski') is None and resolve('999999') is None


def build_world():
    me = mp('Anna Kowalska', 77)
    PublicFigureRole.objects.create(public_figure=me, role_category='parliamentary', role_title='Posłanka X kadencji', evidence_url='https://sejm.gov.pl',
                                    import_key='sejm-term:10:77', since=date(2023, 11, 13), party='KO')
    co = mp('Piotr Wspólny', 78)
    rival = mp('Ewa Przeciwna', 79)
    account = x_account(me, 'AnnaKowalska', '7001')
    p1 = x_post(account, '9001', 'CPK ruszy w terminie, obiecuję.')
    x_post(account, '9002', 'Spotkanie z wyborcami.', days_ago=3)
    SpinDiagnosis.objects.create(post=p1, status='approved', verdict='spin', intensity=72, headline='Obietnica bez pokrycia',
                                 diagnosed_at=timezone.now())
    record(1, 'Interpelacja w sprawie CPK', [(77, None), (78, co)])  # osoba dopięta po oficjalnym id, bez figure
    record(2, 'Zapytanie o ceny energii', [(77, me)], kind='questions')
    for n in range(1, 4):
        voting(n, [(77, 'Anna Kowalska', 'KO', 'YES'), (78, 'Piotr Wspólny', 'KO', 'YES'), (79, 'Ewa Przeciwna', 'PiS', 'NO'),
                   (80, 'Marek Bezprofilu', 'PSL', 'YES')])
    org = RegisteredOrganisation.objects.create(name='Fundacja Jawna', krs_number='0000123456', kind='foundation', official_register_url='https://prs.example/1')
    for f, role in ((me, 'członkini zarządu'), (rival, 'członkini rady')):
        rel = PublicFigureOrganisationRelation(public_figure=f, organisation=org, public_role=role, organ=role.split()[-1],
                                               evidence_url='https://prs.example/1')
        rel.confirm_automatically('krs_register')
        rel.save()
    return me, co, rival


def test_profile_has_all_sections():
    me, co, rival = build_world()
    assert mp_identities(me) == [(10, 77)]
    data = profile(me)
    assert data['slug'] == f'{me.pk}-anna-kowalska'
    assert data['x_accounts'][0]['handle'] == 'AnnaKowalska'
    assert data['posts']['count'] == 2 and data['posts']['diagnoses'] == 1 and data['posts']['avg_spin'] == 72
    assert data['posts']['results'][0]['diagnosis']['intensity'] == 72
    assert data['documents']['count'] == 2 and {d['label'] for d in data['documents']['results']} == {'Interpelacja', 'Zapytanie poselskie'}
    assert data['documents']['results'][0]['replies'] == 1
    assert data['votes']['count'] == 3 and data['votes']['summary'] == {'za': 3} and 'NrGlosowania=' in data['votes']['results'][0]['url']
    assert data['organisations'][0]['krs_number'] == '0000123456' and 'nie dowód' in data['krs_note']
    assert len(data['activity']) == 12 and sum(m['posts'] for m in data['activity']) == 2 and sum(m['votes'] for m in data['activity']) == 3


def test_profile_of_non_mp_has_no_votes_and_no_private_inference():
    minister = PublicFigure.objects.create(canonical_name='Ministra Publiczna', role_category='government', role_title='Ministra',
                                           evidence_url='https://gov.pl')
    voting(1, [(5, 'Ministra Publiczna', 'KO', 'YES')])  # to samo nazwisko w głosowaniu nie łączy osoby
    data = profile(minister)
    assert data['votes']['available'] is False and data['votes']['count'] == 0 and data['documents']['count'] == 0


def test_denominators_co_authors_krs_and_vote_alignment():
    me, co, rival = build_world()
    remember_topics([{'topic': 'CPK', 'people': [me.pk, co.pk]}, {'topic': 'VAT', 'people': [co.pk]}])
    d = denominators(me)
    people = d['people']
    assert people[0]['id'] == co.pk and people[0]['shared'] == {'dokument': 1, 'temat': 1}
    assert {e['kind'] for e in people[0]['evidence']} == {'dokument', 'temat'}
    assert d['krs'][0]['id'] == rival.pk and 'KRS 0000123456' in d['krs'][0]['evidence'][0]['label']
    votes = d['votes']
    assert votes['available'] and votes['window'] == 3 and votes['club'] == 'KO'
    by_name = {r['name']: r for r in votes['aligned']}
    assert by_name['Piotr Wspólny']['pct'] == 100 and by_name['Piotr Wspólny']['id'] == co.pk
    assert by_name['Ewa Przeciwna']['pct'] == 0
    assert by_name['Marek Bezprofilu']['id'] is None  # poseł bez profilu: tylko nazwa z oficjalnej listy
    assert [r['name'] for r in votes['cross_club']][:1] == ['Marek Bezprofilu']
    assert len(by_name['Piotr Wspólny']['evidence']) == 3 and 'sejm.gov.pl' in by_name['Piotr Wspólny']['evidence'][0]['url']
    assert profile(me)['topics'] == [{'topic': 'CPK', 'at': timezone.localdate().isoformat()}]


def test_person_endpoint_json_csv_and_404(monkeypatch):
    me, _, _ = build_world()
    client = APIClient()
    assert client.get(f'/api/przeszlosc/osoba/{me.pk}/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    data = client.get(f'/api/przeszlosc/osoba/{slug(me)}/').json()
    assert data['name'] == 'Anna Kowalska' and data['denominators']['votes']['available']
    r = client.get(f'/api/przeszlosc/osoba/{me.pk}/?eksport=csv')
    body = r.content.decode('utf-8-sig')
    assert r['Content-Type'].startswith('text/csv') and 'attachment' in r['Content-Disposition']
    assert 'wpis na X' in body and 'Interpelacja' in body and 'głosowanie: za' in body and 'kontekst, nie dowód' in body
    assert 'attachment' in client.get(f'/api/przeszlosc/osoba/{me.pk}/?eksport=json')['Content-Disposition']
    assert client.get('/api/przeszlosc/osoba/999999-nikt/').status_code == 404


def test_link_public_record_people_is_idempotent():
    r = record(5, 'Interpelacja', [(90, None)])
    call_command('link_public_record_people')
    assert PublicRecordPerson.objects.get(record=r).figure is None
    later = mp('Nowy Poseł', 90)
    call_command('link_public_record_people')
    assert PublicRecordPerson.objects.get(record=r).figure == later
    from news.public_record_people import link_people
    assert link_people()['linked'] == 0


def test_unlinked_is_state_with_reasons_not_a_regression():
    """Wdrożenie 6.10: {"checked": 12, "linked": 0, "unlinked": 198} - unlinked to stan, nie odpięte w przebiegu."""
    from io import StringIO
    from news.public_record_people import link_people
    record(1, 'Interpelacja byłego posła', [(70, None)])          # wygasły mandat: lista Sejmu ma tylko aktywnych
    ParliamentaryRosterEntry.objects.create(source='sejm', external_id='71', full_name='Bez Profilu', term=10,
                                            source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    record(2, 'Interpelacja posła bez profilu', [(71, None)])     # mandat jest, profil niepołączony (ręczna kontrola)
    linked = mp('Jest Profil', 72)
    record(3, 'Interpelacja', [(72, None)])
    result = link_people()
    assert result['linked'] == 1 and result['cleared'] == 0 and result['unlinked'] == 2
    assert result['why_unlinked'] == {'not_in_roster': 1, 'roster_without_profile': 1, 'ambiguous': 0}
    assert PublicRecordPerson.objects.get(mp_id=72).figure == linked
    out = StringIO()
    call_command('link_public_record_people', stdout=out)
    assert 'stan, nie odpięte teraz' in out.getvalue() and '1 spoza listy mandatów' in out.getvalue()


def committee(code, name, members):
    r = PublicRecord.objects.create(source='committees', kind='committee', external_id=f'10/{code}', term=10, title=name,
                                    source_url=f'https://api.sejm.gov.pl/sejm/term10/committees/{code}', response_sha256='c' * 64,
                                    response_url='https://api.sejm.gov.pl', data={'code': code, 'name': name, 'members': members})
    for m in members:
        PublicRecordPerson.objects.create(record=r, term=10, mp_id=m['id'])
    return r


def test_profile_lists_committees_by_name_and_never_raw_kind_keys(monkeypatch):
    """Właściciel 7.10 (profil posła): „W Sejmie: committee: 3” i „[object Object]” w podtytule."""
    from news.przeszlosc_osoba import DOCUMENT_LABEL, RECORD_LABEL
    me = mp('Michał Testowy', 44)
    committee('ASW', 'Komisja Administracji i Spraw Wewnętrznych', [{'id': 44, 'function': 'zastępca przewodniczącego', 'joinDate': '2023-11-21'}, {'id': 9}])
    committee('ENM', 'Komisja do Spraw Energii', [{'id': 44}])
    committee('OBN', 'Komisja Obrony Narodowej', [{'id': 44, 'function': 'przewodniczący'}])
    committee('CNT', 'Komisja do Spraw Kontroli Państwowej', [{'id': 44, 'leaveDate': '2024-06-01'}])  # dawny skład
    record(1, 'Interpelacja w sprawie testu', [(44, None)])
    PublicRecord.objects.create(source='consultations', kind='osr_document', external_id='x1', term=10, title='OSR',
                                source_url='https://api.sejm.gov.pl/sejm/term10/prints/1/a.pdf', response_sha256='d' * 64,
                                response_url='https://api.sejm.gov.pl').people.create(term=10, mp_id=44)
    data = profile(me)
    assert [(c['name'], c['role']) for c in data['committees']] == [
        ('Komisja Obrony Narodowej', 'przewodniczący'), ('Komisja Administracji i Spraw Wewnętrznych', 'zastępca przewodniczącego'),
        ('Komisja do Spraw Energii', 'członek')]
    assert data['committees'][0]['url'].endswith('KodKom=OBN') and data['committees'][1]['since'] == '2023-11-21'
    labels = set(RECORD_LABEL.values()) | {DOCUMENT_LABEL}
    assert set(data['documents']['by_kind']) <= labels and 'committee' not in str(data['documents']['by_kind'])
    assert data['documents']['count'] == 2  # komisja to funkcja, nie dokument
    party = data.get('party')
    assert party is None or isinstance(party, dict) and party['name']  # strona pokazuje name (ui.tsx: text), nie obiekt


def test_pick_topics_remembers_people(monkeypatch):
    from news import przeszlosc
    from news.przeszlosc_osoba import topic_history
    graph = {'edges': [1, 2, 3], 'counts': {'person': 1, 'statement': 2, 'diagnosis': 1}, 'nodes': [{'id': 'figure:5'}, {'id': 'post:1'}]}
    monkeypatch.setattr(przeszlosc, 'candidates', lambda: ['CPK'])
    monkeypatch.setattr(przeszlosc, 'topic_graph', lambda q: graph)
    przeszlosc.pick_topics()
    assert topic_history()[0]['topic'] == 'CPK' and topic_history()[0]['people'] == [5]


def test_beat_plan_has_sprint_tasks():
    from news.daily_schedule import BEAT_PLAN
    from news import tasks
    assert BEAT_PLAN['przeszlosc-alerts-daily'] == ('przeszlosc_alerts_task', {'hour': 7, 'minute': 0})
    assert BEAT_PLAN['public-record-people-nightly'][0] == 'public_record_people_task'
    assert callable(tasks.przeszlosc_alerts_task) and callable(tasks.public_record_people_task)


def test_spin_trace_free_slice_votes_vs_club_documents_and_cta(monkeypatch):
    me, co, rival = build_world()
    # Głosowanie, w którym posłanka głosuje inaczej niż większość klubu, i drugie - z remisem w klubie.
    voting(0, [(77, 'Anna Kowalska', 'KO', 'NO'), (78, 'Piotr Wspólny', 'KO', 'YES'), (81, 'Inny Klubowy', 'KO', 'YES')])
    client = APIClient()
    data = client.get(f'/api/public-figures/{me.pk}/slad/').json()
    assert data['available'] and len(data['votes']) == 4
    newest = data['votes'][0]
    assert newest['vote'] == 'przeciw' and newest['club_vote'] == 'za' and newest['relation'] == 'inaczej niż klub'
    assert data['votes'][1]['relation'] == 'zgodnie z klubem' and 'NrGlosowania=' in data['votes'][1]['url']
    assert [d['label'] for d in data['documents']] == ['Zapytanie poselskie', 'Interpelacja'] and data['documents'][0]['answered'] is True
    assert data['year'] == {'votes': 4, 'documents': 2}
    # Płatne funkcje przeszłość.today nie trafiają do spin.clinic; link tylko gdy przeszłość jest włączona.
    assert data['full_profile'] is None and 'organisations' not in data and 'denominators' not in data
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    monkeypatch.setenv('PRZESZLOSC_DOMAIN', 'przeszlosc.today')
    full = client.get(f'/api/public-figures/{me.pk}/slad/').json()['full_profile']
    assert full['url'] == f'https://przeszlosc.today/przeszlosc/osoba/{slug(me)}' and 'Wspólne mianowniki' in full['features']
    assert client.get('/api/public-figures/999999/slad/').status_code == 404


def test_spin_trace_never_matches_by_name():
    minister = PublicFigure.objects.create(canonical_name='Ministra Publiczna', role_category='government', role_title='Ministra',
                                           evidence_url='https://gov.pl')
    voting(1, [(5, 'Ministra Publiczna', 'KO', 'YES')])
    data = APIClient().get(f'/api/public-figures/{minister.pk}/slad/').json()
    assert data['available'] is False and data['votes'] == [] and data['documents'] == [] and data['year'] == {'votes': 0, 'documents': 0}


def test_display_name_normalizes_uppercase_surnames():
    from news.przeszlosc_osoba import display_name
    assert display_name('Daniel OBAJTEK') == 'Daniel Obajtek'
    assert display_name('Anna NOWAK-KOWALSKA') == 'Anna Nowak-Kowalska'
    assert display_name('Jan Kowalski') == 'Jan Kowalski' and display_name('Jan DA') == 'Jan DA' and display_name('') == ''

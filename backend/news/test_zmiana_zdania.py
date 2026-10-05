"""Zmiana zdania: kandydaci bez AI, ta sama miara dla każdej partii, brak modelu nie blokuje, tylko konta potwierdzone podwójnie;
KRS na spin.clinic tylko jako nazwy funkcji."""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import zmiana_zdania as zz
from news.agents_common import WindowClosed
from news.clinic_models import PositionCheck, PositionScan, SpinDiagnosis
from news.models import Article, Ballot, ParliamentaryVoting, Source
from news.political_models import (ParliamentaryRosterEntry, PoliticalAccount, PoliticalAccountCandidate, PoliticalPost, PublicFigure,
                                   PublicFigureOrganisationRelation, RegisteredOrganisation, SocialHandleEvidence)
from news.public_records_models import PublicRecord, PublicRecordPerson

pytestmark = pytest.mark.django_db
NOW_TEXT = 'Podatek VAT na żywność trzeba obniżyć do zera, rodziny płacą za dużo w sklepach. Obniżka VAT na żywność od stycznia!'
THEN_TEXT = 'Obniżka podatku VAT na żywność to zły pomysł, budżet tego nie udźwignie, rodziny nie odczują różnicy w sklepach.'


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def staff():
    user, _ = get_user_model().objects.get_or_create(username='redaktor', defaults={'is_staff': True})
    return user


def figure(name, mp_id=None):
    entry = None
    if mp_id:
        entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id=str(mp_id), full_name=name, term=10,
                                                        source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    return PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł na Sejm RP',
                                       evidence_url='https://sejm.gov.pl', parliamentary_roster_entry=entry)


def account(person, handle, user_id, camp='government', confirmed=True):
    candidate = PoliticalAccountCandidate.objects.create(handle=handle, display_name=person.canonical_name, classification='independent',
                                                         confirmation_url='https://sejm.gov.pl')
    acc = PoliticalAccount.objects.create(user_id=user_id, handle=handle, display_name=person.canonical_name, camp=camp,
                                          confirmation_url='https://sejm.gov.pl', confirmation_note='Potwierdzone.')
    if confirmed:
        acc.confirm(staff())
    candidate.resolved_account = acc
    candidate.save(update_fields=['resolved_account'])
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=person.pk,
                                        handle=handle, evidence_url='https://sejm.gov.pl/profil', extracted_url=f'https://x.com/{handle}',
                                        candidate=candidate, status='candidate_created')
    return acc


def post(acc, key, text, days_ago):
    return PoliticalPost.objects.create(account=acc, post_id=key, url=f'https://x.com/{acc.handle}/status/{key}', text=text,
                                        published_at=timezone.now() - timedelta(days=days_ago), response_sha256='a' * 64,
                                        camp_at_collection=acc.camp)


def diagnose(p):
    return SpinDiagnosis.objects.create(post=p, status='approved', verdict='spin', intensity=60, headline='Nagłówek', summary='Streszczenie.',
                                        analysis='Analiza.', diagnosed_at=timezone.now())


def answer(relation='zmiana stanowiska', confidence=90, now='trzeba obniżyć do zera', then='to zły pomysł, budżet tego nie udźwignie'):
    return {'relation': relation, 'confidence': confidence, 'explanation': 'Wcześniej osoba sprzeciwiała się obniżce, teraz ją popiera',
            'quote_now': now, 'quote_then': then}


def test_retrieval_needs_gap_topic_and_confirmed_accounts():
    person = figure('Jan Testowy')
    main = account(person, 'jan_test', '101')
    second = account(person, 'jan_test2', '102')            # drugie potwierdzone konto tej samej osoby
    loose = account(person, 'jan_loose', '103', confirmed=False)  # dowód jest, konto niepotwierdzone przez redaktora
    stranger = account(figure('Ktoś Inny'), 'inny', '104')
    d = diagnose(post(main, '1', NOW_TEXT, 1))
    old = post(second, '2', THEN_TEXT, 40)
    post(main, '3', THEN_TEXT, 5)                      # za blisko (mniej niż 14 dni)
    post(main, '4', 'Dziś byłem na meczu reprezentacji, świetna atmosfera na stadionie.', 60)  # inny temat
    post(loose, '5', THEN_TEXT, 50)
    post(stranger, '6', THEN_TEXT, 50)                 # inna osoba
    found = zz.candidates(d)
    assert [c['source_key'] for c in found] == [f'post:{old.pk}']
    assert found[0]['similarity'] >= zz.MIN_SIMILARITY


def test_unconfirmed_diagnosed_account_gets_no_candidates():
    person = figure('Anna Luźna')
    loose = account(person, 'anna_l', '201', confirmed=False)
    d = diagnose(post(loose, '1', NOW_TEXT, 1))
    post(loose, '2', THEN_TEXT, 40)
    assert zz.candidates(d) == []


def test_statements_and_votes_by_official_mp_id_only():
    person = figure('Ewa Posłanka', mp_id=77)
    acc = account(person, 'ewa_p', '301')
    d = diagnose(post(acc, '1', NOW_TEXT, 1))
    rec = PublicRecord.objects.create(source='statement', kind='statement', external_id='10/1', source_url='https://sejm.gov.pl/st/1',
                                      response_sha256='b' * 64, response_url='https://sejm.gov.pl', term=10,
                                      date=timezone.localdate() - timedelta(days=90), title='Wystąpienie o podatku VAT na żywność',
                                      text=THEN_TEXT)
    PublicRecordPerson.objects.create(record=rec, term=10, mp_id=77, figure=None)
    other = PublicRecord.objects.create(source='statement', kind='statement', external_id='10/2', source_url='https://sejm.gov.pl/st/2',
                                        response_sha256='b' * 64, response_url='https://sejm.gov.pl', term=10,
                                        date=timezone.localdate() - timedelta(days=90), title='Inny poseł o VAT', text=THEN_TEXT)
    PublicRecordPerson.objects.create(record=other, term=10, mp_id=78)  # inny identyfikator, choćby nazwisko było to samo
    source, _ = Source.objects.get_or_create(url='https://api.sejm.gov.pl', defaults={'name': 'Sejm'})
    article = Article.objects.create(source=source, title='Głosowanie: obniżka podatku VAT na żywność', url='https://sejm.example/v1',
                                     published_date=timezone.now() - timedelta(days=120))
    voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=40, number=1, motion='całość projektu', kind='ELECTRONIC')
    ballot = Ballot.objects.create(voting=voting, mp_id=77, name='Ewa Posłanka', club='KO', vote='NO')
    Ballot.objects.create(voting=voting, mp_id=78, name='Ewa Posłanka', club='PiS', vote='YES')
    keys = {c['source_key']: c for c in zz.candidates(d)}
    assert set(keys) == {f'record:{rec.pk}', f'ballot:{ballot.pk}'}
    assert keys[f'ballot:{ballot.pk}']['earlier_text'].startswith('głosował(a) przeciw')


def mirrored():
    gov, opp = figure('Adam Rządowy'), figure('Olga Opozycyjna')
    pairs = []
    for person, handle, uid, camp in ((gov, 'adam_r', '401', 'government'), (opp, 'olga_o', '402', 'opposition')):
        acc = account(person, handle, uid, camp)
        d = diagnose(post(acc, uid + '1', NOW_TEXT, 1))
        post(acc, uid + '2', THEN_TEXT, 40)
        pairs.append(d)
    return pairs


def test_same_measure_for_both_camps(monkeypatch):
    gov, opp = mirrored()
    monkeypatch.setattr(zz, 'ask', lambda payload: (answer(), 'groq:test'))
    result = zz.run()
    assert result['scanned'] == 2 and result['checked'] == 2
    a, b = zz.public_data(gov), zz.public_data(opp)
    assert a and b and len(a['items']) == len(b['items']) == 1
    strip = lambda block: [{k: v for k, v in item.items() if k not in ('url', 'now_url', 'title')} for item in block['items']]
    assert strip(a) == strip(b)
    assert a['note'] == zz.NOTE
    # ten sam próg: pewność tuż pod progiem ukrywa parę po obu stronach
    PositionCheck.objects.update(confidence=zz.MIN_CONFIDENCE - 1)
    assert zz.public_data(gov) is None and zz.public_data(opp) is None


def test_model_unavailable_leaves_pending_and_never_blocks(monkeypatch):
    gov, _ = mirrored()

    def closed(payload):
        raise WindowClosed('brak wolnego modelu')
    monkeypatch.setattr(zz, 'ask', closed)
    result = zz.run()
    assert result['status'] == 'waiting' and result['checked'] == 0
    assert PositionScan.objects.count() == 2
    assert set(PositionCheck.objects.values_list('relation', flat=True)) == {'pending'}
    assert PositionCheck.objects.filter(attempts=0).count() == 2  # próba bez modelu nie zużywa limitu prób
    assert zz.public_data(gov) is None
    response = APIClient().get(f'/api/clinic/spins/{gov.pk}/')
    assert response.status_code == 200 and response.json()['position_changes'] is None


def test_ask_without_free_models_raises_window_closed(monkeypatch):
    import news.clinic_council as council
    monkeypatch.setattr(council, '_members', lambda name, default: [])
    with pytest.raises(WindowClosed):
        zz.ask({'x': 1})


def test_invented_quote_or_loaded_word_is_not_shown(monkeypatch):
    gov, opp = mirrored()
    monkeypatch.setattr(zz, 'ask', lambda payload: (answer(then='tego zdania nie było we wpisie wcale'), 'groq:test'))
    zz.run()
    assert set(PositionCheck.objects.values_list('relation', flat=True)) == {'unclear'}
    check = PositionCheck.objects.first()
    zz.judge(check, {**answer(), 'explanation': 'To hipokryzja polityka.'}, 'groq:test')
    assert check.relation == 'unclear'


def test_detail_api_and_social_line(monkeypatch):
    gov, _ = mirrored()
    monkeypatch.setattr(zz, 'ask', lambda payload: (answer(), 'groq:test'))
    zz.run()
    data = APIClient().get(f'/api/clinic/spins/{gov.pk}/').json()
    block = data['position_changes']
    assert block['items'][0]['quote_then'] == 'to zły pomysł, budżet tego nie udźwignie'
    assert block['items'][0]['kind_label'] == 'Wpis na X'
    line = zz.social_line(data)
    assert line.startswith('Zmiana zdania:') and '\n' not in line
    assert zz.social_line({'position_changes': None}) == ''


def test_deleted_earlier_post_hides_item(monkeypatch):
    gov, _ = mirrored()
    monkeypatch.setattr(zz, 'ask', lambda payload: (answer(), 'groq:test'))
    zz.run()
    PoliticalPost.objects.filter(post_id='4012').update(available=False)
    assert zz.public_data(gov) is None


def test_spin_profile_shows_only_krs_function_names(monkeypatch):
    person = figure('Piotr Rada')
    org = RegisteredOrganisation.objects.create(name='Spółka X S.A.', krs_number='0000123456', kind='company', sector='state',
                                                official_register_url='https://wyszukiwarka-krs.ms.gov.pl/0000123456')
    PublicFigureOrganisationRelation.objects.create(public_figure=person, organisation=org, public_role='członek rady nadzorczej',
                                                    organ='rada nadzorcza', evidence_url='https://krs.example', since=date(2020, 1, 1),
                                                    until=date(2022, 1, 1), relation_status='former', verification_status='confirmed',
                                                    verification_method='krs_register', sources=[{'url': 'https://krs.example'}])
    monkeypatch.delenv('PRZESZLOSC_ENABLED', raising=False)
    data = APIClient().get(f'/api/public-figures/{person.pk}/').json()
    assert data['organisations'] == [{'id': org.pk, 'name': 'Spółka X S.A.', 'kind': 'company', 'sector': 'state',
                                      'public_role': 'członek rady nadzorczej', 'organ': 'rada nadzorcza', 'relation_status': 'former'}]
    assert '0000123456' not in str(data) and '2020-01-01' not in str(data)
    assert data['krs_full_profile'] is None
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    data = APIClient().get(f'/api/public-figures/{person.pk}/').json()
    assert data['krs_full_profile']['url'].endswith(f'/przeszlosc/osoba/{person.pk}-piotr-rada')
    # przeszłość.today zachowuje pełne dane
    from news.przeszlosc_osoba import profile
    full = profile(person)
    assert full['organisations'][0]['krs_number'] == '0000123456' and str(full['organisations'][0]['since']) == '2020-01-01'

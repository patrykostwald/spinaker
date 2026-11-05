"""„Wcześniej i teraz” (v3): walidator, brak wycieku kandydatów, flaga, cisza wyborcza, zgłoszenia, powiadomienia,
ta sama miara dla każdej strony. Bez sieci i bez modeli (odpowiedzi podstawione)."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from news import position_pairs as pp
from news.clinic_models import PositionCheck, PositionPair, SpinDiagnosis
from news.models import Ballot
from news.notification_models import Follow, Notification
from news.test_przeszlosc_osoba import mp, voting, x_account, x_post

pytestmark = pytest.mark.django_db

OLD = 'Nie podniesiemy podatku od nieruchomości w tej kadencji, to obietnica dla wszystkich właścicieli mieszkań.'
NEW = 'Podatek od nieruchomości musi wzrosnąć, bo gminy potrzebują pieniędzy na drogi i szkoły.'


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    cache.clear()
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    yield
    cache.clear()


def x_account_in(figure, handle, user_id, camp):
    """Jak test_przeszlosc_osoba.x_account, ale z obozem ustalonym przed potwierdzeniem konta (potwierdzenie obejmuje obóz)."""
    from django.contrib.contenttypes.models import ContentType
    from news.political_models import PoliticalAccount, PoliticalAccountCandidate, PublicFigure, SocialHandleEvidence
    if camp == 'government':
        return x_account(figure, handle, user_id)
    editor, _ = get_user_model().objects.get_or_create(username='redaktor', defaults={'is_staff': True})
    found = PoliticalAccountCandidate.objects.create(handle=handle, display_name=figure.canonical_name, classification='independent',
                                                     confirmation_url='https://sejm.gov.pl', confirmation_note='Link z profilu.')
    account = PoliticalAccount.objects.create(user_id=user_id, handle=handle, display_name=figure.canonical_name, camp=camp,
                                              confirmation_url='https://sejm.gov.pl', confirmation_note='Potwierdzone.')
    account.confirm(editor)
    found.resolved_account = account
    found.save(update_fields=['resolved_account'])
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk,
                                        handle=handle, evidence_url='https://sejm.gov.pl/profil', extracted_url=f'https://x.com/{handle}',
                                        candidate=found, status='candidate_created')
    return account


def person(name='Anna A', mp_id=1, handle='anna_a', user_id='601', camp='government'):
    figure = mp(name, mp_id)
    account = x_account_in(figure, handle, user_id, camp)
    assert account.camp == camp
    old = x_post(account, f'{user_id}1', OLD, days_ago=200)
    new = x_post(account, f'{user_id}2', NEW, days_ago=2)
    return figure, old, new


def staff(name='redaktor2', decide=True):
    """Personel; decide=True nadaje uprawnienie news.can_decide_positionpair (recenzja Codex 2)."""
    from django.contrib.auth.models import Permission
    user = get_user_model().objects.create_user(name, password='x', is_staff=True)
    if decide:
        user.user_permissions.add(Permission.objects.get(codename='can_decide_positionpair'))
    return get_user_model().objects.get(pk=user.pk)


def candidate(figure, old, new, context='Projekt ustawy podnosi górną stawkę podatku.'):
    return pp.suggest(figure, 'podatek od nieruchomości', f'post:{old.pk}', f'post:{new.pk}',
                      'Nie podniesiemy podatku od nieruchomości', 'Podatek od nieruchomości musi wzrosnąć', context)


def profile(figure):
    return APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/').json()


# --- walidator ---------------------------------------------------------------------------------------------------------

def test_valid_pair_orders_a_older_and_takes_sources_from_materials():
    figure, old, new = person()
    data = pp.validate(figure, f'post:{new.pk}', f'post:{old.pk}', 'Podatek od nieruchomości musi wzrosnąć',
                       'Nie podniesiemy podatku od nieruchomości', '', 'podatek od nieruchomości')
    assert data['a']['key'] == f'post:{old.pk}' and data['b']['key'] == f'post:{new.pk}'
    assert data['a']['quote'] == 'Nie podniesiemy podatku od nieruchomości'
    assert data['a']['source'] == {'name': '@anna_a na X', 'url': old.url, 'fetched_at': data['a']['source']['fetched_at']}
    assert data['a']['kind_label'] == 'Wpis na X'


def test_vote_side_uses_official_ballot():
    figure, _, new = person()
    v = voting(300, [(1, 'Anna A', 'KO', 'NO')])
    ballot = Ballot.objects.get(voting=v, mp_id=1)
    data = pp.validate(figure, f'ballot:{ballot.pk}', f'post:{new.pk}', None, 'Podatek od nieruchomości musi wzrosnąć', '',
                       'podatek od nieruchomości')
    assert data['a']['kind'] == 'glos' and data['a']['vote'] == 'przeciw' and data['a']['quote'] is None
    assert 'Głosowanie 300' in data['a']['vote_subject'] and 'sejm.gov.pl' in data['a']['source']['url']


@pytest.mark.parametrize('case,needle', [
    ('obca osoba', 'brak materiału tej osoby'),
    ('cytat spoza', 'nie jest dosłownym'),
    ('za blisko', 'różnica czasu'),
    ('ocena w kontekście', 'słowo oceniające'),
    ('warunkowa', 'warunkowa'),
    ('ironia', 'ironii'),
    ('podanie dalej', 'podanie dalej'),
    ('dwa zdania', 'więcej niż jedno zdanie'),
])
def test_validator_rejects(case, needle):
    figure, old, new = person()
    a_key, b_key = f'post:{old.pk}', f'post:{new.pk}'
    quote_a, quote_b, context = 'Nie podniesiemy podatku od nieruchomości', 'Podatek od nieruchomości musi wzrosnąć', ''
    if case == 'obca osoba':
        other, other_old, _ = person('Bartek B', 2, 'bartek_b', '602')
        a_key = f'post:{other_old.pk}'
    elif case == 'cytat spoza':
        quote_a = 'Nie podniesiemy żadnych podatków nigdy'
    elif case == 'za blisko':
        account = old.account
        near = x_post(account, '6019', 'Podatek od nieruchomości musi wzrosnąć, mówię jasno od lat.', days_ago=5)
        a_key, quote_a = f'post:{near.pk}', 'Podatek od nieruchomości musi wzrosnąć'
    elif case == 'ocena w kontekście':
        context = 'To klasyczna hipokryzja w sprawie podatku.'
    elif case == 'warunkowa':
        old.text = 'Jeśli nie będzie kryzysu, nie podniesiemy podatku od nieruchomości.'
        old.save()
        quote_a = 'Jeśli nie będzie kryzysu, nie podniesiemy podatku'
    elif case == 'ironia':
        old.text = 'Nie podniesiemy podatku od nieruchomości ;) obiecuję'
        old.save()
        quote_a = 'Nie podniesiemy podatku od nieruchomości ;)'
    elif case == 'podanie dalej':
        old.text = 'RT @ktos: Nie podniesiemy podatku od nieruchomości'
        old.save()
    elif case == 'dwa zdania':
        context = 'Projekt jest w Sejmie. Głosowanie było w piątek.'
    with pytest.raises(pp.PairError) as error:
        pp.validate(figure, a_key, b_key, quote_a, quote_b, context, 'podatek od nieruchomości')
    assert any(needle in issue for issue in error.value.issues), error.value.issues


# --- publiczność, flaga, cisza -----------------------------------------------------------------------------------------

def test_flag_off_no_changes():
    figure, old, new = person()
    pp.approve(candidate(figure, old, new), staff())
    assert 'position_pairs' not in profile(figure)
    assert APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/').status_code == 404


def test_candidates_never_public_until_approved(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = candidate(figure, old, new)
    assert pair.status == 'suggested' and list(pair.events.values_list('event', flat=True)) == ['suggested']
    assert profile(figure)['position_pairs']['items'] == []
    assert APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/').json()['items'] == []
    pp.approve(pair, staff())
    data = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/').json()
    item = data['items'][0]
    assert item['a']['date'] < item['b']['date'] and item['a']['quote'] and item['b']['quote']
    assert item['notice'] == pp.NOTICE and item['context'] and 'count' not in data and 'total' not in data
    assert set(item) == {'id', 'topic', 'a', 'b', 'context', 'approved_at', 'ai_suggested', 'notice', 'review_pending',
                         'review_note', 'report_url', 'context_source', 'context_note', 'subject_response'}
    assert 'key' not in item['a']
    assert profile(figure)['position_pairs']['items'][0]['id'] == pair.pk


def test_rejected_and_withdrawn_hidden(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    user = staff()
    pair = pp.approve(candidate(figure, old, new), user)
    with pytest.raises(pp.PairError):
        pp.withdraw(pair, user, '')
    pp.withdraw(pair, user, 'Cytat wyrwany z kontekstu wywiadu.')
    assert profile(figure)['position_pairs']['items'] == []
    assert PositionPair.objects.get().events.filter(event='withdrawn').exists()


def test_election_silence_hides_and_blocks(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    settings.ELECTION_SILENCE = True
    block = profile(figure)['position_pairs']
    assert block['items'] == [] and block['paused'] is True
    other, o_old, o_new = person('Bartek B', 2, 'bartek_b', '602')
    with pytest.raises(pp.PairError) as error:
        pp.approve(candidate(other, o_old, o_new), staff('inny'))
    assert error.value.code == 'silence'
    assert pair.status == 'approved'


def test_unavailable_post_hides_pair(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pp.approve(candidate(figure, old, new), staff())
    old.available = False
    old.save()
    assert profile(figure)['position_pairs']['items'] == []


def test_diagnosis_detail_gets_pairs(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    diagnosis = SpinDiagnosis.objects.create(post=new, status='approved', verdict='spin', intensity=50)
    pair = pp.approve(candidate(figure, old, new), staff())
    assert pair.diagnosis_id == diagnosis.pk
    data = APIClient().get(f'/api/clinic/spins/{diagnosis.pk}/').json()
    assert data['position_pairs']['items'][0]['id'] == pair.pk


# --- sprostowanie i powiadomienia ----------------------------------------------------------------------------------------

REASON = 'Wypowiedź dotyczyła innego projektu ustawy, nie tego głosowania.'


def test_anonymous_report_queues_but_keeps_pair_visible(settings):
    """Recenzja Codex 2: anonimowe zgłoszenie (nawet z „to ja”) nie zdejmuje pary; kolejka z priorytetem i review_pending."""
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    url = f'/api/stanowiska/{pair.pk}/zgloszenie/'
    assert APIClient().post(url, {'reason': 'za krótko'}, format='json').status_code == 400
    response = APIClient().post(url, {'reason': REASON, 'is_subject': True}, format='json')
    body = response.json()
    assert response.status_code == 202 and body['status'] == 'received' and body['hidden'] is False
    assert body['confirm_email_sent'] is False and 'privacy' in body  # bez adresu e-mail nie ma czego potwierdzać
    pair.refresh_from_db()
    report = pair.reports.get()
    # Recenzja Fable: niepotwierdzone „dotyczy mnie” = priorytet zwykły i bez publicznej etykiety
    assert pair.status == 'approved' and report.priority == 'zwykly' and not report.verified and report.ip_hash
    item = profile(figure)['position_pairs']['items'][0]
    assert item['review_pending'] is False and item['review_note'] == ''
    for n in range(5):  # wiele anonimowych zgłoszeń z różnych adresów nadal nie zdejmuje pary (próg liczy tylko konta)
        APIClient(REMOTE_ADDR=f'10.0.0.{n + 2}').post(url, {'reason': REASON}, format='json')
    pair.refresh_from_db()
    assert pair.status == 'approved'
    pp.resolve_reports(pair, staff('drugi'), 'Cytat i kontekst sprawdzone w źródle.')
    assert profile(figure)['position_pairs']['items'][0]['review_pending'] is False


def test_verified_reporter_hides_pair_until_decision(settings):
    from news.clinic_models import VerifiedReporter
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    office = get_user_model().objects.create_user('biuro_posla', password='x')
    VerifiedReporter.objects.create(user=office, figure=figure, role='przedstawiciel', evidence='e-mail z domeny sejm.gov.pl')
    client = APIClient()
    client.force_authenticate(office)
    response = client.post(f'/api/stanowiska/{pair.pk}/zgloszenie/', {'reason': REASON}, format='json')
    assert response.json()['hidden'] is True
    pair.refresh_from_db()
    assert pair.status == 'suggested' and pair.reports.get().verified is True
    assert profile(figure)['position_pairs']['items'] == []
    pair = pp.approve(pair, staff('drugi'))
    assert pair.reports.get().resolved_at is not None


def test_threshold_of_independent_account_reports(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    users = [get_user_model().objects.create_user(f'czytelnik{n}', password='x') for n in range(3)]
    get_user_model().objects.filter(pk__in=[u.pk for u in users]).update(date_joined=timezone.now() - timedelta(days=10))
    _, hidden = pp.report(pair, REASON, user=users[0], ip='10.1.0.1')
    _, hidden2 = pp.report(pair, REASON, user=users[0], ip='10.1.0.2')  # to samo konto
    _, hidden3 = pp.report(pair, REASON, user=users[1], ip='10.1.0.1')  # ten sam adres
    assert not (hidden or hidden2 or hidden3) and pp.independent_reports(pair) == 1
    pp.report(pair, REASON, user=users[1], ip='10.1.0.3')
    _, hidden = pp.report(pair, REASON, user=users[2], ip='10.1.0.4')
    assert hidden is True and pp.independent_reports(pair) == 3
    pair.refresh_from_db()
    assert pair.status == 'suggested'


def test_followers_get_neutral_alert_only_after_approval(settings):
    figure, old, new = person()
    reader = get_user_model().objects.create_user('czytelnik', password='x')
    Follow.objects.create(user=reader, figure=figure, mode='posts')
    pair = candidate(figure, old, new)
    assert Notification.objects.count() == 0
    settings.POSITION_PAIRS_ENABLED = True
    pp.approve(pair, staff())
    note = Notification.objects.get(user=reader)
    assert note.kind == 'position_pair' and note.title == 'Nowe zestawienie wypowiedzi: podatek od nieruchomości' and f'#stanowiska-{pair.pk}' in note.url
    assert pp.notify_followers(pair) == 0  # bez duplikatów


# --- generator kandydatów i ta sama miara --------------------------------------------------------------------------------

def fake_ask(payload):
    return ({'relation': 'zmiana stanowiska', 'confidence': 90,
             'explanation': 'Wcześniej zapowiedź bez podwyżki, teraz poparcie dla wyższej stawki.',
             'quote_then': 'Nie podniesiemy podatku od nieruchomości', 'quote_now': 'Podatek od nieruchomości musi wzrosnąć'},
            'groq:test')


def test_from_topic_creates_ai_candidate_not_public(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    result = pp.from_topic(figure, 'podatek od nieruchomości', ask=fake_ask)
    assert result['created'] == 1
    pair = PositionPair.objects.get()
    assert pair.ai_suggested and pair.status == 'suggested' and pair.prompt_version == pp.PROMPT_VERSION
    assert profile(figure)['position_pairs']['items'] == []


def test_same_measure_for_both_sides(settings):
    """Identyczne materiały dwóch osób z różnych obozów dają identyczny wynik generatora i walidatora."""
    gov, _, _ = person('Anna A', 1, 'anna_a', '601', camp='government')
    opp, _, _ = person('Bartek B', 2, 'bartek_b', '602', camp='opposition')
    results = [pp.from_topic(f, 'podatek od nieruchomości', ask=fake_ask) for f in (gov, opp)]
    assert results[0] == results[1]
    pairs = {p.figure_id: p for p in PositionPair.objects.all()}
    strip = lambda side: {k: v for k, v in side.items() if k not in ('key', 'source')}  # noqa: E731
    assert strip(pairs[gov.pk].a) == strip(pairs[opp.pk].a) and pairs[gov.pk].context == pairs[opp.pk].context
    import inspect
    source = inspect.getsource(pp)
    assert 'camp' not in source and 'partia' not in source.lower().replace('partii ani obozu', '')


def test_from_checks_uses_existing_loop_results():
    figure, old, new = person()
    diagnosis = SpinDiagnosis.objects.create(post=new, status='approved', verdict='spin', intensity=50)
    PositionCheck.objects.create(diagnosis=diagnosis, source_kind='post', source_key=f'post:{old.pk}', earlier_post=old,
                                 source_url=old.url, source_date=old.published_at.date(), earlier_text=OLD, relation='change',
                                 confidence=80, explanation='Wcześniej zapowiedź bez podwyżki, teraz poparcie dla wyższej stawki.',
                                 quote_then='Nie podniesiemy podatku od nieruchomości', quote_now='Podatek od nieruchomości musi wzrosnąć')
    result = pp.from_checks()
    assert result['created'] == 1
    pair = PositionPair.objects.get()
    assert pair.ai_suggested and pair.source_check_id and pair.diagnosis_id == diagnosis.pk
    assert pair.topic == ''  # dwa wpisy: temat wpisuje człowiek przy zatwierdzeniu (bez losowych słów)
    assert pp.from_checks()['created'] == 0  # bez duplikatów


def test_command_add_approve_withdraw():
    figure, old, new = person()
    staff('dyzurny')
    with pytest.raises(CommandError):
        call_command('pary_stanowisk', 'dodaj', '--osoba', str(figure.pk), '--temat', 'podatek', '--a', f'post:{old.pk}',
                     '--b', f'post:{new.pk}', '--cytat-a', 'zmyślony cytat bez pokrycia', '--cytat-b', 'Podatek od nieruchomości musi wzrosnąć',
                     '--kto', 'dyzurny')
    call_command('pary_stanowisk', 'dodaj', '--osoba', str(figure.pk), '--temat', 'podatek od nieruchomości', '--a', f'post:{old.pk}',
                 '--b', f'post:{new.pk}', '--cytat-a', 'Nie podniesiemy podatku od nieruchomości',
                 '--cytat-b', 'Podatek od nieruchomości musi wzrosnąć', '--kto', 'dyzurny')
    pair = PositionPair.objects.get()
    assert not pair.ai_suggested and pair.suggested_by.username == 'dyzurny'
    with pytest.raises(CommandError):  # cztery oczy: ta sama osoba nie zatwierdza
        call_command('pary_stanowisk', 'zatwierdz', str(pair.pk), '--kto', 'dyzurny', '--kontekst', 'Projekt dotyczy stawek od 2027 roku.')
    staff('drugi_dyzurny')
    with pytest.raises(CommandError):  # kontekst obowiązkowy
        call_command('pary_stanowisk', 'zatwierdz', str(pair.pk), '--kto', 'drugi_dyzurny')
    call_command('pary_stanowisk', 'zatwierdz', str(pair.pk), '--kto', 'drugi_dyzurny', '--kontekst', 'Projekt dotyczy stawek od 2027 roku.')
    pair.refresh_from_db()
    assert pair.context_source == 'human' and pair.approved_by.username == 'drugi_dyzurny'
    with pytest.raises(CommandError):
        call_command('pary_stanowisk', 'wycofaj', str(pair.pk), '--kto', 'dyzurny')
    call_command('pary_stanowisk', 'wycofaj', str(pair.pk), '--kto', 'dyzurny', '--uwaga', 'Prośba o sprostowanie uznana.')
    pair.refresh_from_db()
    assert pair.status == 'withdrawn' and pair.approved_by.username == 'drugi_dyzurny'
    call_command('pary_stanowisk', 'bilans')


# --- recenzja Codex 2 (13.10): poprawki -----------------------------------------------------------------------------------

def test_shortened_quote_from_conditional_sentence_rejected():
    figure, old, new = person()
    old.text = 'Jeśli nie będzie kryzysu, nie podniesiemy podatku od nieruchomości. Mówię to jasno.'
    old.save()
    with pytest.raises(pp.PairError) as error:
        pp.validate(figure, f'post:{old.pk}', f'post:{new.pk}', 'nie podniesiemy podatku od nieruchomości',
                    'Podatek od nieruchomości musi wzrosnąć', '', 'podatek od nieruchomości')
    assert any('warunkowa' in issue for issue in error.value.issues)
    old.text = 'Mówię to jasno. Nie podniesiemy podatku od nieruchomości. Jeśli ktoś pyta o inne podatki, to inna sprawa.'
    old.save()
    data = pp.validate(figure, f'post:{old.pk}', f'post:{new.pk}', 'Nie podniesiemy podatku od nieruchomości',
                       'Podatek od nieruchomości musi wzrosnąć', '', 'podatek od nieruchomości')
    assert data['a']['quote']  # warunek w innym zdaniu nie blokuje


@pytest.mark.parametrize('text,data', [
    ('  rt @ktos: Nie podniesiemy podatku od nieruchomości', {}),
    ('RT  @ktos Nie podniesiemy podatku od nieruchomości', {}),
    ('„@ktos: Nie podniesiemy podatku od nieruchomości”', {}),
    ('Nie podniesiemy podatku od nieruchomości via @ktos', {}),
    ('Nie podniesiemy podatku od nieruchomości', {'referenced_tweets': [{'type': 'quoted', 'id': '1'}]}),
    ('Nie podniesiemy podatku od nieruchomości', {'referenced_posts': [{'type': 'retweeted', 'id': '2'}]}),
])
def test_reposts_and_quote_posts_rejected(text, data):
    figure, old, new = person()
    old.text, old.source_data = text, data
    old.save()
    with pytest.raises(pp.PairError) as error:
        pp.validate(figure, f'post:{old.pk}', f'post:{new.pk}', 'Nie podniesiemy podatku od nieruchomości',
                    'Podatek od nieruchomości musi wzrosnąć', '', 'podatek od nieruchomości')
    assert any('podanie dalej' in issue for issue in error.value.issues)


def test_reply_is_own_statement():
    figure, old, new = person()
    old.source_data = {'referenced_tweets': [{'type': 'replied_to', 'id': '3'}]}
    old.save()
    assert pp.validate(figure, f'post:{old.pk}', f'post:{new.pk}', 'Nie podniesiemy podatku od nieruchomości',
                       'Podatek od nieruchomości musi wzrosnąć', '', 'podatek od nieruchomości')


def test_approve_refuses_unavailable_post():
    figure, old, new = person()
    pair = candidate(figure, old, new)
    old.available = False
    old.save()
    with pytest.raises(pp.PairError) as error:
        pp.approve(pair, staff())
    assert error.value.code == 'unavailable' and 'niedostępny' in str(error.value)
    pair.refresh_from_db()
    assert pair.status == 'suggested'


def test_pairs_never_cached_by_intermediaries(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pp.approve(candidate(figure, old, new), staff())
    response = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/')
    assert response['Cache-Control'] == 'no-store' and response.json()['items']
    assert APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/')['Cache-Control'] == 'no-store'
    settings.ELECTION_SILENCE = True
    response = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/')
    assert response['Cache-Control'] == 'no-store' and response.json()['items'] == [] and response.json()['paused'] is True


def test_decisions_require_permission():
    figure, old, new = person()
    pair = candidate(figure, old, new)
    staff('bez_prawa', decide=False)
    with pytest.raises(CommandError):
        call_command('pary_stanowisk', 'zatwierdz', str(pair.pk), '--kto', 'bez_prawa')
    pair.refresh_from_db()
    assert pair.status == 'suggested'


def test_command_verify_reporter_and_queue():
    from news.clinic_models import VerifiedReporter
    figure, old, new = person()
    staff('dyzurny')
    get_user_model().objects.create_user('biuro', password='x')
    call_command('pary_stanowisk', 'zweryfikuj', '--login', 'biuro', '--osoba', str(figure.pk), '--dowod', 'pismo z biura',
                 '--kto', 'dyzurny')
    assert VerifiedReporter.objects.get().verified_by.username == 'dyzurny'
    call_command('pary_stanowisk', 'zgloszenia')

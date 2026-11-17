"""Recenzja Fable 13.10 (prawo i produkt): stary blok „Zmiana zdania” wyłączony, semantyka głosu, sformułowania, kontekst
obowiązkowy, cztery oczy, nazwiska w łańcuchu, sprostowania i rejestr korekt, potwierdzenie e-mail, graf po identyfikatorach,
przełączniki w bazie (SiteFlag) i cisza wyborcza z datami. Bez sieci (poczta: locmem)."""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from news import causal_chain, position_pairs as pp, v3_flags
from news import zmiana_zdania as zz
from news.clinic_models import CausalChain, PositionCheck, PositionPair, SiteFlag, SiteFlagChange, SpinDiagnosis
from news.models import Ballot
from news.test_position_pairs import OLD, NEW, candidate, person, staff as pair_staff
from news.test_przeszlosc_osoba import mp, voting
from news.test_spina_v3 import DAY, fake_ask, good_steps, make_message, staff as chain_staff

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    cache.clear()
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    yield
    cache.clear()


# --- 1. stary blok „Zmiana zdania” -----------------------------------------------------------------------------------------

def legacy_check():
    figure, old, new = person()
    diagnosis = SpinDiagnosis.objects.create(post=new, status='approved', verdict='spin', intensity=50)
    PositionCheck.objects.create(diagnosis=diagnosis, source_kind='post', source_key=f'post:{old.pk}', earlier_post=old,
                                 source_url=old.url, source_date=old.published_at.date(), earlier_text=OLD, relation='change',
                                 confidence=90, explanation='Wcześniej zapowiedź bez podwyżki, teraz poparcie dla wyższej stawki.',
                                 quote_then='Nie podniesiemy podatku od nieruchomości', quote_now='Podatek od nieruchomości musi wzrosnąć')
    return diagnosis


def test_legacy_block_off_by_default(settings):
    diagnosis = legacy_check()
    data = APIClient().get(f'/api/clinic/spins/{diagnosis.pk}/').json()
    assert data['position_changes'] is None and zz.social_line(data) == ''
    assert zz.social_line({'position_changes': {'items': [{'date': '2026-01-01'}]}}) == ''
    settings.POSITION_CHANGES_LEGACY_ENABLED = True
    assert zz.public_data(diagnosis)['items']  # włączony ręcznie: działa jak dawniej
    settings.ELECTION_SILENCE = True
    assert zz.public_data(diagnosis) is None  # ale nie w ciszy wyborczej


def test_legacy_review_command_moves_to_human_queue():
    legacy_check()
    call_command('pary_stanowisk', 'stare', '--przenies')
    pair = PositionPair.objects.get()
    assert pair.status == 'suggested' and pair.ai_suggested and pair.context_source == 'ai'


# --- 2. semantyka głosu ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('motion,target', [
    ('wniosek o odrzucenie projektu w pierwszym czytaniu', 'wniosek o odrzucenie'),
    ('poprawka 3 do art. 5', 'poprawka'),
    ('całość projektu', 'całość'),
    ('w trzecim czytaniu', 'całość'),
    ('wniosek o przerwę', 'inne'),
])
def test_vote_target(motion, target):
    assert pp.vote_target(motion) == target


def vote_pair(motion, vote='YES'):
    figure, old, new = person()
    v = voting(300, [(1, 'Anna A', 'KO', vote)])
    v.motion = motion
    v.save()
    ballot = Ballot.objects.get(voting=v, mp_id=1)
    pair = pp.suggest(figure, 'podatek od nieruchomości', f'ballot:{ballot.pk}', f'post:{new.pk}', None,
                      'Podatek od nieruchomości musi wzrosnąć', 'Głosowanie dotyczyło wniosku o odrzucenie projektu.')
    return pair


def test_rejection_motion_needs_confirmation_and_is_described(settings):
    settings.POSITION_PAIRS_ENABLED = True
    pair = vote_pair('wniosek o odrzucenie projektu w pierwszym czytaniu')
    assert pair.a['vote_target'] == 'wniosek o odrzucenie' and pair.a['vote_label'] == 'za wnioskiem o odrzucenie projektu'
    assert pair.a['vote_subject'].startswith('Wniosek o odrzucenie: ')
    with pytest.raises(pp.PairError) as error:
        pp.approve(pair, pair_staff())
    assert error.value.code == 'subject'
    pair = pp.approve(pair, pair_staff('drugi'), confirm_subject=True)
    item = APIClient().get(f'/api/przeszlosc/osoba/{pair.figure_id}/stanowiska/').json()['items'][0]
    assert item['a']['vote_label'] == 'za wnioskiem o odrzucenie projektu' and item['a']['vote'] == 'za'
    assert pair.events.get(event='approved').details['confirm_subject'] is True


def test_whole_bill_vote_needs_no_confirmation():
    pair = vote_pair('całość projektu', vote='NO')
    assert pair.a['vote_label'] == 'przeciw całości projektu'
    assert pp.approve(pair, pair_staff()).status == 'approved'


# --- 3, 4. sformułowania, kontekst i temat ---------------------------------------------------------------------------------

def test_notice_discloses_criterion_and_alert_has_topic():
    assert 'według naszej metody' in pp.NOTICE and 'bez oceny' not in pp.NOTICE
    assert pp.ALERT_TITLE.format(topic='VAT') == 'Nowe zestawienie wypowiedzi: VAT'


def test_context_and_topic_required_and_marked(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = candidate(figure, old, new, context='')
    with pytest.raises(pp.PairError) as error:
        pp.approve(pair, pair_staff())
    assert error.value.code == 'context'
    pair.topic = ''
    pair.save()
    with pytest.raises(pp.PairError) as error:
        pp.approve(pair, pair_staff('drugi'), context='Projekt podnosi stawki od 2027 roku.')
    assert error.value.code == 'topic'
    pair = pp.approve(pair, pair_staff('trzeci'), context='Projekt podnosi stawki od 2027 roku.', topic='podatek od nieruchomości')
    item = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/').json()['items'][0]
    assert item['context_source'] == 'human' and item['context_note'] == pp.CONTEXT_NOTE['human']


def test_four_eyes_for_human_suggestions():
    figure, old, new = person()
    author = pair_staff('autor')
    pair = pp.suggest(figure, 'podatek od nieruchomości', f'post:{old.pk}', f'post:{new.pk}', 'Nie podniesiemy podatku od nieruchomości',
                      'Podatek od nieruchomości musi wzrosnąć', 'Projekt podnosi stawki od 2027 roku.', user=author)
    with pytest.raises(pp.PairError) as error:
        pp.approve(pair, author)
    assert error.value.code == 'four_eyes'
    assert pp.approve(pair, pair_staff('drugi')).status == 'approved'


# --- 8. nazwiska w łańcuchu, wpis usunięty z X ---------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    'Poseł Test pomija etap konsultacji.',      # imię i nazwisko z materiałów (display_name konta)
    'Wpis @ministerstwo pomija konsultacje.',    # @konto
])
def test_names_and_handles_not_allowed_outside_facts(text):
    message, _ = make_message()
    items = causal_chain.materials(message)
    steps, gates = causal_chain.validate_steps(good_steps(message) + [{'kind': 'spin', 'text': text}], items)
    assert len(steps) == 4 and 'nazwisko' in gates['prawnik']['issues'][0]['issue']


def test_inflected_surname_detected():
    items = [{'person': 'Jan Kowalski'}]
    assert causal_chain._names_in('Przekaz Kowalskiego pomija dane.', items)
    assert not causal_chain._names_in('Przekaz pomija dane z kowalni.', items)


def test_public_chain_hidden_when_material_post_deleted(settings):
    settings.CAUSAL_CHAIN_ENABLED = True
    message, posts = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    causal_chain.approve(chain, chain_staff())
    url = f'/api/clinic/messages/{DAY.isoformat()}/'
    assert APIClient().get(url).json()['government']['causal_chain']['report_url'].endswith('/causal-chain/zgloszenie/')
    posts[1].available = False
    posts[1].save()
    assert APIClient().get(url).json()['government']['causal_chain'] is None


# --- 6. sprostowanie łańcucha i rejestry korekt ----------------------------------------------------------------------------

def test_chain_report_and_corrections_register(settings):
    settings.CAUSAL_CHAIN_ENABLED = True
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    user = chain_staff()
    causal_chain.approve(chain, user)
    response = APIClient().post(f'/api/clinic/messages/{message.pk}/causal-chain/zgloszenie/',
                                {'reason': 'Krok drugi przypisuje przekazowi coś, czego nie ma we wpisach.'}, format='json')
    assert response.status_code == 202
    assert chain.reports.count() == 1
    with pytest.raises(causal_chain.ChainError) as error:
        causal_chain.reject(chain, user)
    assert error.value.code == 'note'
    causal_chain.reject(chain, user, 'Krok drugi nie wynikał z materiałów.')
    assert chain.reports.get().resolved_at is not None
    register = APIClient().get('/api/clinic/corrections/').json()
    row = next(r for r in register['results'] if r['type'] == 'chain_withdrawal')
    assert row['reason'] == 'Krok drugi nie wynikał z materiałów.' and row['author'] is None and 'contact' not in str(row)
    assert register['counts']['chains'] == 1


def test_pair_withdrawal_in_przeszlosc_register(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    pp.withdraw(pair, pair_staff('drugi'), 'Cytat dotyczył innego projektu.')
    rows = APIClient().get('/api/przeszlosc/poprawki/').json()['results']
    assert rows[0]['type'] == 'pair_withdrawal' and 'innego projektu' in rows[0]['label']


# --- 5. ścieżka osoby: potwierdzenie e-mail, wiek kont, odpowiedź, retencja -------------------------------------------------

def report(pair, contact, is_subject=True):
    return APIClient().post(f'/api/stanowiska/{pair.pk}/zgloszenie/', {
        'reason': 'Wypowiedź dotyczyła innego projektu ustawy, nie tego głosowania.', 'contact': contact,
        'is_subject': is_subject}, format='json').json()


def token_from_mail():
    body = mail.outbox[-1].body
    return body.split('/potwierdz/')[1].split('/')[0]


def test_official_domain_confirmation_hides_pair(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    body = report(pair, 'biuro.anny@sejm.gov.pl')
    assert body['confirm_email_sent'] is True and body['hidden'] is False and len(mail.outbox) == 1
    pair.refresh_from_db()
    assert pair.status == 'approved'
    confirmed = APIClient().get(f'/api/stanowiska/zgloszenie/potwierdz/{token_from_mail()}/').json()
    assert confirmed == {'status': 'confirmed', 'hidden': True}
    pair.refresh_from_db()
    assert pair.status == 'suggested' and pair.reports.get().official_domain is True
    pp.approve(pair, pair_staff('drugi'), 'Sprawdzono: cytat i głos dotyczą tego samego projektu.')
    assert 'Decyzja w sprawie zgłoszenia' in mail.outbox[-1].subject and 'Uzasadnienie' in mail.outbox[-1].body


def test_other_domain_confirmation_marks_review_pending(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    report(pair, 'jan@example.com')
    APIClient().get(f'/api/stanowiska/zgloszenie/potwierdz/{token_from_mail()}/')
    pair.refresh_from_db()
    row = pair.reports.get()
    assert pair.status == 'approved' and row.priority == 'wysoki' and not row.official_domain
    item = APIClient().get(f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/').json()['items'][0]
    assert item['review_pending'] is True
    pp.resolve_reports(pair, pair_staff('drugi'), 'Kontekst opisany, cytaty dosłowne.')
    assert 'pozostaje bez zmian' in mail.outbox[-1].body


def test_confirmation_link_expires(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    report(pair, 'biuro.anny@sejm.gov.pl')
    pair.reports.update(created_at=timezone.now() - timedelta(hours=49), token_expires_at=timezone.now() - timedelta(hours=1))
    assert APIClient().get(f'/api/stanowiska/zgloszenie/potwierdz/{token_from_mail()}/').status_code == 410


def test_young_accounts_do_not_count_toward_threshold(settings):
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    users = [get_user_model().objects.create_user(f'nowy{n}', password='x') for n in range(3)]
    for n, user in enumerate(users):
        _, hidden = pp.report(pair, 'Wypowiedź dotyczyła innego projektu ustawy.', user=user, ip=f'10.2.0.{n}')
    assert hidden is False and pp.independent_reports(pair) == 0


def test_contact_retention():
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), pair_staff())
    row, _ = pp.report(pair, 'Wypowiedź dotyczyła innego projektu ustawy.', 'jan@example.com', True)
    row.resolved_at = timezone.now() - timedelta(days=91)
    row.save()
    call_command('pary_stanowisk', 'czysc-kontakty')
    row.refresh_from_db()
    assert row.contact == '' and row.confirm_token == '' and row.reason


# --- 10. graf i dane trzecie -----------------------------------------------------------------------------------------------

def test_graph_nodes_by_id_and_every_edge_sourced(settings):
    settings.PRZESZLOSC_NETWORK_ENABLED = True
    anna = mp('Anna A', 1)
    for n in range(1, 4):
        voting(n, [(1, 'Anna A', 'KO', 'YES'), (3, 'Celina C', 'KO', 'NO')])
    data = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/').json()
    ids = {n['id'] for n in data['nodes']}
    assert 'mp:10:3' in ids and not any('Celina' in i for i in ids)
    for edge in data['edges']:
        assert edge['evidence'] or (edge['evidence_note'] and edge['evidence_url'].startswith('/przeszlosc/osoba/'))
    vote_edge = next(e for e in data['edges'] if e['kind'] == 'glosowania')
    assert 'wspólnych głosowaniach' in vote_edge['label'] and vote_edge['window'] == 3


def test_mp_expenses_labelled_as_third_party():
    from news.przeszlosc_osoba import mp_identities
    from news.public_records_models import PublicRecord, PublicRecordPerson
    from news.zrodla_profil import open_data
    anna = mp('Anna A', 1)
    record = PublicRecord.objects.create(source='mileage', kind='office_report', external_id='o1', source_url='https://jakglosuja.pl/x',
                                         response_sha256='c' * 64, response_url='https://jakglosuja.pl', term=10, date=date(2026, 1, 1),
                                         title='Biuro', data={'year': 2025, 'total_pln': 1000, 'pdf_url': 'https://orka.sejm.gov.pl/a.pdf'})
    PublicRecordPerson.objects.create(record=record, term=10, mp_id=1, figure=anna)
    block = open_data(anna, mp_identities(anna))['mp_expenses']
    assert block['third_party'] is True and 'nie sprawdzono automatycznie' in block['notice']
    assert block['primary_urls'] == ['https://orka.sejm.gov.pl/a.pdf'] and block['source_label'] == 'jakglosuja.pl'


# --- 9. przełączniki w bazie i cisza wyborcza z datami ---------------------------------------------------------------------

def test_site_flag_overrides_env_without_restart(settings):
    settings.POSITION_PAIRS_ENABLED = True
    assert pp.enabled()
    SiteFlag.objects.create(key='POSITION_PAIRS_ENABLED', value=False)
    assert not pp.enabled()  # zapis czyści pamięć przełączników
    SiteFlag.objects.all().delete()
    assert pp.enabled()


def test_election_silence_window_from_site_flag_and_settings(settings):
    now = timezone.now()
    SiteFlag.objects.create(key='ELECTION_SILENCE', value=True, active_from=now + timedelta(hours=1),
                            active_until=now + timedelta(hours=25))
    assert not v3_flags.silence(now) and v3_flags.silence(now + timedelta(hours=2)) and not v3_flags.silence(now + timedelta(hours=26))
    SiteFlag.objects.all().delete()
    settings.ELECTION_SILENCE_FROM, settings.ELECTION_SILENCE_UNTIL = now - timedelta(hours=1), now + timedelta(hours=1)
    assert causal_chain.silence() and pp.silence()


def test_switch_command_logs_changes(settings):
    pair_staff('operator')
    call_command('przelacznik', 'ustaw', 'CAUSAL_CHAIN_ENABLED', 'off', '--kto', 'operator', '--uwaga', 'afera o 22:00')
    assert SiteFlag.objects.get(key='CAUSAL_CHAIN_ENABLED').value is False and not causal_chain.enabled()
    call_command('przelacznik', 'usun', 'CAUSAL_CHAIN_ENABLED', '--kto', 'operator')
    assert list(SiteFlagChange.objects.order_by('changed_at').values_list('key', flat=True)) == ['CAUSAL_CHAIN_ENABLED'] * 2
    with pytest.raises(CommandError):
        call_command('przelacznik', 'ustaw', 'COKOLWIEK', 'on', '--kto', 'operator')
    call_command('przelacznik', 'lista')

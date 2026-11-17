"""Ruch 7: pętla „Zamówienia publiczne” - sygnały z zebranych ogłoszeń BZP, bez sieci i bez wysyłki do zamawiających."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from news import zamowienia
from news.agent_models import AgentNote
from news.public_records_models import PublicRecord

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 8, 10, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def offline():
    with patch('requests.sessions.Session.request', side_effect=AssertionError('No network')), \
         patch('news.social_publish._mail', return_value=True) as mail:
        yield mail


def notice(nid, title, cpv='', kind='ContractNotice', deadline='2026-10-20T08:00:00Z', **data):
    return PublicRecord.objects.create(source='bzp', kind='notice', external_id=nid, source_url=f'https://ezamowienia.gov.pl/x/{nid}',
        response_url='https://ezamowienia.gov.pl/s', response_sha256='0' * 64, fetched_at=NOW - timedelta(hours=1), title=title,
        data={'noticeType': kind, 'cpvCode': cpv, 'organizationName': 'GMINA TESTOWA', 'organizationCity': 'Mosina',
              'submittingOffersDate': deadline, 'isTenderAmountBelowEU': True, 'noticeNumber': f'2026/BZP {nid}', **data})


def test_signals_only_for_actionable_matching_future_notices(offline):
    notice('a', 'Usługa', cpv='72413000-8 (Usługi w zakresie projektowania stron WWW)')
    notice('b', 'Wykonanie nowej strony internetowej gminy')
    notice('c', 'Dostosowanie BIP i deklaracja dostępności')
    notice('d', 'Remont drogi gminnej')
    notice('e', 'Strona internetowa', kind='TenderResultNotice')
    notice('f', 'Strona internetowa szkoły', deadline='2026-10-01T08:00:00Z')
    notice('g', 'Dostępność architektoniczna budynku')
    result = zamowienia.run(NOW)
    notes = AgentNote.objects.filter(agent='zamowienia', kind='signal')
    assert {n.scores['notice_id'] for n in notes} == {'a', 'b', 'c'}
    assert result['signals'] == 3 and result['produced'] == 7 and result['mailed']
    note = notes.get(scores__notice_id='a')
    assert 'CPV 72413000' in note.body and 'Szkic oferty' in note.body and 'WCAG 2.1 AA' in note.body
    assert 'GMINA TESTOWA' in note.title and note.sources == ['https://ezamowienia.gov.pl/x/a']
    assert offline.call_args.kwargs == {'important': True}
    # drugi bieg: bez duplikatów i bez maila
    offline.reset_mock()
    assert zamowienia.run(NOW)['signals'] == 0 and not offline.called


def test_decision_and_auto_close_after_deadline(django_user_model):
    notice('a', 'Nowa strona internetowa', deadline='2026-10-08T08:00:00Z')
    notice('b', 'Serwis internetowy muzeum', deadline='2026-10-30T08:00:00Z')
    zamowienia.run(NOW)
    user = django_user_model.objects.create_user('owner')
    b = AgentNote.objects.get(scores__notice_id='b')
    zamowienia.decide(b, 'składamy', user)
    assert zamowienia.close_expired(NOW + timedelta(days=2)) == 1
    a = AgentNote.objects.get(scores__notice_id='a')
    b.refresh_from_db()
    assert a.status == 'rejected' and a.scores['decision'] == 'termin minął'
    assert b.status == 'accepted' and b.scores['decision'] == 'składamy' and b.decided_by == user


def test_empty_database_hint():
    result = zamowienia.run(NOW)
    assert result['produced'] == 0 and 'BZP_API_ENABLED' in result['hint']


def test_bzp_collector_keeps_notice_fields():
    from scraper.bzp_backfill import save_notice_record
    row = {'noticeId': 'n1', 'cpvCode': '72413000-8 (x)', 'organizationName': 'GMINA', 'submittingOffersDate': '2026-10-20T08:00:00Z',
           'noticeType': 'ContractNotice', 'orderObject': 'Strona'}
    save_notice_record(row, 'n1', '2026/BZP 1', 'Strona', NOW, 'https://ezamowienia.gov.pl/n1')
    save_notice_record(row, 'n1', '2026/BZP 1', 'Strona', NOW, 'https://ezamowienia.gov.pl/n1')
    record = PublicRecord.objects.get(source='bzp', kind='notice')
    assert record.data['cpvCode'].startswith('72413000') and record.data['noticeNumber'] == '2026/BZP 1'


def test_admin_list_and_actions(admin_client):
    notice('a', 'Nowa strona internetowa')
    zamowienia.run(NOW)
    note = AgentNote.objects.get(agent='zamowienia')
    admin_client.post('/admin/news/zamowieniesygnal/', {'action': 'skip', '_selected_action': [note.pk]})
    note.refresh_from_db()
    assert note.status == 'rejected' and note.scores['decision'] == 'pomijamy'


def test_hunter_profiles_beyond_websites(offline):
    """Łowca zleceń (21.10): wszystkie obszary iapply, bez sprzętu i bez fałszywych trafień z budownictwa."""
    notice('s1', 'Wykonanie aplikacji mobilnej dla mieszkańców')
    notice('s2', 'Wdrożenie chatbota AI na stronie urzędu')
    notice('s3', 'Usługa', cpv='79341000-6 (Usługi reklamowe)')
    notice('s4', 'Automatyzacja procesów obsługi wniosków')
    notice('s5', 'Szkolenia z zakresu sztucznej inteligencji dla pracowników')
    notice('s6', 'Modernizacja elementów systemu informacji o prawie')
    notice('n1', 'Budowa systemu kanalizacji sanitarnej')
    notice('n2', 'Automatyzacja oświetlenia hali sportowej')
    notice('n3', 'Dostawa serwerów', cpv='72413000-8 (Usługi w zakresie projektowania stron WWW)', orderType='Delivery')
    notice('n4', 'Dostawa licencji', cpv='48000000-8 (Pakiety oprogramowania)', orderType='Delivery')
    zamowienia.run(NOW)
    found = {n.scores['notice_id']: n.scores['profile'] for n in AgentNote.objects.filter(agent='zamowienia')}
    assert found == {'s1': 'oprogramowanie', 's2': 'ai', 's3': 'marketing', 's4': 'automatyzacja', 's5': 'szkolenia', 's6': 'oprogramowanie'}
    note = AgentNote.objects.get(scores__notice_id='s2')
    assert 'Obszar: AI i analiza danych' in note.body and 'WCAG 2.1 AA' not in note.body and 'referencje' in note.body
    subject, text = offline.call_args.args[1], offline.call_args.args[2]
    assert subject.startswith('Łowca zleceń: 6') and 'AI i analiza danych:' in text and 'Marketing' in text

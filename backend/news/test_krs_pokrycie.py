from datetime import date

import pytest

from news import krs, krs_agent, krs_pokrycie
from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation
from news.przeszlosc_models import KrsKolejka
from news.public_records_models import PublicRecord
from news.test_krs import ODPIS

NIP = '5260250995'  # poprawna suma kontrolna


def _extract(nip=NIP, krs_number='0000012345'):
    extract = krs.parse(krs_number, 'S', ODPIS)
    extract.nip = nip
    return extract


def _record(source, kind, ext, data):
    return PublicRecord.objects.create(source=source, kind=kind, external_id=ext, source_url='https://example.org/' + ext,
                                       response_sha256='0' * 64, response_url='https://example.org/' + ext, data=data)


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setenv('KRS_POKRYCIE_ODSTEP', '0')


def test_valid_nip():
    assert krs_pokrycie.valid_nip('PL 526-025-09-95') == NIP
    assert krs_pokrycie.valid_nip('5260250996') == '' and krs_pokrycie.valid_nip('123') == ''


@pytest.mark.django_db
def test_zasil_takes_only_identifiers_and_skips_natural_persons():
    RegisteredOrganisation.objects.create(name='Znana', krs_number='0000000001', kind='company',
                                          official_register_url='https://wyszukiwarka-krs.ms.gov.pl/', nip='')
    _record('ted', 'notice', '1-2026', {'buyer_nip': NIP, 'winners': [
        {'name': 'Jan Kowalski', 'osoba_fizyczna': True},
        {'name': 'Firma sp. z o.o.', 'osoba_fizyczna': False, 'id': 'PL7740001454'},
        {'name': 'GmbH', 'osoba_fizyczna': False, 'id': 'DE123456789'}]})
    _record('niw', 'grant_pl', 'n1', {'krs': '0000099999'})
    stats = krs_pokrycie.zasil()
    queued = set(KrsKolejka.objects.values_list('kind', 'value', 'origin'))
    assert ('krs', '0000000001', 'org') in queued  # podmiot bez NIP: po odpis
    assert ('nip', NIP, 'ted_zamawiajacy') in queued and ('nip', '7740001454', 'ted_wykonawca') in queued
    assert ('krs', '0000099999', 'niw') in queued
    assert not any(v.startswith('DE') or 'Kowalski' in v for _, v, _ in queued)
    assert stats['ted_wykonawca'] == 1
    assert krs_pokrycie.zasil() == {}  # idempotentne


@pytest.mark.django_db
def test_nip_goes_through_biala_lista_and_krs_must_agree(monkeypatch):
    KrsKolejka.objects.create(kind='nip', value=NIP, origin='ted_wykonawca')
    KrsKolejka.objects.create(kind='nip', value='7740001454', origin='ted_wykonawca')
    KrsKolejka.objects.create(kind='nip', value='1132853869', origin='bzp')
    monkeypatch.setattr(krs_pokrycie, 'biala_lista', lambda nips, day=None: (
        {NIP: '0000012345', '7740001454': '0000054321', '1132853869': ''}, 'ok'))
    extracts = {'0000012345': _extract(), '0000054321': _extract(nip='1111111111', krs_number='0000054321')}
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=True, timeout=30: (extracts.get(number), 'ok' if number in extracts else 'missing'))
    stats = krs_pokrycie.uzupelnij(limit=10, wl_limit=1)
    assert stats['ok'] == 1 and stats['mismatch'] == 1 and stats['no_krs'] == 1
    org = RegisteredOrganisation.objects.get(krs_number='0000012345')
    assert org.nip == NIP and org.name == 'Fundacja Testowa Pomocy'
    assert not RegisteredOrganisation.objects.filter(krs_number='0000054321').exists()  # NIP w KRS inny - nie zapisujemy
    assert KrsKolejka.objects.get(value='1132853869').status == 'no_krs'


@pytest.mark.django_db
def test_network_error_is_retried_not_missing(monkeypatch):
    item = KrsKolejka.objects.create(kind='krs', value='0000012345', origin='org')
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=True, timeout=30: (None, 'error'))
    assert krs_pokrycie.uzupelnij(limit=5, wl_limit=0)['error'] == 1
    item.refresh_from_db()
    assert item.status == 'error' and item.attempts == 1 and item.next_try_at > item.created_at
    assert krs_pokrycie.uzupelnij(limit=5, wl_limit=0).get('odpisy') == 0  # przerwa przed ponowieniem


def test_biala_lista_keeps_only_krs(monkeypatch):
    class R:
        status_code = 200

        def json(self):
            return {'result': {'entries': [{'identifier': NIP, 'subjects': [
                {'nip': NIP, 'krs': '0000012345', 'name': 'X', 'representatives': [{'firstName': 'Jan'}]}]},
                {'identifier': '1132853869', 'subjects': [{'nip': '1132853869', 'krs': None, 'name': 'Jan Kowalski'}]}]}}
    monkeypatch.setattr(krs_pokrycie.requests, 'get', lambda *a, **k: R())
    found, status = krs_pokrycie.biala_lista([NIP, '1132853869', '7740001454'])
    assert status == 'ok' and found == {NIP: '0000012345', '1132853869': '', '7740001454': ''}


@pytest.mark.django_db
def test_full_extract_closes_relation_when_person_left_organ():
    figure = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł',
                                         evidence_url='https://sejm.gov.pl/x', import_key='test:jk2')
    org = RegisteredOrganisation.objects.create(name='Fundacja Testowa Pomocy', krs_number='0000012345', kind='foundation',
                                                official_register_url='https://wyszukiwarka-krs.ms.gov.pl/')
    rel = PublicFigureOrganisationRelation.objects.create(public_figure=figure, organisation=org, public_role='członek rady',
                                                          organ='organ nadzoru', evidence_url='https://api-krs.ms.gov.pl/x')
    rel.confirm_automatically('krs_register')
    rel.save()
    assert krs_pokrycie.refresh_relations(org, _extract()) == 1
    rel.refresh_from_db()
    assert rel.relation_status == 'former' and rel.until == date(2024, 9, 4) and rel.verification_status == 'confirmed'


@pytest.mark.django_db
def test_agent_without_source_waits_for_editor(monkeypatch):
    """Imiennicy: zgodna maska w KRS bez źródła, które wymienia osobę i podmiot, nie potwierdza relacji."""
    figure = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł',
                                         evidence_url='https://sejm.gov.pl/x', import_key='test:jk3')
    monkeypatch.setattr(krs, 'fetch', lambda number: _extract())
    monkeypatch.setattr(krs_agent, 'page_mentions', lambda url, surname, entity: False)
    candidate = {'name': 'Fundacja Testowa Pomocy', 'krs': '0000012345', 'role': 'prezes zarządu', 'period': '',
                 'current': True, 'sector': 'ngo', 'sources': [{'url': 'https://nic.pl/a', 'title': 'x'}]}
    relation = krs_agent.verify(figure, candidate)
    assert relation.verification_status == 'pending_review'


@pytest.mark.django_db
def test_raport_counts():
    PublicFigure.objects.create(canonical_name='Anna Nowak', role_category='parliamentary', role_title='Posłanka',
                                evidence_url='https://sejm.gov.pl/y', import_key='test:an')
    RegisteredOrganisation.objects.create(name='A', krs_number='0000000002', kind='company',
                                          official_register_url='https://wyszukiwarka-krs.ms.gov.pl/', nip=NIP)
    data = krs_pokrycie.raport()
    assert data['osoby']['wszystkie'] == 1 and data['osoby']['niesprawdzone'] == 1
    assert data['podmioty']['z_nip'] == 1
    assert 'OSOBY PUBLICZNE' in krs_pokrycie.raport_tekst(data)


@pytest.mark.django_db
def test_grounded_but_unread_source_does_not_confirm(monkeypatch):
    """Śledczy R3 P0-12: adres z wyników Gemini, którego strona nie wymienia osoby i podmiotu, nie potwierdza imiennika."""
    figure = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł',
                                         evidence_url='https://sejm.gov.pl/x', import_key='test:jk4')
    monkeypatch.setattr(krs, 'fetch', lambda number: _extract())
    monkeypatch.setattr(krs_agent, 'page_mentions', lambda url, surname, entity: False)
    candidate = {'name': 'Fundacja Testowa Pomocy', 'krs': '0000012345', 'role': 'prezes zarządu', 'period': '', 'current': True,
                 'sector': 'ngo', 'sources': [{'url': 'https://example.org/a', 'title': 'x', 'grounded': True}]}
    relation = krs_agent.verify(figure, candidate)
    assert relation.verification_status == 'pending_review' and all('read' not in s for s in relation.sources)


@pytest.mark.django_db
def test_org_without_nip_does_not_return_every_night():
    """Śledczy R3 P1-21: świeżo sprawdzony podmiot bez NIP w KRS nie wraca do kolejki co noc."""
    from django.utils import timezone
    RegisteredOrganisation.objects.create(name='Bez NIP', krs_number='0000000005', kind='association',
                                          official_register_url='https://wyszukiwarka-krs.ms.gov.pl/', nip='')
    krs_pokrycie.zasil()
    KrsKolejka.objects.filter(value='0000000005').update(status='ok', checked_at=timezone.now())
    assert krs_pokrycie.zasil().get('org_odswiez') is None
    assert KrsKolejka.objects.get(value='0000000005').status == 'ok'

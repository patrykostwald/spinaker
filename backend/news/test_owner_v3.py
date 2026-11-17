"""Decyzje właściciela 13.10: domeny urzędowe, klauzula art. 14 i sprzeciw, odpowiedź osoby i powiadomienie o wycofaniu,
oświadczenia majątkowe (metadane i link), narzędzia pilotażu. Bez sieci (poczta locmem, HTTP podstawione)."""
import csv
import hashlib
import shutil
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from news import asset_declarations as ad
from news import official_domains as od
from news import pilotaz
from news import position_pairs as pp
from news.clinic_models import (AssetDeclaration, DataObjection, OfficialDomainChange, PositionPair, SubjectResponse,
                                VerifiedReporter)
from news.notification_models import Follow, Notification
from news.test_position_pairs import candidate, person, staff
from news.test_przeszlosc_osoba import mp

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    cache.clear()
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    yield
    cache.clear()


# --- 1. domeny urzędowe ---------------------------------------------------------------------------------------------------

def test_domain_list_from_file_suffix_and_case():
    rows = {r['domain']: r for r in od.entries()}
    assert {'sejm.gov.pl', 'senat.gov.pl', 'pis.org.pl', 'platforma.org'} <= set(rows)
    assert all(r['source'] and r['checked'] for r in rows.values())
    assert rows['pis.org.pl']['status'] == 'do potwierdzenia'  # niepewne, ale działa od razu
    assert od.match('Biuro.Posla@Okreg.SEJM.gov.pl') == 'sejm.gov.pl'
    assert od.match('kontakt@pis.org.pl') == 'pis.org.pl'
    assert od.match('ktos@notsejm.gov.pl') is None and od.match('ktos@sejm.gov.pl.evil.com') is None
    assert pp.official_domain('jan@senat.gov.pl') and not pp.official_domain('jan@example.com')


def test_env_overrides_file(settings):
    settings.POSITION_PAIR_OFFICIAL_DOMAINS = ['example.gov.pl']
    assert od.domains() == ['example.gov.pl'] and od.match('a@sejm.gov.pl') is None


def test_command_add_remove_logged_and_check(monkeypatch):
    call_command('domeny_urzedowe', 'dodaj', 'nowa-partia.pl', '--rodzaj', 'partia', '--zrodlo', 'https://nowa-partia.pl',
                 '--kto', 'operator')
    assert od.match('x@nowa-partia.pl') == 'nowa-partia.pl'
    call_command('domeny_urzedowe', 'usun', 'pis.org.pl', '--uwaga', 'domena nieużywana w e-mailach', '--kto', 'operator')
    assert od.match('x@pis.org.pl') is None
    assert list(OfficialDomainChange.objects.order_by('changed_at').values_list('action', flat=True)) == ['add', 'remove']
    with pytest.raises(CommandError):
        call_command('domeny_urzedowe', 'dodaj', 'nie domena', '--zrodlo', 'x', '--kto', 'operator')
    import socket
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, port: [('ok',)] if host == 'sejm.gov.pl' else (_ for _ in ()).throw(OSError()))
    assert od.check('sejm.gov.pl')['dns'] is True and od.check('nieistnieje.pl')['dns'] is False
    call_command('domeny_urzedowe', 'sprawdz', 'sejm.gov.pl')
    call_command('domeny_urzedowe', 'lista')


# --- 2. klauzula art. 14 i sprzeciw ---------------------------------------------------------------------------------------

def test_privacy_notice_behind_flag(settings):
    anna = mp('Anna A', 1)
    assert 'privacy_notice' not in APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/').json()
    assert APIClient().post(f'/api/przeszlosc/osoba/{anna.pk}/sprzeciw/', {}, format='json').status_code == 404
    settings.PRZESZLOSC_PRIVACY_NOTICE_ENABLED = True
    notice = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/').json()['privacy_notice']
    assert notice['version'] == 'art14-szkic-1' and notice['status'] == 'szkic do prawnika' and notice['date'] == '2026-10-13'
    text = ' '.join(s['text'] for s in notice['sections'])
    assert 'iapply sp. z o.o.' in text and 'art. 21' in text and 'kontakt@iapply.pl' in text


def test_objection_queue_confirm_and_decision(settings):
    settings.PRZESZLOSC_PRIVACY_NOTICE_ENABLED = True
    anna = mp('Anna A', 1)
    response = APIClient().post(f'/api/przeszlosc/osoba/{anna.pk}/sprzeciw/', {
        'reason': 'Proszę o usunięcie danych o funkcji w spółce, którą pełniłam przed mandatem.', 'contact': 'anna@example.com',
        'relation': 'osoba'}, format='json')
    assert response.status_code == 202 and len(mail.outbox) == 1
    token = mail.outbox[0].body.split('/potwierdz/')[1].split('/')[0]
    assert APIClient().get(f'/api/przeszlosc/sprzeciw/potwierdz/{token}/').json() == {'status': 'confirmed'}
    assert APIClient().get(f'/api/przeszlosc/sprzeciw/potwierdz/{token}/').status_code == 410  # replay
    row = DataObjection.objects.get()
    assert row.status == 'potwierdzony' and row.notice_version == 'art14-szkic-1'
    get_user_model().objects.create_user('ido', password='x', is_staff=True)
    with pytest.raises(CommandError):
        call_command('sprzeciwy', 'rozpatrz', str(row.pk), '--decyzja', 'odrzucony', '--uwaga', ' ', '--kto', 'ido')
    call_command('sprzeciwy', 'rozpatrz', str(row.pk), '--decyzja', 'odrzucony', '--uwaga', 'Funkcja publiczna z KRS.', '--kto', 'ido')
    row.refresh_from_db()
    assert row.status == 'odrzucony' and row.decision_sent_at and 'UODO' in mail.outbox[-1].body
    assert APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/').status_code == 200  # bez automatycznego usuwania


# --- 3. odpowiedź osoby i powiadomienie o wycofaniu ------------------------------------------------------------------------

def test_subject_response_only_from_verified_and_public_after_decision(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    url = f'/api/stanowiska/{pair.pk}/odpowiedz/'
    text = 'Zmiana stanowiska wynikała z nowych danych o finansach gmin, o czym mówiłam publicznie w marcu.'
    assert APIClient().post(url, {'text': text}, format='json').status_code == 403
    office = get_user_model().objects.create_user('biuro', password='x')
    VerifiedReporter.objects.create(user=office, figure=figure, role='przedstawiciel', evidence='pismo')
    client = APIClient()
    client.force_authenticate(office)
    assert client.post(url, {'text': text}, format='json').status_code == 202
    row = SubjectResponse.objects.get()
    assert row.status == 'zgloszona' and row.via == 'verified_reporter'
    profile = f'/api/przeszlosc/osoba/{figure.pk}/stanowiska/'
    assert APIClient().get(profile).json()['items'][0]['subject_response'] is None
    staff('bez_prawa', decide=False)
    with pytest.raises(CommandError):
        call_command('pary_stanowisk', 'odpowiedz-opublikuj', str(row.pk), '--kto', 'bez_prawa')
    staff('dyzurny')
    call_command('pary_stanowisk', 'odpowiedz-opublikuj', str(row.pk), '--kto', 'dyzurny')
    shown = APIClient().get(profile).json()['items'][0]['subject_response']
    assert shown == {'label': 'Odpowiedź osoby', 'text': text, 'date': timezone.localdate().isoformat()}


def test_subject_response_via_confirmed_official_email(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = pp.approve(candidate(figure, old, new), staff())
    row, _ = pp.report(pair, 'Wypowiedź dotyczyła innego projektu ustawy.', 'biuro@sejm.gov.pl', True)
    confirm_token = mail.outbox[-1].body.split('/potwierdz/')[1].split('/')[0]
    assert row.confirm_token == hashlib.sha256(confirm_token.encode()).hexdigest()  # w bazie tylko skrót
    with pytest.raises(pp.PairError):
        pp.submit_response(pair, 'Odpowiedź osoby z biura poselskiego.', token=confirm_token)  # token potwierdzenia to nie token odpowiedzi
    pp.confirm_report(confirm_token)
    pair.refresh_from_db()
    assert pair.status == 'suggested'  # adres urzędowy zdejmuje parę
    pp.approve(pair, staff('drugi'), 'Sprawdzono: ten sam projekt.')
    import re
    response_token = next(re.search(r'pole token\): (\S+)', m.body).group(1) for m in mail.outbox if 'pole token' in m.body)
    pair.refresh_from_db()
    response = pp.submit_response(pair, 'Odpowiedź osoby z biura poselskiego.', token=response_token)
    assert response.via == 'official_email' and response.report_id == row.pk
    with pytest.raises(pp.PairError):  # token odpowiedzi jednorazowy
        pp.submit_response(pair, 'Druga odpowiedź tym samym kodem.', token=response_token)
    with pytest.raises(pp.PairError) as error:  # link potwierdzający jednorazowy (replay)
        pp.confirm_report(confirm_token)
    assert error.value.code == 'used'


def test_withdrawal_notifies_only_previously_notified(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    reader = get_user_model().objects.create_user('czytelnik', password='x')
    Follow.objects.create(user=reader, figure=figure, mode='posts')
    pair = pp.approve(candidate(figure, old, new), staff())
    late = get_user_model().objects.create_user('pozniej', password='x')
    Follow.objects.create(user=late, figure=figure, mode='posts')  # zaczął obserwować po publikacji pary
    pp.withdraw(pair, staff('drugi'), 'Cytat dotyczył innego projektu.')
    notes = Notification.objects.filter(kind='position_pair_withdrawn')
    assert list(notes.values_list('user__username', flat=True)) == ['czytelnik']
    assert notes.get().title == 'Zestawienie wycofane: podatek od nieruchomości. Powód: Cytat dotyczył innego projektu.'


# --- 4. oświadczenia majątkowe ---------------------------------------------------------------------------------------------

def tiny_pdf() -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def index_record(anna, url, context='za rok 2024 złożone 30.04.2025', title='Oświadczenie majątkowe'):
    from news.public_records_models import PublicRecord, PublicRecordPerson
    record = PublicRecord.objects.create(source='assets', kind='asset_document', external_id=f'10/1/{hashlib.sha256(url.encode()).hexdigest()}',
                                         source_url=url, response_sha256='d' * 64, response_url='https://www.sejm.gov.pl', term=10,
                                         title=title, data={'url': url, 'title': title, 'context': context, 'year': 2024,
                                                            'year_status': 'reported', 'mp_id': 1, 'name': 'Anna A'})
    PublicRecordPerson.objects.create(record=record, term=10, mp_id=1, figure=None)
    return record


class FakeResponse:
    def __init__(self, status, body=b'', headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def iter_content(self, size):
        yield self.body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, timeout=None, stream=None):
        self.calls.append((url, dict(headers or {})))
        return self.responses.pop(0)


def test_sync_fetch_and_profile_block(settings):
    anna = mp('Anna A', 1)
    url = 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp/oswiadczenia/001_2024.pdf'
    index_record(anna, url)
    index_record(anna, 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp/oswiadczenia/001_2024_k.pdf', title='Korekta oświadczenia')
    index_record(anna, 'https://evil.example/a.pdf')
    with pytest.raises(CommandError):
        call_command('oswiadczenia', 'synchronizuj')  # flaga wyłączona
    settings.ASSETS_DECLARATIONS_ENABLED = True
    assert ad.sync() == {'created': 3, 'updated': 0}
    decl = AssetDeclaration.objects.get(url=url)
    assert decl.figure == anna and decl.year == 2024 and decl.kind == 'oswiadczenie' and decl.published_on == date(2025, 4, 30)
    assert AssetDeclaration.objects.get(url__endswith='_k.pdf').kind == 'korekta'
    pdf = tiny_pdf()
    session = FakeSession([FakeResponse(404), FakeResponse(200, pdf, {'ETag': '"abc"'}), FakeResponse(200, pdf)])  # robots 404 = brak ograniczeń
    assert ad.fetch_metadata(limit=10, delay=0, session=session) == {'fetched': 2, 'unchanged': 0, 'errors': 1}
    decl.refresh_from_db()
    assert decl.sha256 == hashlib.sha256(pdf).hexdigest() and decl.etag == '"abc"' and decl.auto_read['status'] == 'skan bez warstwy tekstu'
    from urllib.parse import urlsplit
    assert all(urlsplit(c[0]).hostname == 'www.sejm.gov.pl' for c in session.calls)  # adres spoza Sejmu nie był pobierany
    AssetDeclaration.objects.update(fetched_at=timezone.now() - timedelta(days=31))
    session = FakeSession([FakeResponse(304), FakeResponse(304)])
    assert ad.fetch_metadata(limit=10, delay=0, session=session)['unchanged'] == 2
    assert session.calls[0][1].get('If-None-Match') == '"abc"'
    block = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/').json()['assets_declarations']
    first = next(item for item in block['items'] if item['url'] == url)
    assert first['url'].startswith('https://') and first['auto_read']['note'] == ad.AUTO_READ_NOTE
    assert 'nie porównujemy' in block['notice'] and 'informacja publiczna' in block['source']['license']
    assert not any(key in first for key in ('total', 'change', 'score', 'rank'))


def test_assets_absent_when_flag_off():
    anna = mp('Anna A', 1)
    assert 'assets_declarations' not in APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/').json()


# --- 5. pilotaż ------------------------------------------------------------------------------------------------------------

@pytest.fixture
def out_dir():
    path = Path(django_settings.BASE_DIR) / 'tmp' / 'pilotaz-test'
    shutil.rmtree(path, ignore_errors=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_pilot_pairs_balanced_sheet_and_report(out_dir):
    from news.test_position_pairs import x_account_in
    from news.test_przeszlosc_osoba import x_post
    from news.test_position_pairs import NEW, OLD
    for name, mp_id, handle, uid, camp in (('Anna A', 1, 'anna_a', '601', 'government'), ('Bartek B', 2, 'bartek_b', '602', 'opposition')):
        figure = mp(name, mp_id)
        account = x_account_in(figure, handle, uid, camp)
        old, new = x_post(account, uid + '1', OLD, days_ago=200), x_post(account, uid + '2', NEW, days_ago=2)
        candidate(figure, old, new)
    result = pilotaz.pairs(2, dry_run=True, path=out_dir)
    assert result['by_camp'] == {'government': 1, 'opposition': 1} and result['log']['calls'] == 0
    with open(result['csv'], encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    assert len(rows) == 2 and rows[0]['A'] and rows[0]['zrodlo_B'].startswith('https://x.com/')
    rows[0].update(decyzja='tak', powod='ok', czas_s='120')
    rows[1].update(decyzja='nie', powod='kontekst', czas_s='300')
    with open(result['csv'], 'w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=pilotaz.PAIR_COLUMNS, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    report = pilotaz.report(result['csv'], 'par')
    assert report['reviewed'] == 2 and report['blocking_rate'] == 0.5 and report['accepted'] is False
    assert report['time_median_s'] == 210.0 and set(report['camps']) == {'government', 'opposition'}
    assert Path(report['md']).exists() and PositionPair.objects.filter(status='suggested').count() == 2  # nic nie opublikowano
    call_command('pilotaz', 'raport', '--plik', result['csv'])


def test_pilot_chains_dry_run(out_dir):
    from news import causal_chain
    from news.test_spina_v3 import fake_ask, good_steps, make_message
    message, _ = make_message()
    message.day = timezone.localdate() - timedelta(days=1)
    message.save()
    causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    result = pilotaz.chains(20, dry_run=True, path=out_dir)
    assert result['chains'] == 1 and result['calls'] == 0
    with open(result['csv'], encoding='utf-8-sig', newline='') as handle:
        row = next(csv.DictReader(handle, delimiter=';'))
    assert row['oboz'] == 'government' and 'fakt:' in row['kroki']
    call_command('pilotaz', 'lancuch', '--dni', '20', '--dry-run', '--wyjscie', str(out_dir))


# --- recenzja Codex 3: testy regresyjne -------------------------------------------------------------------------------------

def test_response_only_to_public_pair(settings):
    settings.POSITION_PAIRS_ENABLED = True
    figure, old, new = person()
    pair = candidate(figure, old, new)  # kandydat, niepubliczny
    office = get_user_model().objects.create_user('biuro', password='x')
    VerifiedReporter.objects.create(user=office, figure=figure, role='przedstawiciel', evidence='pismo')
    client = APIClient()
    client.force_authenticate(office)
    url = f'/api/stanowiska/{pair.pk}/odpowiedz/'
    missing = client.post(f'/api/stanowiska/{pair.pk + 999}/odpowiedz/', {'text': 'Odpowiedź do pary.'}, format='json')
    hidden = client.post(url, {'text': 'Odpowiedź do niepublicznej pary.'}, format='json')
    assert hidden.status_code == missing.status_code == 404 and hidden.json() == missing.json()  # bez enumeracji
    pair.approved_at = timezone.now()
    pair.save()  # zatwierdzona kiedyś, teraz zdjęta (status suggested)
    with pytest.raises(pp.PairError):
        pp.submit_response(pair, 'Odpowiedź do zdjętej pary.', user=office)


def test_objection_neutral_for_unknown_profile_and_retention(settings):
    settings.PRZESZLOSC_PRIVACY_NOTICE_ENABLED = True
    anna = mp('Anna A', 1)
    body = {'reason': 'Proszę o sprawdzenie danych w profilu, opis funkcji jest nieaktualny.', 'contact': 'x@example.com',
            'relation': 'osoba'}
    known = APIClient().post(f'/api/przeszlosc/osoba/{anna.pk}/sprzeciw/', body, format='json')
    unknown = APIClient().post('/api/przeszlosc/osoba/999999-nikt/sprzeciw/', body, format='json')
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    ghost = DataObjection.objects.get(ident='999999-nikt')
    assert ghost.figure is None and len(ghost.confirm_token) == 64 and ghost.token_expires_at
    row = DataObjection.objects.get(figure=anna)
    row.status, row.decided_at = 'odrzucony', timezone.now() - timedelta(days=91)
    row.save()
    call_command('sprzeciwy', 'czysc')
    row.refresh_from_db()
    assert row.contact == '' and row.confirm_token == '' and row.reason


def test_objection_token_expires(settings):
    settings.PRZESZLOSC_PRIVACY_NOTICE_ENABLED = True
    anna = mp('Anna A', 1)
    APIClient().post(f'/api/przeszlosc/osoba/{anna.pk}/sprzeciw/', {
        'reason': 'Proszę o sprawdzenie danych w profilu, opis funkcji jest nieaktualny.', 'contact': 'x@example.com',
        'relation': 'osoba'}, format='json')
    token = mail.outbox[-1].body.split('/potwierdz/')[1].split('/')[0]
    DataObjection.objects.update(token_expires_at=timezone.now() - timedelta(minutes=1))
    assert APIClient().get(f'/api/przeszlosc/sprzeciw/potwierdz/{token}/').status_code == 410
    assert APIClient().get('/api/przeszlosc/sprzeciw/potwierdz/zly-token/').status_code == 404


class TextResponse(FakeResponse):
    def __init__(self, status, text=''):
        super().__init__(status)
        self.text = text


def test_robots_disallow_and_fail_closed(settings):
    settings.ASSETS_DECLARATIONS_ENABLED = True
    anna = mp('Anna A', 1)
    index_record(anna, 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp/oswiadczenia/001_2024.pdf')
    ad.sync()
    session = FakeSession([TextResponse(200, 'User-agent: *\nDisallow: /sejm10.nsf/')])
    assert ad.fetch_metadata(limit=5, delay=0, session=session) == {'fetched': 0, 'unchanged': 0, 'errors': 1}
    assert AssetDeclaration.objects.get().fetch_error == 'robots.txt zabrania pobrania' and len(session.calls) == 1
    cache.clear()
    AssetDeclaration.objects.update(fetched_at=None, fetch_error='')
    result = ad.fetch_metadata(limit=5, delay=0, session=FakeSession([TextResponse(503)]))
    assert result['stopped'].startswith('robots.txt niedostępny') and AssetDeclaration.objects.get().fetched_at is None


def test_size_limits_before_and_during_download(settings):
    settings.ASSETS_DECLARATIONS_ENABLED = True
    anna = mp('Anna A', 1)
    index_record(anna, 'https://www.sejm.gov.pl/a/001_2024.pdf')
    index_record(anna, 'https://www.sejm.gov.pl/a/001_2023.pdf', context='za rok 2023 złożone 30.04.2024')
    ad.sync()

    class Big(FakeResponse):
        closed = False

        def iter_content(self, size):
            for _ in range(5):
                yield b'%PDF-' + b'x' * (ad.MAX_BYTES // 3)

        def close(self):
            Big.closed = True
    declared = FakeResponse(200, b'', {'Content-Length': str(ad.MAX_BYTES + 1)})
    declared.iter_content = lambda size: (_ for _ in ()).throw(AssertionError('treść nie powinna być pobierana'))
    session = FakeSession([TextResponse(404), declared, Big(200)])
    assert ad.fetch_metadata(limit=5, delay=0, session=session)['errors'] == 2
    assert set(AssetDeclaration.objects.values_list('fetch_error', flat=True)) == {'ValueError: pdf_too_large'} and Big.closed
    assert ad.TIMEOUT == (5, 20)


def test_domain_normalization_idna_and_edge_cases(settings):
    assert od.normalize('Sejm.Gov.PL.') == 'sejm.gov.pl' and od.normalize('https://www.Senat.gov.pl/kontakt') == 'senat.gov.pl'
    assert od.normalize('ZAŻÓŁĆ.pl') == 'zażółć.pl'.encode('idna').decode('ascii') and od.normalize('zażółć.pl').startswith('xn--')
    with pytest.raises(ValueError):
        od.normalize('')
    od.change('zażółć.pl', 'add', kind='partia', source='test', by='t')
    assert od.match('Biuro@ZAŻÓŁĆ.pl') == od.normalize('zażółć.pl') and od.match('x@sejm.gov.pl.') == 'sejm.gov.pl'
    assert od.match('x@notsejm.gov.pl') is None and od.match('x@sejm.gov.pl.evil.com') is None and od.match('') is None
    settings.POSITION_PAIR_OFFICIAL_DOMAINS = ['', '  ', 'zła domena', 'ok.gov.pl']
    assert 'ok.gov.pl' in od.domains() and '' not in od.domains()


def test_pilot_round_robin_all_camps():
    by_camp = {'government': list('abc'), 'opposition': list('def'), 'brak konta': list('gh')}
    for n in (3, 5):
        counts = {}
        for camp, _ in pilotaz.round_robin(by_camp, n):
            counts[camp] = counts.get(camp, 0) + 1
        assert sum(counts.values()) == n and max(counts.values()) - min(counts.values()) <= 1
        assert set(counts) == set(by_camp) if n >= 3 else True  # żaden obóz nie jest pomijany
    assert len(pilotaz.round_robin({'government': ['a'], 'opposition': []}, 5)) == 1


def test_pilot_report_rejects_missing_or_unknown_reasons(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / 'arkusz.csv'

    def write(rows):
        with open(path, 'w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=pilotaz.PAIR_COLUMNS, delimiter=';')
            writer.writeheader()
            writer.writerows([{c: r.get(c, '') for c in pilotaz.PAIR_COLUMNS} for r in rows])
    write([{'id': 1, 'oboz': 'government', 'decyzja': 'nie', 'powod': ''}])
    with pytest.raises(pilotaz.ReportError):
        pilotaz.report(path, 'par')
    write([{'id': 1, 'oboz': 'government', 'decyzja': 'nie', 'powod': 'ok'}])
    with pytest.raises(pilotaz.ReportError):
        pilotaz.report(path, 'par')
    write([{'id': 1, 'oboz': 'government', 'decyzja': 'może', 'powod': 'ok'}])
    with pytest.raises(CommandError):
        call_command('pilotaz', 'raport', '--plik', str(path))
    write([{'id': 1, 'oboz': 'government', 'decyzja': 'nie', 'powod': 'jezyk'}, {'id': 2, 'oboz': 'opposition', 'decyzja': 'tak'}])
    chain = pilotaz.report(path, 'lancuch')
    assert chain['blocking_rejected'] == 0 and chain['rejected'] == 1

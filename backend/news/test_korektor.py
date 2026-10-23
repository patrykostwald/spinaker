from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from news import korektor, urzedy

AFTER = date(2026, 10, 22)
BEFORE = date(2024, 5, 1)


def test_registry_entries_have_sources_and_unsure_stay_out():
    for row in urzedy.URZEDY:
        assert row.zrodlo.startswith('https://'), row.klucz
    assert urzedy.urzad('prezydent').osoba == 'Karol Nawrocki'
    assert urzedy.urzad('prezydent').od == date(2025, 8, 6)
    assert urzedy.urzad('lider-polska-2050') is None  # [DP]
    block = urzedy.blok(AFTER)
    assert 'Aktualne urzędy na dzień 22.10.2026' in block
    assert 'Prezydent RP: Karol Nawrocki' in block
    assert 'Andrzej Duda - Prezydent RP 2015-2025' in block
    assert 'Konwiński' not in block  # [DP] nie trafia do promptu


@pytest.mark.parametrize('text', [
    'Prezydent Andrzej Duda zawetował ustawę.',
    'Rozmowa z prezydentem Dudą o wecie.',
    'Andrzej Duda (Prezydent RP) w Kanale Zero',
    'Prezydent RP Andrzej Duda',
    'Spotkanie z premierem Morawieckim w Sejmie.',
    'Marszałek Sejmu Szymon Hołownia otworzył posiedzenie.',
    'Minister sprawiedliwości Adam Bodnar zapowiedział zmiany.',
])
def test_former_holder_with_office_after_change_is_an_error(text):
    errors = korektor.bledy_urzedu(text, AFTER)
    assert errors and errors[0]['rodzaj'] == 'urzad'


@pytest.mark.parametrize('text', [
    'Prezydent Karol Nawrocki zawetował ustawę.',
    'Były prezydent Andrzej Duda skomentował weto.',
    'Ówczesny prezydent Andrzej Duda podpisał ustawę w 2020 r.',
    'Andrzej Duda, były prezydent, w rozmowie.',
    'Premier Donald Tusk i marszałek Sejmu Włodzimierz Czarzasty.',
    'Wicepremier Kosiniak-Kamysz o armii.',
    'Prezydent Warszawy Rafał Trzaskowski.',
    # recenzja integracji 23.10: urząd przy innej osobie, okres, inna instytucja, imiennik
    'Andrzej Duda, prezydent Karol Nawrocki i premier Donald Tusk.',
    'Szymon Hołownia, marszałek Sejmu Włodzimierz Czarzasty i inni.',
    'Morawiecki - premier w latach 2017-2023.',
    'Piotr Duda, prezydent związku, zapowiedział protest.',
])
def test_correct_or_marked_former_is_fine(text):
    assert korektor.bledy_urzedu(text, AFTER) == []


def test_text_from_the_term_is_fine():
    assert korektor.bledy_urzedu('Prezydent Andrzej Duda zawetował ustawę.', BEFORE) == []


def test_other_person_swaps():
    errors = korektor.bledy_urzedu('Prezydent Donald Tusk spotkał się z premierem Nawrockim.', AFTER)
    assert {(e['napisano'], e['powinno']) for e in errors} == {('Donald Tusk', 'Karol Nawrocki'), ('Karol Nawrocki', 'Donald Tusk')}


def _interview(**fields):
    from news.clinic_models import ClinicInterview
    defaults = dict(url='https://www.youtube.com/watch?v=abcdefghijk', video_id='abcdefghijk', day=AFTER,
                    title='Prezydent Karol Nawrocki: rozmowa o wecie | Gość Wydarzeń', channel='Polsat News',
                    guest_name='Andrzej Duda', guest_role='Prezydent RP', host_name='Piotr Witwicki', status='approved',
                    headline='Karol Nawrocki o wecie: oceny przedstawione jako fakty', summary='Prezydent Andrzej Duda bronił weta.',
                    transcript='[00:01] GOŚĆ: tekst')
    defaults.update(fields)
    return ClinicInterview.objects.create(**defaults)


@pytest.mark.django_db
def test_regression_nawrocki_interview_signed_as_duda():
    """Wpadka 22.10: wywiad z prezydentem Nawrockim podpisany jako „Andrzej Duda”."""
    row = _interview()
    errors = korektor.bledy_wywiadu(row)
    kinds = {(e['rodzaj'], e.get('pole')) for e in errors}
    assert ('gosc', 'guest_name') in kinds and ('gosc', 'guest') in kinds and ('urzad', None) in kinds
    changed = korektor.popraw_goscia(row)
    row.refresh_from_db()
    assert changed == ['guest_name']  # rola „Prezydent RP” już była właściwa
    assert row.guest_name == 'Karol Nawrocki' and row.guest_role == 'Prezydent RP'
    assert not [e for e in korektor.bledy_wywiadu(row) if e['rodzaj'] == 'gosc']


@pytest.mark.django_db
def test_guest_named_in_title_is_not_replaced():
    """„Bosak: Tusk musi odejść” - gość Bosak zostaje, choć tytuł wymienia tylko Tuska z rejestru."""
    row = _interview(title='Bosak: Tusk musi odejść | Gość Wydarzeń', guest_name='Krzysztof Bosak', guest_role='',
                     headline='Bosak o rządzie', summary='Krzysztof Bosak krytykuje rząd.')
    assert not [e for e in korektor.bledy_wywiadu(row) if e.get('pole') == 'guest_name']
    assert korektor.popraw_goscia(row) == [] and row.guest_name == 'Krzysztof Bosak'


@pytest.mark.django_db
def test_guest_role_cleared_without_title_evidence():
    row = _interview(title='Rozmowa dnia | Gość Wydarzeń', headline='Rozmowa o wecie', summary='')
    korektor.popraw_goscia(row)
    row.refresh_from_db()
    assert row.guest_name == 'Andrzej Duda' and row.guest_role == ''


@pytest.mark.django_db
def test_interview_gate_holds_wrong_office_text(monkeypatch):
    from news import clinic_interview
    row = _interview()
    result = {'headline': row.headline, 'summary': 'Prezydent Andrzej Duda znów bronił weta.', 'overall': '',
              'guest_analysis': {}, 'host_analysis': {}, 'limitations': '', 'usage': {}}
    calls = []
    monkeypatch.setattr(clinic_interview, 'diagnose_transcript', lambda meta, text: calls.append(meta) or dict(result))
    clinic_interview._gate(row)
    assert len(calls) == 1 and calls[0]['guest_name'] == 'Karol Nawrocki'  # ponowiona raz, już z poprawnym gościem
    assert row.status == 'flagged' and row.error.startswith(korektor.PREFIX)


@pytest.mark.django_db
def test_interview_gate_passes_after_good_rediagnosis(monkeypatch):
    from news import clinic_interview
    row = _interview()
    good = {'headline': 'Karol Nawrocki o wecie', 'summary': 'Prezydent Karol Nawrocki bronił weta.', 'overall': '',
            'guest_analysis': {}, 'host_analysis': {}, 'limitations': '', 'usage': {}}
    monkeypatch.setattr(clinic_interview, 'diagnose_transcript', lambda meta, text: dict(good))
    clinic_interview._gate(row)
    assert row.status == 'approved' and row.summary == good['summary'] and row.guest_name == 'Karol Nawrocki'


def test_transcript_prompt_carries_offices_and_hint():
    from news.clinic_interview import transcript_prompt
    prompt = transcript_prompt('Polsat News: Prezydent Karol Nawrocki')
    assert 'Prezydent RP: Karol Nawrocki' in prompt and 'nie zgaduj' in prompt and 'Polsat News' in prompt


def _diagnosis(text_summary, published=None):
    from news.clinic_models import SpinDiagnosis
    from news.political_models import PoliticalAccount, PoliticalPost
    account = PoliticalAccount.objects.create(handle='NawrockiKn', display_name='Karol Nawrocki', user_id='1', camp='opposition')
    post = PoliticalPost.objects.create(account=account, post_id='1', camp_at_collection='opposition', response_sha256='0' * 64, text='Wpis', url='https://x.com/NawrockiKn/status/1',
                                        published_at=published or timezone.now())
    return SpinDiagnosis.objects.create(post=post, status='approved', headline='Weto', summary=text_summary,
                                        diagnosed_at=timezone.now())


@pytest.mark.django_db
def test_diagnosis_gate_requeues_once_then_waits_for_human():
    row = _diagnosis('Prezydent Andrzej Duda pisze o wecie.')
    row.usage = {'snapshot': {'x': 1}}
    assert korektor.bramka_diagnozy(row)
    assert row.status == 'queued' and row.repair_attempts == 1 and 'snapshot' not in row.usage
    assert korektor.bramka_diagnozy(row)
    assert row.status == 'pending_review'


@pytest.mark.django_db
def test_daily_message_check():
    assert korektor.bledy_przekazu({'message': 'Obóz broni prezydenta Dudy.', 'points': []}, AFTER)
    assert not korektor.bledy_przekazu({'message': 'Obóz broni prezydenta Nawrockiego.', 'points': []}, AFTER)


@pytest.mark.django_db
def test_command_reports_and_repairs(monkeypatch, tmp_path):
    row = _interview(day=timezone.localdate() - timedelta(days=1), repair_attempts=1)
    _diagnosis('Prezydent Andrzej Duda pisze o wecie.')
    monkeypatch.setattr(korektor, 'OSOBY_X', tmp_path / 'brak.csv')
    out = StringIO()
    call_command('korektor', '--dni', '3', stdout=out)
    text = out.getvalue()
    assert 'wywiady 1, diagnozy 1' in text and 'Brak listy zweryfikowanej' in text and 'Andrzej Duda' in text
    call_command('korektor', '--dni', '3', '--napraw', stdout=StringIO())
    row.refresh_from_db()
    assert row.guest_name == 'Karol Nawrocki' and row.status == 'flagged'  # treść z błędem wstrzymana (limit ponowień)
    from news.clinic_models import SpinDiagnosis
    assert SpinDiagnosis.objects.get().status == 'queued'


@pytest.mark.django_db
def test_x_list_reading(tmp_path):
    from news.political_models import PublicFigure
    figure = PublicFigure.objects.create(canonical_name='Marek Jakubiak', role_category='parliamentary', role_title='Poseł',
                                         import_key='test:jakubiak')
    path = tmp_path / 'osoby_x.csv'
    path.write_text('imie_nazwisko,id,konto,zrodlo,data,pewnosc\n'
                    f'Marek Jakubiak,{figure.pk},@MarekJakubiak,https://www.wikidata.org/wiki/Q1,2026-10-23,wysoka\n'
                    f'Ktoś Niepewny,{figure.pk},@cos,https://example.org,2026-10-23,niska\n', encoding='utf-8')
    result = korektor.braki_x(path)
    assert result['sprawdzone'] == 1 and result['braki'][0]['konto'] == 'MarekJakubiak'
    # format osoby_x.csv z gałęzi osoby-x: osoba_id = klucz osoby (import_key), nie numer
    keyed = tmp_path / 'osoby_x_klucz.csv'
    keyed.write_text('imie_nazwisko,osoba_id,konto,zrodlo,data_sprawdzenia,pewnosc,stan_konta,uwagi\n'
                     'Marek Jakubiak,test:jakubiak,MarekJakubiak,https://www.sejm.gov.pl/x,2026-10-23,wysoka,aktualne,\n', encoding='utf-8')
    assert [b['id'] for b in korektor.braki_x(keyed)['braki']] == [figure.pk]


@pytest.mark.django_db
def test_task_and_mail(monkeypatch, tmp_path):
    from news.tasks import korektor_task
    monkeypatch.setattr(korektor, 'OSOBY_X', tmp_path / 'brak.csv')
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'koordynator@example.org')
    with patch('news.social_publish._mail', return_value=True) as mail:
        result = korektor_task()
        assert result['status'] == 'ok' and result['mail'] == 'ok'
        assert korektor_task()['mail'] == 'already_run'
    assert mail.call_count == 1 and 'Korektor' in mail.call_args[0][1]
    monkeypatch.setenv('KOREKTOR_ENABLED', 'false')
    assert korektor_task() == {'status': 'disabled'}


@pytest.mark.django_db
def test_x_decision_queue_shows_only_conflicts_with_proposal():
    from django.contrib.contenttypes.models import ContentType
    from news.political_models import PoliticalAccountCandidate, PublicFigure, SocialHandleEvidence
    figure = PublicFigure.objects.create(canonical_name='Tomasz Głogowski', role_category='parliamentary', role_title='Poseł',
                                         import_key='test:glogowski')
    PoliticalAccountCandidate.objects.all().delete()  # migracje wstawiają kandydatury startowe
    party = PoliticalAccountCandidate.objects.create(handle='Platforma_org', display_name='Platforma Obywatelska',
                                                     classification='government',
                                                     resolution_error='Strażnik: Konto powiązano już z innym profilem; do decyzji.')
    SocialHandleEvidence.objects.create(platform='x', handle='Platforma_org', candidate=party, evidence_url='https://www.sejm.gov.pl/x',
                                        subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk)
    PoliticalAccountCandidate.objects.create(handle='JanNowak', display_name='Jan Nowak', classification='independent',
                                             resolution_error='Strażnik: Brak jednoznacznego obozu w oficjalnym rejestrze.')
    queue = korektor.do_decyzji()
    assert queue['czeka'] == 2 and len(queue['konflikty']) == 1
    assert queue['konflikty'][0]['osoby'] == ['Tomasz Głogowski'] and 'konto partii' in queue['konflikty'][0]['propozycja']


@pytest.mark.django_db
def test_x_decision_queue_includes_warden_conflicts_once():
    from news.account_warden import STATE
    from news.models import ImportState
    from news.political_models import PoliticalAccountCandidate
    PoliticalAccountCandidate.objects.all().delete()
    ImportState.objects.update_or_create(name=STATE, defaults={'cursor': {'report': {'conflicts': [
        {'name': 'Anna Kowalska', 'handle': 'akowalska', 'source': 'https://www.sejm.gov.pl/a',
         'reason': 'Konflikt dowodów: konto przy innej osobie.', 'proposal': 'przypiąć do: Anna Kowalska'},
        {'name': 'Anna Kowalska', 'handle': 'AKowalska', 'source': 'https://www.sejm.gov.pl/a', 'reason': 'x', 'proposal': 'y'},
    ]}}})
    queue = korektor.do_decyzji()
    assert [c['konto'] for c in queue['konflikty']] == ['akowalska'] and queue['konflikty'][0]['straznik']
    report = {'dzien': '2026-10-23', 'dni': 2, 'napraw': False, 'wywiady': [], 'diagnozy': [], 'przekazy': [],
              'konta_x': {'dostepna': False, 'lista': 'osoby_x.csv'}, 'kolejka_x': queue, 'przyczyna': '',
              'profile': {'osoby': 0, 'liczby': {k: 0 for k in korektor.SECTIONS}, 'listy': {k: [] for k in korektor.SECTIONS}},
              'podsumowanie': {'wywiady': 0, 'diagnozy': 0, 'przekazy': 0}}
    body = korektor.text(report)
    assert '@akowalska, osoby: Anna Kowalska, Strażnik ostatniej nocy -> przypiąć do: Anna Kowalska · https://www.sejm.gov.pl/a' in body

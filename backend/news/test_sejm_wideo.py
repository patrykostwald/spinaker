"""Wystąpienia z nagrań Sejmu -> Dr. Spin: wybór tą samą miarą, sekunda nagrania, kworum Konsylium. Bez sieci."""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from news import clinic_ai, sejm_wideo
from news.political_models import ParliamentaryRosterEntry, PublicFigure
from news.public_records_models import PublicRecord, PublicRecordPerson
from news.zrodla_models import SejmVideoSpin

pytestmark = pytest.mark.django_db
DAY = date(2026, 10, 5)
WORDS = ' '.join(['słowo'] * 200)


def fake(verdict='spin', intensity=60):
    return {'verdict': verdict, 'intensity': intensity, 'headline': 'Liczba bez kontekstu', 'summary': 'Krótko.',
            'analysis': 'Dłużej.', 'limitations': '', 'claims': [], 'usage': {'model': 'konsylium: a, b'},
            'techniques': [{'name': 'fałszywa alternatywa', 'quote': 'x', 'explanation': 'y'}]}


def mp(name, mp_id):
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id=str(mp_id), full_name=name, term=10, club='KO',
                                                    source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    return PublicFigure.objects.create(canonical_name=name, role_category='parliament', role_title='Poseł na Sejm RP',
                                       evidence_url='https://api.sejm.gov.pl/', parliamentary_roster_entry=entry)


def record(source, kind, key, text, data, figure=None, mp_id=1):
    row = PublicRecord.objects.create(source=source, kind=kind, external_id=key, date=DAY, text=text, title=key, data=data,
                                      source_url='https://api.sejm.gov.pl/sejm/term10/x', response_url='https://api.sejm.gov.pl/x',
                                      response_sha256='0')
    if figure:
        PublicRecordPerson.objects.create(record=row, term=10, mp_id=mp_id, figure=figure)
    return row


@pytest.fixture
def sejm(monkeypatch):
    monkeypatch.setenv('SEJM_VIDEO_SPIN_ENABLED', 'true')
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    monkeypatch.setenv('CLINIC_AI_PROVIDER', 'claude')
    monkeypatch.setattr(clinic_ai, 'provider', lambda: 'claude')
    a, b, c = mp('Anna Długa', 1), mp('Bartosz Krótki', 2), mp('Celina Komisja', 3)
    record('videos', 'video', 'V' * 32, '', {'unid': 'V' * 32, 'type': 'posiedzenie', 'start': '2026-10-05T09:00:00',
                                              'end': '2026-10-05T20:00:00', 'player': 'https://sejm.gov.pl/Sejm10.nsf/transmisje_arch.xsp?unid=V'})
    record('statements', 'statement', '10/40/2026-10-05/5', WORDS + ' ' + WORDS,
           {'startDateTime': '2026-10-05T10:01:05', 'function': 'Poseł', 'memberID': 1}, a, 1)
    record('statements', 'statement', '10/40/2026-10-05/6', WORDS,
           {'startDateTime': '2026-10-05T11:00:00', 'function': 'Poseł', 'memberID': 2}, b, 2)
    record('statements', 'statement', '10/40/2026-10-05/7', WORDS * 3,
           {'startDateTime': '2026-10-05T12:00:00', 'function': 'Wicemarszałek', 'memberID': 2}, b, 2)
    record('statements', 'statement', '10/40/2026-10-05/8', 'krótko', {'startDateTime': '2026-10-05T12:30:00'}, c, 3)
    record('videos', 'committee_speech', 'ASW/7/2', WORDS + ' dodatkowe', {
        'unid': 'U' * 32, 'player': 'https://sejm.gov.pl/p', 'video_start': '2026-10-05T10:00:00',
        'video_end': '2026-10-05T12:00:00', 'position': 0.5, 'committee': 'Komisja Administracji'}, c, 3)
    return a, b, c


def test_candidates_same_measure_exact_second_and_estimate(sejm):
    a, b, c = sejm
    rows = sejm_wideo.candidates(DAY)
    assert [r['figure'] for r in rows] == [a, c, b]  # tylko długość; wicemarszałek i krótkie pominięte
    first = rows[0]
    assert first['place'] == 'sala' and first['exact'] and first['offset'] == 3665
    committee = rows[1]
    assert committee['place'] == 'komisja' and not committee['exact'] and committee['offset'] == 3600
    assert sejm_wideo.video_link('https://p', 3665) == 'https://p#t=3665' and sejm_wideo.timecode(3665) == '1:01:05'


def test_select_tops_up_to_daily_limit_once(sejm, monkeypatch):
    monkeypatch.setenv('SEJM_VIDEO_SPIN_DAILY', '2')
    assert len(sejm_wideo.select(DAY)) == 2
    assert sejm_wideo.select(DAY) == []
    rows = list(SejmVideoSpin.objects.order_by('-rank_score'))
    assert rows[0].video_url.endswith('#t=3665') and rows[0].offset_exact and rows[0].status == 'queued'


def test_run_diagnoses_through_same_pipeline_and_publishes(sejm, monkeypatch):
    seen = []
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: seen.append(context) or fake())
    result = sejm_wideo.run(limit=1, now=timezone.make_aware(timezone.datetime(2026, 10, 6, 12)))
    assert result['status'] == 'ok' and result['selected'] == 3
    row = SejmVideoSpin.objects.get(status='approved')
    assert row.verdict == 'spin' and row.diagnosed_at and row.techniques[0]['name'] == 'fałszywa alternatywa'
    context = seen[0]
    assert context['url'].endswith('#t=3665') and 'zapis urzędowy Kancelarii Sejmu' in context['text']
    assert context['author'] == 'Anna Długa'
    items = sejm_wideo.published()
    assert sejm_wideo.item(items[0])['timecode'] == '1:01:05'


def test_without_quorum_the_statement_waits(sejm, monkeypatch):
    def no_quorum(context):
        error = clinic_ai.ClinicAIError('council_quorum: 3/4 członków')
        error.council, error.quorum = {'members': []}, {'met': False}
        raise error
    monkeypatch.setattr(clinic_ai, 'diagnose', no_quorum)
    sejm_wideo.run(limit=1, now=timezone.make_aware(timezone.datetime(2026, 10, 6, 12)))
    row = SejmVideoSpin.objects.order_by('-rank_score').first()
    assert row.status == 'queued' and row.error.startswith('council_quorum') and row.diagnosed_at is None
    assert not sejm_wideo.published().exists()


def test_disabled_without_flag(sejm, monkeypatch):
    monkeypatch.delenv('SEJM_VIDEO_SPIN_ENABLED')
    assert sejm_wideo.run() == {'status': 'disabled'}
    assert not SejmVideoSpin.objects.exists()


def test_api_lists_only_published(sejm, client, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: fake())
    sejm_wideo.run(limit=1, now=timezone.make_aware(timezone.datetime(2026, 10, 6, 12)))
    data = client.get('/api/clinic/sejm-wideo/').json()
    assert len(data['results']) == 1 and data['results'][0]['place'] == 'sala'
    assert data['results'][0]['person']['name'] == 'Anna Długa'

"""All models and network are mocked. Real ORM, quota reservations and PDF rendering."""
import csv
import io
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory
from django.urls import reverse

from news import report_data as data, raportysta as agent, council_registry as registry
from news.clinic_models import SpinDiagnosis, ClinicDailyMessage
from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure, ParliamentaryRosterEntry
from news.report_models import InstitutionalReport, ReportReview, ReportDailyBudget, ReportObservation
from news.report_roles import CORE_ROLES, validate_roles
from news.report_exports import render, render_pages, csv_bytes

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 3, 3, tzinfo=ZoneInfo('Europe/Warsaw'))
MEMBERS = [('groq', 'openai/gpt-oss-20b'), ('nim', 'nvidia/nemotron'), ('groq', 'qwen/qwen'),
           ('nim', 'meta/llama'), ('openrouter', 'deepseek/model:free'), ('nim', 'mistral/model'),
           ('nim', 'moonshot/kimi'), ('nim', 'ibm/granite'), ('nim', 'ai2/olmo')]


@pytest.fixture(autouse=True)
def isolated(settings):
    settings.REPORTS_ENABLED = True
    settings.REPORTS_DAILY_CALLS = 60
    settings.REPORTS_DIAGNOSIS_RESERVE_RATIO = .8
    settings.REPORTS_MIN_WEEKS = 4
    settings.REPORTS_MIN_WEEKLY_PER_CAMP = 10
    settings.REPORTS_MIN_RESEARCH = 100
    settings.REPORTS_MIN_STATEMENTS = 30
    settings.REPORTS_MIN_VOTES = 10
    settings.REPORTS_MIN_TOPIC = 20
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('news.council_registry.configured', return_value=True), \
         patch('news.clinic_council._members', return_value=MEMBERS), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('No network')), \
         patch('smtplib.SMTP', side_effect=AssertionError('No delivery')), \
         patch('news.clinic_council.ask', side_effect=mock_answer) as ask:
        yield ask
    cache.clear()


@pytest.fixture
def records():
    start, end = data.period()
    result = []
    for camp in ('government', 'opposition'):
        account = PoliticalAccount.objects.create(user_id=str(len(result) + 1), handle=camp, camp=camp, enabled=True)
        for week in range(4):
            for i in range(13):
                n = len(result) + 1
                date = datetime.combine(start + timedelta(days=week * 7 + i % 7), datetime.min.time(), data.WARSAW)
                post = PoliticalPost.objects.create(account=account, post_id=str(n),
                    url=f'https://example.org/posts/{n}', text='TREŚĆ CUDZEGO WPISU - NIE EKSPORTUJ',
                    published_at=date, camp_at_collection=camp)
                result.append(SpinDiagnosis.objects.create(post=post, status='approved',
                    verdict=('spin', 'partial', 'no_spin')[i % 3], intensity=(i * 7) % 100,
                    diagnosed_at=date + timedelta(hours=1), techniques=[{'name': 'Apel do emocji'}]))
    return result


def mock_answer(member, system, payload, schema, **kwargs):
    assert registry.reserve(member), 'Test provider must obey the real reservation guard'
    if 'sentences' in schema['properties']:
        values = json.loads(payload)
        language = values['language']
        if 'topic' in values['facts']:
            return {'sentences': [{'text': 'Monitoring obejmuje zweryfikowane obserwacje.', 'fact_ids': ['topic']}], 'extra_roles': []}
        return {'sentences': [{'text': 'Próba obejmuje wybrane diagnozy.' if language == 'pl' else
                              'The sample covers selected diagnoses.',
                              'fact_ids': ['camp:government', 'camp:opposition']}], 'extra_roles': []}
    return {'decision': 'publish', 'critical': [], 'notes': [], 'reason': 'Zgodne z danymi i metodą.'}


def finish(report, limit=50):
    for _ in range(limit):
        status = agent.step(report.pk)
        if status not in ('queued', 'working'):
            break
    report.refresh_from_db()
    return report


def report(kind='weekly', audience='redakcje'):
    return agent.request_sample(kind, audience)


def test_weekly_gate_each_week_and_camp(records):
    assert data.build('weekly')['gate']['ready']
    first = records[:5]
    SpinDiagnosis.objects.filter(pk__in=[r.pk for r in first]).update(status='rejected')
    gate = data.build('weekly')['gate']
    assert not gate['ready']
    assert any('Rządzący: 8/10' in s for s in gate['missing'])
    assert data.build('weekly_en')['gate'] == gate


def test_partial_week_and_duplicate_rows_cannot_open_gate(records):
    start, end = data.period()
    rows = data.diagnosis_rows(start, end)
    assert not data.gate('weekly', rows * 10, start + timedelta(days=1), end)['ready']
    thin = rows[:1] * 100
    assert not data.gate('weekly', thin, start, end)['ready']


def test_research_threshold_and_missing_topic_adapter(records, settings):
    assert data.build('research')['gate']['ready']
    settings.REPORTS_MIN_RESEARCH = 105
    assert not data.build('research')['gate']['ready']
    assert not data.build('topic', {'topic': 'energia'})['gate']['ready']
    assert not data.build('profile')['gate']['ready']
    assert data.build('profile')['gate']['measurements'][0]['actual'] == 0


def test_hidden_withdrawn_unavailable_excluded(records):
    SpinDiagnosis.objects.filter(pk=records[0].pk).update(hidden_at=NOW)
    SpinDiagnosis.objects.filter(pk=records[1].pk).update(withdrawn_at=NOW)
    PoliticalPost.objects.filter(pk=records[2].post_id).update(available=False)
    result = data.build('research')
    assert len(result['rows']) == 101
    assert not any('TREŚĆ CUDZEGO' in json.dumps(r, ensure_ascii=False) for r in result['rows'])


def test_complete_chain_and_private_approval(records, isolated):
    row = report()
    row.snapshot['synthetic'] = True
    row.save(update_fields=['snapshot'])
    finish(row)
    assert row.status == 'awaiting_approval'
    assert row.round == 1 and isolated.call_count == 11
    assert set(CORE_ROLES).issubset(set(row.reviews.values_list('role', flat=True)))
    assert len(set(row.reviews.filter(role__in=CORE_ROLES).values_list('model', flat=True))) == 6
    assert agent.certified(row)
    assert row.approved_at is None
    user = get_user_model().objects.create_user('admin', is_staff=True, is_superuser=True)
    approved = agent.approve(row.pk, user)
    assert approved.status == 'approved' and approved.approved_hash == row.artifact_hash
    assert row.pdf[:4] == b'%PDF' and len(re.findall(rb'/Type /Page\b', row.pdf)) >= 2
    exported = list(csv.DictReader(io.StringIO(bytes(row.csv).decode('utf-8-sig'))))
    assert sum(r['kind'] == 'diagnosis' for r in exported) == 26
    assert b'TRE' not in row.csv
    # Opt-in delivery of the exact artifact produced by this full mock review chain.
    if os.environ.get('REPORTS_TEST_ARTIFACT_DIR'):
        folder = Path(os.environ['REPORTS_TEST_ARTIFACT_DIR'])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'raport-przykladowy.pdf').write_bytes(row.pdf)
        (folder / 'raport-przykladowy.csv').write_bytes(row.csv)
        (folder / 'metoda-i-zrodla.txt').write_text(row.method, encoding='utf-8')
        qa = folder.parent.parent / 'tmp' / 'pdfs'
        qa.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(render_pages(row.snapshot, row.draft), 1):
            page.thumbnail((620, 877))
            page.save(qa / f'reports-preview-{i}.png')


@pytest.mark.parametrize('phase', ['politics', 'linguist', 'council'])
def test_revision_restarts_every_reviewer(records, isolated, phase):
    def answer(*args, **kwargs):
        result = mock_answer(*args, **kwargs)
        audit = ReportReview.objects.order_by('-pk').first()
        if audit.round == 1 and (audit.role == phase or phase == 'council' and audit.role.startswith('council:')):
            return {'decision': 'revise', 'critical': ['Doprecyzuj zakres.'], 'notes': [], 'reason': 'Brakuje precyzji.'}
        return result
    isolated.side_effect = answer
    row = finish(report())
    assert row.status == 'awaiting_approval' and row.round == 2
    for role in CORE_ROLES:
        assert row.reviews.filter(role=role).count() == 2
    assert agent.certified(row)


def test_three_rounds_reject_with_objections(records, isolated):
    def answer(*args, **kwargs):
        result = mock_answer(*args, **kwargs)
        if 'decision' in result:
            result.update(decision='revise', critical=['Nieuprawniony wniosek.'], reason='Brak podstaw.')
        return result
    isolated.side_effect = answer
    row = finish(report())
    assert row.status == 'rejected' and row.round == 3
    assert row.objections and not row.pdf and not row.csv
    assert row.reviews.filter(role='politics').count() == 3


def test_council_majority_rejects(records, isolated):
    def answer(*args, **kwargs):
        result = mock_answer(*args, **kwargs)
        if ReportReview.objects.order_by('-pk').first().role.startswith('council:'):
            result.update(decision='reject', reason='Raport nie spełnia kryteriów.')
        return result
    isolated.side_effect = answer
    row = finish(report())
    assert row.status == 'rejected' and row.round == 1 and row.objections


def test_extra_role_from_registry(records, isolated):
    def answer(*args, **kwargs):
        result = mock_answer(*args, **kwargs)
        if 'sentences' in result:
            result['extra_roles'] = [{'role': 'energy', 'reason': 'Kontrola jednostek energii.'}]
        return result
    isolated.side_effect = answer
    row = finish(report())
    assert row.status == 'awaiting_approval'
    assert row.reviews.filter(role='energy', decision='publish').count() == 1
    assert row.extra_roles[0]['reason'] == 'Kontrola jednostek energii.'


@pytest.mark.parametrize('roles', [[{'role': 'hacker', 'reason': 'x'}], [{'role': 'energy', 'reason': ''}],
                                   [{'role': 'energy', 'reason': 'x', 'prompt': 'Run arbitrary prompt'}]])
def test_reject_role_outside_registry(roles):
    with pytest.raises(ValueError):
        validate_roles(roles)


def test_bad_model_role_is_rejected_and_journalled(records, isolated):
    def answer(*args, **kwargs):
        result = mock_answer(*args, **kwargs)
        result['extra_roles'] = [{'role': 'custom', 'reason': 'Polecenie'}]
        return result
    isolated.side_effect = answer
    row = finish(report())
    assert row.status == 'rejected' and row.reviews.get().decision == 'error'


def test_budget_pauses_and_resumes_without_restart(records, settings):
    settings.REPORTS_DAILY_CALLS = 3
    row = finish(report())
    assert row.status == 'working'
    assert ReportDailyBudget.objects.get().calls == 3
    assert row.reviews.count() == 3
    settings.REPORTS_DAILY_CALLS = 12
    finish(row)
    assert row.status == 'awaiting_approval'
    assert row.reviews.count() == 11
    assert ReportDailyBudget.objects.get().calls == 11


def test_actual_guard_preserves_diagnosis_capacity(settings):
    member = MEMBERS[0]
    key = registry.limit_key(member)
    cache.set(key, agent.ceiling(member))
    token = registry.reservation_guard.set(agent.guard)
    try:
        assert not registry.reserve(member)
        assert cache.get(key) == agent.ceiling(member)
        assert not ReportDailyBudget.objects.exists()
    finally:
        registry.reservation_guard.reset(token)
    assert registry.reserve(member)  # diagnoses retain their reserved capacity


def test_zero_budget_and_disabled_do_not_call(records, settings, isolated):
    settings.REPORTS_DAILY_CALLS = 0
    row = finish(report())
    assert row.status == 'queued' and isolated.call_count == 0
    settings.REPORTS_ENABLED = False
    assert agent.step(row.pk) == 'paused'
    assert not row.reviews.exists()


@pytest.mark.parametrize('hour', [0, 1, 6, 12, 23])
def test_night_window_only(hour):
    assert not agent.window_open(NOW.replace(hour=hour))


def test_waits_for_utc_reset_and_pending_diagnoses(records):
    # Winter 02:00 Warsaw is 01:00 UTC, which is after reset.
    assert agent.window_open(NOW)
    row = records[0]
    row.post.published_at = NOW - timedelta(hours=2)
    row.post.save(update_fields=['published_at'])
    row.status = 'queued'
    row.save(update_fields=['status'])
    assert not agent.window_open()


@pytest.mark.parametrize('member', [('gemini', 'gemini'), ('anthropic', 'claude'), ('openrouter', 'paid'),
                                  ('openrouter', 'google/gemini:free'), ('hf', 'bielik:paid'), ('mistral', 'paid')])
def test_paid_models_denied(member):
    assert not agent.free_member(member)
    assert not agent.guard(member, 1)


def test_draft_requires_source_and_computed_numbers():
    base = {'sentences': [{'text': 'Próba ma 999 diagnoz.', 'fact_ids': ['camp:government']}], 'extra_roles': []}
    with pytest.raises(ValueError):
        agent.validate_draft(base, {'camp:government': {'count': 10}})
    base['sentences'][0] = {'text': 'Próba jest ograniczona.', 'fact_ids': ['invented']}
    with pytest.raises(ValueError):
        agent.validate_draft(base, {'camp:government': {}})
    assert agent.validate_review({'decision': 'publish', 'critical': ['Błąd.'], 'notes': [], 'reason': 'Błąd.'})['decision'] == 'revise'


def test_csv_formula_injection_and_no_raw_posts(records):
    snapshot = data.build('weekly')
    snapshot['rows'][0]['url'] = '=HYPERLINK("bad")'
    result = csv_bytes(snapshot).decode('utf-8-sig')
    assert "'=HYPERLINK" in result and 'TREŚĆ CUDZEGO WPISU' not in result


def test_command_deduplicates_and_never_sends(records, settings, isolated):
    settings.REPORTS_ENABLED = False
    out = io.StringIO()
    call_command('reports_sample', type='weekly', audience='redakcje', stdout=out)
    call_command('reports_sample', type='weekly', audience='redakcje', stdout=out)
    assert InstitutionalReport.objects.count() == 1 and isolated.call_count == 0
    with pytest.raises(ValueError):
        agent.request_sample('weekly_en', 'redakcje')
    assert 'Panel:' in out.getvalue()


def test_approval_permissions_and_changed_artifact(records):
    row = finish(report())
    staff = get_user_model().objects.create_user('editor', is_staff=True)
    with pytest.raises(PermissionError):
        agent.approve(row.pk, staff)
    staff.is_superuser = True
    InstitutionalReport.objects.filter(pk=row.pk).update(csv=b'changed')
    with pytest.raises(ValueError):
        agent.approve(row.pk, staff)


def test_private_admin_files_and_readiness(records):
    row = finish(report())
    url = reverse('admin:news_reports_download', args=[row.pk, 'pdf'])
    client = Client()
    assert client.get(url).status_code == 302
    user = get_user_model().objects.create_user('admin', is_staff=True, is_superuser=True)
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200 and 'private' in response['Cache-Control'] and 'no-store' in response['Cache-Control']
    # Direct view/context assertion: local Python 3.14 is incompatible with Django
    # 5.1's test-template context copying; production uses Python 3.11.
    from django.contrib import admin
    request = RequestFactory().get(reverse('admin:news_reports_readiness'))
    request.user = user
    response = admin.site._registry[InstitutionalReport].readiness(request)
    assert response.status_code == 200
    assert any(item['ready'] for item in response.context_data['readiness'])
    assert any(not item['ready'] for item in response.context_data['readiness'])
    # Source withdrawal immediately disables even previously generated private downloads.
    pk = int(row.snapshot['rows'][0]['id'].split(':')[1])
    SpinDiagnosis.objects.filter(pk=pk).update(withdrawn_at=NOW)
    assert client.get(url).status_code == 400


def test_daily_messages_recalculate_tone_without_exporting_text(records):
    d = records[40]
    msg = ClinicDailyMessage.objects.create(day=d.post.published_at.date(), camp='government', status='approved',
            thesis='Rządzący wskazują na działania.', themes=['Energia'], tone=[{'post_id': str(d.post.pk), 'label': 'apel'}])
    msg.posts.add(d.post)
    snapshot = data.build('weekly')
    assert f'message:{msg.pk}' in snapshot['facts']
    assert 'TREŚĆ CUDZEGO' not in json.dumps(snapshot, ensure_ascii=False)


def test_profile_identity_and_term_not_name(records):
    from news.models import Article, Source, ParliamentaryVoting, Ballot
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='7', term=10,
        full_name='Osoba Testowa', source_url='https://example.org/roster')
    figure = PublicFigure.objects.create(canonical_name='Osoba Testowa', parliamentary_roster_entry=roster,
        role_category='parliamentary', evidence_url='https://example.org/person')
    source = Source.objects.create(name='Źródło testowe', url='https://example.org')
    for term, mp in [(10, 7), (9, 7), (10, 8)]:
        article = Article.objects.create(source=source, title='Głosowanie', url=f'https://example.org/{term}/{mp}',
                                         published_date=NOW - timedelta(days=8))
        voting = ParliamentaryVoting.objects.create(article=article, term=term, sitting=1, number=mp, kind='test', motion='')
        Ballot.objects.create(voting=voting, mp_id=mp, name='Osoba Testowa', vote='YES')
    with patch('news.clinic.figures_by_account', return_value={records[0].post.account_id: figure}):
        snapshot = data.build('profile', {'figure_id': figure.pk})
    votes = [r for r in snapshot['rows'] if r['kind'] == 'vote']
    assert len(votes) == 1 and snapshot['gate']['measurements'][1]['actual'] == 1
    assert snapshot['limitations']


def test_english_same_data_and_real_exports(records):
    from news.report_exports import TECHNIQUES_EN
    from news.techniques import CANONICAL_TECHNIQUES
    assert set(TECHNIQUES_EN) == set(CANONICAL_TECHNIQUES)
    pl, en = data.build('weekly'), data.build('weekly_en')
    assert pl['facts'] == en['facts'] and pl['rows'] == en['rows']
    row = finish(report('weekly_en', 'think-tanki'))
    assert row.status == 'awaiting_approval'
    assert 'Method and sources' in row.method
    assert row.draft['sentences'][0]['text'].startswith('The sample')


def test_uniqueness_at_database_level(records):
    row = report()
    with pytest.raises(IntegrityError), transaction.atomic():
        InstitutionalReport.objects.create(kind='weekly', audience='redakcje', sample_key=row.sample_key)


def test_schedule_and_registry():
    from news.daily_schedule import BEAT_PLAN, MILESTONES
    from news.agent_registry import REGISTRY
    assert BEAT_PLAN['institutional-reports-night'][1]['hour'] == '2-5'
    assert any(m.key == 'institutional-reports' for m in MILESTONES)
    assert REGISTRY['raportysta']['flag'] == 'REPORTS_ENABLED'


def observation(kind='bill', **kwargs):
    n = ReportObservation.objects.count() + 1
    user, _ = get_user_model().objects.get_or_create(username='verifier', defaults={'is_superuser': True})
    return ReportObservation.objects.create(external_key=f'test:{n}', kind=kind, topic='energia',
        day=kwargs.pop('day', data.period()[1] - timedelta(days=5)), analysis='Własna analiza materiału.',
        source_url=f'https://example.org/observation/{n}', confidence_reason='Jedno potwierdzone źródło.',
        approved=True, verified_by=user, verified_at=NOW, **kwargs)


def test_topic_real_data_contract_and_exports(records):
    figure = PublicFigure.objects.create(canonical_name='Osoba Testowa', role_category='parliamentary',
                                         evidence_url='https://example.org/figure')
    for _ in range(17):
        observation()
    observation('amendment')
    observation('lobbying')
    d = records[40]
    observation('stance', figure=figure, diagnosis=d, stance='support', day=d.post.published_at.date())
    with patch('news.clinic.figures_by_account', return_value={d.post.account_id: figure}):
        row = agent.request_sample('topic', 'dzialy-gr', {'topic': 'energia'})
        assert row.gate['ready']
        finish(row)
    assert row.status == 'awaiting_approval'
    assert row.snapshot['facts']['topic']['lobbying_confidence'] == {'low': 1}
    assert 'confidence_reason' in bytes(row.csv).decode('utf-8-sig')
    assert 'TREŚĆ CUDZEGO' not in bytes(row.csv).decode('utf-8-sig')
    assert row.pdf.startswith(b'%PDF')


def test_unverified_or_edited_observations_excluded():
    from news.report_observations import rows
    obj = observation()
    start, end = data.period()
    assert len(rows(start, end, topic='energia')) == 1
    obj.analysis = 'Nowa wersja wymaga kontroli.'
    obj.save(update_fields=['analysis'])
    obj.refresh_from_db()
    assert not obj.approved and not rows(start, end, topic='energia')


def test_observation_withdrawal_invalidates_export():
    from news.report_observations import rows, current
    obj = observation()
    start, end = data.period()
    snapshot = {'rows': rows(start, end)}
    assert current(snapshot)
    ReportObservation.objects.filter(pk=obj.pk).update(approved=False)
    assert not current(snapshot)


def test_changes_and_vote_alignment_are_computed():
    from news.report_observations import comparisons
    rows = [dict(id='observation:1', kind='stance', date='2026-09-01', figure_id=1, topic='energia',
                 stance='support', ballot_id=None, vote='', supporting_vote=''),
            dict(id='observation:2', kind='stance', date='2026-09-02', figure_id=1, topic='energia',
                 stance='oppose', ballot_id=10, vote='NO', supporting_vote='YES'),
            dict(id='observation:3', kind='stance', date='2026-09-03', figure_id=1, topic='energia',
                 stance='oppose', ballot_id=11, vote='YES', supporting_vote='YES'),
            dict(id='observation:4', kind='stance', date='2026-09-04', figure_id=1, topic='energia',
                 stance='oppose', ballot_id=12, vote='ABSTAIN', supporting_vote='YES')]
    result = comparisons(rows)
    assert len(result['position_changes']) == 1
    assert result['alignment_counts'] == {'consistent': 1, 'different': 1, 'unassessed': 1}


def test_observation_needs_evidence_identity_and_confidence():
    from django.core.exceptions import ValidationError
    obj = observation('stance')
    with pytest.raises(ValidationError):
        obj.full_clean()
    obj = observation(confidence='high')
    with pytest.raises(ValidationError):
        obj.full_clean()


def test_budget_race_is_deferred_not_rejected(records, isolated):
    row = report()
    with patch('news.raportysta.reserve_call', return_value=False):
        assert agent.step(row.pk) == 'paused'
    assert row.reviews.get().decision == 'deferred'
    assert all(cache.get(registry.limit_key(m), 0) == 0 for m in MEMBERS)
    finish(row)
    assert row.status == 'awaiting_approval' and row.reviews.count() == 11


def test_complete_step_can_replay_without_second_model_call(records, isolated):
    row = report()
    row.panel = agent.select_panel([])
    row.save(update_fields=['panel'])
    answer = agent._ask(row, 'author')
    # Crash after persisted response but before saving phase advancement.
    assert agent._ask(row, 'author') == answer
    assert isolated.call_count == 1
    finish(row)
    assert row.status == 'awaiting_approval' and isolated.call_count == 11


def test_overlong_evidence_never_silently_truncated(records, isolated):
    row = report()
    row.snapshot['facts']['oversized'] = 'x' * 13000
    row.save(update_fields=['snapshot'])
    finish(row)
    assert row.status == 'rejected' and isolated.call_count == 0
    assert row.reviews.get().decision == 'error'


def test_diagnosis_lock_prevents_reports(records, isolated):
    row = report()
    cache.set('clinic-diagnose-lock', 'diagnosis', 60)
    assert agent.step(row.pk) == 'locked'
    assert isolated.call_count == 0 and cache.get('clinic-diagnose-lock') == 'diagnosis'


def test_baseline_withdrawal_invalidates_report(records):
    row = finish(report())
    SpinDiagnosis.objects.filter(pk=records[0].pk).update(withdrawn_at=NOW)
    assert not data.sources_current(row.snapshot)


def test_changed_message_invalidates_report(records):
    d = records[40]
    msg = ClinicDailyMessage.objects.create(day=d.post.published_at.date(), camp='government', status='approved',
            thesis='Rządzący wskazują na działania.', themes=['Energia'])
    msg.posts.add(d.post)
    snapshot = data.build('weekly')
    assert data.sources_current(snapshot)
    ClinicDailyMessage.objects.filter(pk=msg.pk).update(thesis='Rządzący wskazują inny temat.')
    assert not data.sources_current(snapshot)


def test_full_profile_with_verified_position_links(records):
    from news.models import Article, Source, ParliamentaryVoting, Ballot
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='7', term=10,
        full_name='Osoba Testowa', source_url='https://example.org/roster')
    figure = PublicFigure.objects.create(canonical_name='Osoba Testowa', parliamentary_roster_entry=roster,
        role_category='parliamentary', evidence_url='https://example.org/person')
    source = Source.objects.create(name='Źródło testowe', url='https://example.org')
    ballots = []
    for n in range(10):
        article = Article.objects.create(source=source, title='Głosowanie', url=f'https://example.org/vote/{n}',
                                         published_date=NOW - timedelta(days=8))
        voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=1, number=n, kind='test', motion='')
        ballots.append(Ballot.objects.create(voting=voting, mp_id=7, name='Osoba Testowa', vote='YES'))
    for d, stance, ballot in [(records[0], 'support', ballots[0]), (records[1], 'oppose', ballots[1])]:
        observation('stance', figure=figure, diagnosis=d, stance=stance, day=d.post.published_at.date(),
                    ballot=ballot, supporting_vote='YES')
    with patch('news.clinic.figures_by_account', return_value={records[0].post.account_id: figure}):
        row = agent.request_sample('profile', 'biura-poselskie', {'figure_id': figure.pk})
        assert row.gate['ready']
        finish(row)
    assert row.status == 'awaiting_approval'
    comparisons = row.snapshot['facts']['profile_comparisons']
    assert len(comparisons['position_changes']) == 1
    assert comparisons['alignment_counts'] == {'consistent': 1, 'different': 1}


def test_research_completes_full_chain(records):
    row = finish(report('research', 'uczelnie'))
    assert row.status == 'awaiting_approval'
    assert len([r for r in row.snapshot['rows'] if r['kind'] == 'diagnosis']) == 104
    assert row.pdf.startswith(b'%PDF') and row.csv

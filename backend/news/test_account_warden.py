from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import account_warden as w
from news import account_warden_sources as s
from news.models import ImportState
from news.political_models import PoliticalAccount, PoliticalAccountCandidate, PublicFigure, ParliamentaryRosterEntry, PoliticalRead, SocialHandleEvidence

pytestmark = pytest.mark.django_db
SYNC_ROSTERS = s.sync_rosters
SEARCH_LEADS = s.search_leads
WIKIDATA_LEADS = s.wikidata_leads
OFFICIAL_LEADS = s.official_leads


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', lambda *a, **k: pytest.fail('Unexpected network'))
    monkeypatch.setattr(w, '_notify', Mock(return_value=True))
    monkeypatch.setattr(s, 'sync_rosters', lambda events: None)
    monkeypatch.setattr(s, 'wikidata_leads', lambda: {})
    monkeypatch.setattr(s, 'official_leads', lambda target: [])
    monkeypatch.setattr(s, 'search_leads', lambda target, reserve: [])
    monkeypatch.setattr(s, 'party_leads', lambda target: [])
    monkeypatch.setenv('ACCOUNT_WARDEN_DAILY_X_LOOKUPS', '60')
    monkeypatch.delenv('X_POLITICAL_POLLING_ENABLED', raising=False)


def target(camp='government', name='Jan Kowalski', suffix='1', priority=1):
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id=suffix, full_name=name,
        club='KO' if camp == 'government' else 'PiS', source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    f = PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł',
        evidence_url=entry.source_url, parliamentary_roster_entry=entry, import_key='parliamentary:sejm:' + suffix)
    return s.Target(f'figure:{f.pk}', name, 'Poseł', camp, priority, ('sejm',), f)


def user_data(handle='JanKowalski', uid='1234', **changes):
    data = {'id': uid, 'username': handle, 'name': 'Jan Kowalski', 'description': 'Poseł na Sejm',
            'protected': False, 'created_at': '2015-01-01T00:00:00Z',
            'verified': False, 'public_metrics': {'followers_count': 10000}}
    return {**data, **changes}


def report():
    return {'lookups': 0, 'events': [], 'added_ids': []}


def add(t, data=None):
    data = data or user_data()
    return w.save_candidate(t, s.Lead(data['username'], 'https://www.sejm.gov.pl/profile', 'official'), data, 'accepted', '')[0]


@pytest.mark.parametrize('camp', ['government', 'opposition'])
def test_certain_added_confirmed_and_readable_one_lookup(camp, monkeypatch):
    t = target(camp)
    monkeypatch.setattr(s, 'targets', lambda **k: [t])
    monkeypatch.setattr(s, 'wikidata_leads', lambda: {'jan kowalski': [s.Lead('JanKowalski', 'https://www.wikidata.org/entity/Q123', 'wikidata')]})
    lookup = Mock(return_value={'data': user_data()})
    monkeypatch.setattr(w, 'x_lookup', lookup)
    r = w.run(only_missing=True)
    assert r['status'] == 'ok', r
    a = PoliticalAccount.objects.get(user_id='1234')
    assert a.enabled and a.is_confirmed() and a.camp == camp
    assert not a.confirmed_by.has_usable_password()
    assert SocialHandleEvidence.objects.get(subject_object_id=t.figure.pk).status == 'candidate_created'
    assert r['coverage']['sejm']['observed'] == 1
    assert r['lookups'] == lookup.call_count == 1
    # The normal poller actually reads the newly added account; only its X transport is mocked.
    import json
    from news.political_polling import political_poll_cycle
    config = {'page_size': 10, 'lookback_hours': 24, 'daily_requests': 100, 'daily_posts': 100, 'monthly_usd': Decimal('5')}
    monkeypatch.setattr('news.political_polling.configuration', lambda: config)
    payload = {'data': [{'id': '987654321', 'author_id': a.user_id, 'text': 'Testowy wpis posła',
                         'created_at': (timezone.now() - timedelta(minutes=1)).isoformat()}],
               'meta': {'result_count': 1}, 'includes': {'users': [user_data()]}}
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: json.dumps(payload).encode())
    assert political_poll_cycle()['new_posts'] == 1
    assert a.posts.get().text == 'Testowy wpis posła'


def test_uncertain_only_queue(monkeypatch):
    t = target()
    monkeypatch.setattr(s, 'search_leads', lambda *a: [s.Lead('JanKowalski', 'https://example.org/evidence', 'search')])
    monkeypatch.setattr(w, 'x_lookup', lambda **k: {'data': user_data(public_metrics={'followers_count': 100})})
    r = report()
    w.discover_missing([t], r, 10)
    assert not PoliticalAccount.objects.filter(user_id='1234').exists()
    c = PoliticalAccountCandidate.objects.get(handle='JanKowalski')
    assert c.resolved_account_id is None and 'Zasięg' in c.resolution_error
    assert SocialHandleEvidence.objects.get(candidate=c).status == 'pending_review'


@pytest.mark.parametrize('data', [user_data(description='parodia'), user_data(name='Jan Kowalski fanpage'),
    user_data(created_at=timezone.now().isoformat(), verified=True), user_data(protected=True)])
def test_hard_rejection(data):
    assert w.check_candidate(data, target(), 'official')[0] == 'rejected'


def test_web_requires_all_conditions():
    t = target()
    assert w.check_candidate(user_data(), t, 'search') == ('accepted', '')
    assert w.check_candidate(user_data(description=''), t, 'search')[0] == 'pending'
    assert w.check_candidate(user_data(public_metrics={'followers_count': 1}, verified=True), t, 'search')[0] == 'accepted'


def test_rename_by_id_preserves_confirmation(monkeypatch):
    a = add(target())
    a.last_verified_at = timezone.now() - timedelta(days=15)
    a.save(update_fields=['last_verified_at'])
    lookup = Mock(return_value={'data': [user_data(handle='NewKowalski')]})
    monkeypatch.setattr(w, 'x_lookup', lookup)
    r = report()
    w.verify_accounts(r, 100)
    a.refresh_from_db()
    assert a.handle == 'NewKowalski' and a.enabled and a.is_confirmed()
    assert lookup.call_args.kwargs == {'ids': ['1234']}
    assert r['events'][0]['kind'] == 'renamed'


@pytest.mark.parametrize('payload', [
    {'errors': [{'resource_id': '1234', 'type': 'https://api.x.com/2/problems/resource-unavailable'}]},
    {'data': [user_data(protected=True)]}, {'data': [user_data(name='Obca Osoba')]},
])
def test_suspended_protected_or_changed_identity_disabled(payload, monkeypatch):
    a = add(target())
    PoliticalAccount.objects.filter(pk=a.pk).update(last_verified_at=None)
    monkeypatch.setattr(w, 'x_lookup', lambda **k: payload)
    w.verify_accounts(report(), 100)
    a.refresh_from_db()
    assert not a.enabled


def test_partial_response_does_not_disable_or_verify(monkeypatch):
    a = add(target())
    PoliticalAccount.objects.filter(pk=a.pk).update(last_verified_at=None)
    monkeypatch.setattr(w, 'x_lookup', lambda **k: {'errors': [{'detail': 'technical failure'}]})
    w.verify_accounts(report(), 100)
    a.refresh_from_db()
    assert a.enabled and a.last_verified_at is None


def test_daily_budget_survives_runs_and_counts_users(monkeypatch):
    monkeypatch.setenv('ACCOUNT_WARDEN_DAILY_X_LOOKUPS', '2')
    assert w.reserve_units('x', 2)
    assert not w.reserve_units('x') and w.remaining() == 0
    state = ImportState.objects.get(name=w.STATE + '-budget')
    state.cursor['day'] = '2000-01-01'
    state.save()
    assert w.remaining() == 2 and w.reserve_units('x', 2)
    assert not w.reserve_units('x')


def test_lookup_limit_during_discovery(monkeypatch):
    t = target()
    monkeypatch.setenv('ACCOUNT_WARDEN_DAILY_X_LOOKUPS', '1')
    monkeypatch.setattr(s, 'search_leads', lambda *a: [s.Lead('one', 'https://example.org/one', 'search'), s.Lead('two', 'https://example.org/two', 'search')])
    lookup = Mock(return_value={'data': None})
    monkeypatch.setattr(w, 'x_lookup', lookup)
    w.discover_missing([t], report(), 100)
    assert lookup.call_count == 1


def test_dry_run_no_writes_or_external_calls(monkeypatch):
    target()
    monkeypatch.setattr(w, 'x_lookup', lambda **k: pytest.fail('X in dry run'))
    monkeypatch.setattr(s, 'sync_rosters', lambda *a: pytest.fail('sync in dry run'))
    counts = {m: m.objects.count() for m in apps.get_models()}
    out = StringIO()
    call_command('account_warden', dry_run=True, stdout=out)
    assert 'dry_run' in out.getvalue()
    assert counts == {m: m.objects.count() for m in counts}
    w._notify.assert_not_called()


def test_budget_fit_preserves_cap_and_priority(monkeypatch):
    high, low = target(priority=0), target(name='Piotr Nowak', suffix='2', priority=2)
    a = add(high)
    b = add(low, user_data(handle='PiotrNowak', uid='4567', name='Piotr Nowak'))
    monkeypatch.setattr(w, 'configuration', lambda: {'page_size': 10, 'daily_requests': 1,
        'daily_posts': 100, 'monthly_usd': Decimal('5')})
    r = report()
    r['added_ids'] = [a.pk, b.pk]
    w.fit_polling_budget([high, low], r)
    a.refresh_from_db(); b.refresh_from_db()
    assert a.poll_interval_minutes < b.poll_interval_minutes
    assert 1440 / a.poll_interval_minutes + 1440 / b.poll_interval_minutes <= 1
    assert a.is_confirmed() and b.is_confirmed()
    assert r['polling']['total_requests_day'] <= r['polling']['budget_requests_day']


def test_existing_disabled_account_not_resurrected():
    t = target()
    a = add(t)
    a.enabled = False
    a.save()
    result, reason = w.save_candidate(t, s.Lead(a.handle, 'https://example.org/proof', 'official'), user_data(), 'accepted', '')
    assert result is None and 'wyłączone' in reason
    a.refresh_from_db()
    assert not a.enabled


def test_staff_panel_permissions_and_section():
    client = APIClient()
    assert client.get('/api/admin/status/').status_code in (401, 403)
    staff = get_user_model().objects.create_user(username='warden-test-staff', is_staff=True)
    client.force_authenticate(staff)
    response = client.get('/api/admin/status/')
    assert response.status_code == 200
    assert any(row['title'] == 'Strażnik kont' for row in response.data['sections'])


def test_inactive_report_without_disabling(monkeypatch):
    a = add(target())
    old = timezone.now() - timedelta(days=40)
    PoliticalAccount.objects.filter(pk=a.pk).update(last_verified_at=None, created_at=old, last_polled_at=timezone.now())
    PoliticalRead.objects.create(account=a, status='ok', reserved_posts=10, reserved_usd='0.06', started_at=old)
    monkeypatch.setattr(w, 'x_lookup', lambda **k: {'data': [user_data()]})
    r = report()
    w.verify_accounts(r, 10)
    a.refresh_from_db()
    assert a.enabled and any(e['kind'] == 'inactive' for e in r['events'])


def test_schedule():
    from config.celery import app
    task = app.conf.beat_schedule['account-warden-nightly']
    assert task['schedule'].hour == {3} and task['schedule'].minute == {10}


def test_club_change_report_only(monkeypatch):
    # Exercise the actual synchronization wrapper with mocked official import commands.
    t = target()
    a = add(t)
    def sync(command, **kwargs):
        if command == 'sync_parliamentary_roster' and kwargs.get('source') == 'sejm':
            ParliamentaryRosterEntry.objects.filter(pk=t.figure.parliamentary_roster_entry_id).update(club='PiS')
    monkeypatch.setattr(s, 'call_command', sync)
    events = []
    SYNC_ROSTERS(events)
    a.refresh_from_db()
    assert a.camp == 'government' and a.enabled and any(e['kind'] == 'camp' for e in events)


def test_same_lookup_reused_when_party_evidence_strengthens_search(monkeypatch):
    t = target()
    monkeypatch.setattr(s, 'search_leads', lambda *a: [s.Lead('JanKowalski', 'https://example.org/search', 'search')])
    monkeypatch.setattr(s, 'party_leads', lambda *a: [s.Lead('JanKowalski', 'https://platforma.org/person', 'party')])
    lookup = Mock(return_value={'data': user_data(description='', public_metrics={'followers_count': 100})})
    monkeypatch.setattr(w, 'x_lookup', lookup)
    r = report()
    w.discover_missing([t], r, 60)
    assert len(r['added_ids']) == 1 and lookup.call_count == 1


def test_failure_still_uses_budget_and_is_in_cost_journal(monkeypatch):
    from news.political_models import AccountWardenRun
    from news.admin_finance import recorded_events
    t = target()
    monkeypatch.setattr(s, 'targets', lambda **k: [t])
    monkeypatch.setattr(s, 'official_leads', lambda *a: [s.Lead('JanKowalski', 'https://www.sejm.gov.pl/person', 'official')])
    monkeypatch.setattr(w, 'x_lookup', Mock(side_effect=w.TechnicalError('X: HTTP 429')))
    r = w.run(only_missing=True)
    assert r['status'] == 'error' and w.remaining() == 59
    journal = AccountWardenRun.objects.latest('pk')
    assert journal.lookups == 1 and journal.finished_at and journal.report['status'] == 'error'
    events = recorded_events(timezone.now() - timedelta(hours=1), timezone.now())
    assert any(e[1] == 'x' and e[2] == 0.01 for e in events)
    assert not ImportState.objects.get(name=w.STATE).cursor.get('lease')


def test_batches_at_most_100_and_budget_counts_every_user(monkeypatch):
    PoliticalAccount.objects.all().update(enabled=False)
    PoliticalAccount.objects.bulk_create([PoliticalAccount(user_id=str(10000 + i), handle=f'Jan{i}',
        display_name='Jan Kowalski', camp='government', enabled=True) for i in range(105)])
    monkeypatch.setenv('ACCOUNT_WARDEN_DAILY_X_LOOKUPS', '105')
    lookup = Mock(side_effect=lambda ids: {'data': [user_data(handle='Jan' + str(int(uid) - 10000), uid=uid) for uid in ids]})
    monkeypatch.setattr(w, 'x_lookup', lookup)
    r = report()
    w.verify_accounts(r, 105)
    assert [len(call.kwargs['ids']) for call in lookup.call_args_list] == [100, 5]
    assert r['lookups'] == 105 and not w.reserve_units('x')


def test_search_requires_real_search_citation_and_handle(monkeypatch):
    import json
    t = target()
    monkeypatch.setattr(s.registry, 'configured', lambda _: True)
    monkeypatch.setattr(s.registry, 'reserve', lambda _: True)
    monkeypatch.setattr(s.registry, 'credentials', lambda _: 'test')
    payload = {'choices': [{'message': {'content': json.dumps({'candidates': [
        {'handle': 'JanKowalski', 'url': 'https://example.org/real'},
        {'handle': 'Invented', 'url': 'https://example.org/real'},
        {'handle': 'Fake', 'url': 'https://example.org/hallucinated'}]}), 'executed_tools': [
            {'search_results': {'results': [{'url': 'https://example.org/real', 'snippet': 'Poseł Jan Kowalski @JanKowalski'}]}}]}}]}
    response = Mock()
    response.json.return_value = payload
    post = Mock(return_value=response)
    monkeypatch.setattr(s.requests, 'post', post)
    assert SEARCH_LEADS(t, lambda: True) == [s.Lead('JanKowalski', 'https://example.org/real', 'search')]
    assert post.call_args.kwargs['json']['model'] == 'groq/compound'
    assert 'niezaufane dane' in post.call_args.kwargs['json']['messages'][0]['content']


def test_search_leaves_half_free_pool_for_service(monkeypatch):
    from django.core.cache import cache
    key = 'warden-test-search-reserve'
    monkeypatch.setattr(s.registry, 'configured', lambda _: True)
    monkeypatch.setattr(s.registry, 'limit_key', lambda _: key)
    monkeypatch.setattr(s.registry, 'daily_limit', lambda _: 300)
    cache.set(key, 150)
    assert SEARCH_LEADS(target(), lambda: True) == []
    assert cache.get(key) == 150
    cache.delete(key)


def test_wikidata_requires_unique_name_and_valid_handle(monkeypatch):
    def row(handle, entity):
        return {'personLabel': {'value': 'Jan Kowalski'}, 'x': {'value': handle}, 'person': {'value': 'http://www.wikidata.org/entity/' + entity}}
    response = Mock()
    response.json.return_value = {'results': {'bindings': [row('JanKowalski', 'Q1'), row('OtherKowalski', 'Q2')]}}
    monkeypatch.setattr(s.requests, 'get', lambda *a, **k: response)
    assert WIKIDATA_LEADS() == {}
    response.json.return_value = {'results': {'bindings': [row('JanKowalski', 'Q1')]}}
    assert WIKIDATA_LEADS()['jan kowalski'][0].url == 'https://www.wikidata.org/entity/Q1'


def test_recent_priority_does_not_starve_lower_priority(monkeypatch):
    high, low = target(priority=0), target(name='Piotr Nowak', suffix='2')
    high.figure.account_discovery_at = timezone.now()
    monkeypatch.setattr(s, 'official_leads', lambda t: [s.Lead('PiotrNowak', 'https://www.sejm.gov.pl/profile', 'official')])
    monkeypatch.setattr(w, 'x_lookup', lambda **k: {'data': user_data(handle='PiotrNowak', uid='4567', name='Piotr Nowak')})
    r = report()
    w.discover_missing([high, low], r, 1)
    assert len(r['added_ids']) == 1


def test_mandate_loss_is_reported_without_disabling(monkeypatch):
    t = target()
    a = add(t)
    def sync(command, **kwargs):
        if command == 'sync_parliamentary_roster' and kwargs.get('source') == 'sejm':
            ParliamentaryRosterEntry.objects.filter(pk=t.figure.parliamentary_roster_entry_id).update(active=False)
    monkeypatch.setattr(s, 'call_command', sync)
    events = []
    SYNC_ROSTERS(events)
    a.refresh_from_db()
    assert a.enabled and any(e['kind'] == 'former' for e in events)


def test_lock_shared_by_task_and_command(monkeypatch):
    ImportState.objects.create(name=w.STATE, cursor={'lease_until': (timezone.now() + timedelta(hours=1)).isoformat()})
    monkeypatch.setattr(s, 'sync_rosters', lambda *a: pytest.fail('Concurrent run'))
    assert w.run()['status'] == 'already_running'


def test_identity_wrong_first_name_does_not_pass_on_common_first_name():
    t = target()
    verdict, _ = w.check_candidate(user_data(name='Jan Nowak', username='JanNowak'), t, 'search')
    assert verdict != 'accepted'


def test_new_fields_match_migration():
    # Only checks the migration graph, never opens or changes a production database.
    call_command('makemigrations', 'news', check=True, dry_run=True, stdout=StringIO())


def test_all_roster_groups_get_public_figures(monkeypatch):
    from news.parliamentary_roster import RosterRow
    from news.government_roster import CabinetRow
    from news.voivode_roster import VoivodeRow
    monkeypatch.setattr('news.management.commands.sync_parliamentary_roster.get_rows', lambda source: [
        RosterRow('1', 'Jan ' + source, club='KO', source_url='https://www.sejm.gov.pl/list', term=10)])
    monkeypatch.setattr('news.management.commands.sync_public_figures.cabinet_rows', lambda: [
        CabinetRow('Anna Minister', 'Minister Testów', 'https://www.gov.pl/list', 'kprm-cabinet:anna-minister')])
    monkeypatch.setattr('news.management.commands.sync_voivodes.get_rows', lambda: [
        VoivodeRow('test', 'Anna Wojewoda', 'Wojewoda', 'Urząd', 'https://www.gov.pl/list')])
    SYNC_ROSTERS([])
    scope = s.targets()
    assert {g for t in scope for g in t.groups} == {'sejm', 'senat', 'ep', 'cabinet', 'voivodes', 'leaders', 'parties'}
    assert all(t.figure and t.figure.pk for t in scope)
    assert next(t for t in scope if t.name == 'Sławomir Mentzen').priority == 0


def test_registry_party_leader_is_not_lost_when_missing_from_priority_seeds():
    figure = PublicFigure.objects.create(canonical_name='Lider Innej Partii', role_category='party',
        role_title='Przewodniczący', organisation='Inna partia', evidence_url='https://example.org/wladze')
    person = next(t for t in s.targets() if t.figure.pk == figure.pk)
    assert 'leaders' in person.groups and person.priority == 0
    assert person.camp == ''  # An unknown affiliation is queued, never guessed.


def test_stored_official_evidence_is_discovered_when_profile_unavailable(monkeypatch):
    from django.contrib.contenttypes.models import ContentType
    from news.social_handle_discovery import SocialDiscoveryError
    t = target()
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure),
        subject_object_id=t.figure.pk, handle='JanKowalski', evidence_url='https://www.europarl.europa.eu/1',
        extracted_url='https://x.com/JanKowalski')
    monkeypatch.setattr(s, 'discover_for_entry', Mock(side_effect=SocialDiscoveryError('unavailable')))
    assert OFFICIAL_LEADS(t) == [s.Lead('JanKowalski', 'https://www.europarl.europa.eu/1', 'official')]


def test_party_abbreviation_uses_same_age_and_parody_checks():
    t = s.Target('party:psl', 'Polskie Stronnictwo Ludowe', 'Partia', 'government', 0, ('parties',), party_handle='nowePSL')
    data = user_data(handle='nowePSL', name='PSL')
    assert w.check_candidate(data, t, 'party')[0] == 'accepted'
    assert w.check_candidate({**data, 'description': 'parodia'}, t, 'party')[0] == 'rejected'


def test_merged_cabinet_member_loses_role_but_keeps_mp_and_account(monkeypatch):
    from news.government_roster import CabinetRow
    from news.political_models import PublicFigureRole
    t = target()
    a = add(t)
    f = PublicFigure.objects.create(canonical_name=t.name, role_category='government', role_title='Minister Testów',
        import_key='kprm-cabinet:jan-kowalski', merged_into=t.figure, archived=True, evidence_url='https://www.gov.pl/list')
    rows = [CabinetRow(t.name, 'Minister Testów', 'https://www.gov.pl/list', f.import_key)]
    monkeypatch.setattr('news.management.commands.sync_public_figures.cabinet_rows', lambda: rows)
    call_command('sync_public_figures', source='cabinet', stdout=StringIO())
    rows[:] = [CabinetRow('Inna Osoba', 'Minister Innych Spraw', 'https://www.gov.pl/list', 'kprm-cabinet:inna-osoba')]
    call_command('sync_public_figures', source='cabinet', stdout=StringIO())
    assert PublicFigureRole.objects.get(public_figure=t.figure).status == 'former'
    t.figure.refresh_from_db(); a.refresh_from_db(); f.refresh_from_db()
    assert t.figure.status == 'current' and a.enabled and f.archived and f.status == 'former'

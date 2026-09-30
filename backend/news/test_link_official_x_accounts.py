from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from news.management.commands import link_official_x_accounts as command
from news.political_models import ParliamentaryRosterEntry, PoliticalAccount, SocialHandleEvidence


class Reply:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def wikidata(rows):
    return Reply({'results': {'bindings': [
        {'person': {'value': f'http://www.wikidata.org/entity/Q{index}'}, 'personLabel': {'value': name}, 'x': {'value': handle}}
        for index, (name, handle) in enumerate(rows)]}})


def mp(name, club, external_id):
    return ParliamentaryRosterEntry.objects.create(source='sejm', external_id=external_id, full_name=name, club=club,
                                                   source_url='https://api.sejm.gov.pl/sejm/term10/MP', active=True)


@pytest.mark.django_db
def test_plan_matches_only_unique_current_mps_and_known_clubs(monkeypatch):
    mp('Jan Kowalski', 'KO', '1')
    mp('Anna Nowak', 'niez.', '2')
    monkeypatch.setattr(command.requests, 'get', lambda *args, **kwargs: wikidata([
        ('Jan Kowalski', 'jankowalski'), ('Anna Nowak', 'annanowak'), ('Ktoś Spoza Sejmu', 'ktos')]))
    out = StringIO()
    call_command('link_official_x_accounts', '--skip-discovery', '--wikidata', stdout=out)
    text = out.getvalue()
    assert 'POŁĄCZ  @jankowalski → Jan Kowalski · Sejm · KO · government' in text
    assert 'POMIŃ   @annanowak' in text and '@ktos' not in text
    assert not SocialHandleEvidence.objects.exists()


@pytest.mark.django_db
def test_apply_creates_confirmed_accounts_with_camp(monkeypatch):
    staff = get_user_model().objects.create_user('ordynator', password='x', is_staff=True)
    entry = mp('Jan Kowalski', 'PiS', '1')
    monkeypatch.setattr(command.requests, 'get', lambda *args, **kwargs: wikidata([('Jan Kowalski', 'jankowalski')]))

    def fake_resolve(candidate, confirmed_by):
        account = PoliticalAccount.objects.create(user_id='42', handle=candidate.handle, display_name=candidate.display_name,
                                                  camp=candidate.proposed_camp, confirmation_url=candidate.confirmation_url)
        account.confirm(confirmed_by)
        candidate.resolved_account = account
        candidate.save(update_fields=['resolved_account'])
        return account
    monkeypatch.setattr(command, 'resolve_candidate', fake_resolve)
    monkeypatch.setattr(command, 'official_identity', lambda handle, name: (True, ''))
    call_command('link_official_x_accounts', '--skip-discovery', '--wikidata', '--apply', '--enable',
                 '--confirmed-by', 'ordynator', stdout=StringIO())
    account = PoliticalAccount.objects.get()
    assert account.camp == 'opposition' and account.enabled and account.is_confirmed()
    evidence = SocialHandleEvidence.objects.get()
    assert evidence.roster_entry == entry and evidence.status == 'candidate_created' and evidence.reviewed_by == staff


def test_senate_footer_accounts_are_never_personal():
    assert 'polskisenat' in command.INSTITUTIONAL_HANDLES


def test_official_identity_requires_surname_and_rejects_parody(monkeypatch):
    monkeypatch.setenv('X_POLITICAL_BEARER_TOKEN', 't')

    class XReply:
        status_code = 200
        def __init__(self, data):
            self.data = data
        def json(self):
            return {'data': self.data}
    replies = {'real': {'name': 'Jan Kowalski', 'username': 'real', 'description': 'Poseł na Sejm RP'},
               'fake': {'name': 'Prawdziwy Patriota', 'username': 'fake', 'description': ''},
               'parody': {'name': 'Jan Kowalski', 'username': 'parody', 'description': 'Konto parodystyczne'}}
    monkeypatch.setattr(command.requests, 'get', lambda url, **kwargs: XReply(replies[url.rsplit('/', 1)[1]]))
    assert command.official_identity('real', 'Jan Kowalski') == (True, '')
    assert command.official_identity('fake', 'Jan Kowalski')[0] is False
    assert command.official_identity('parody', 'Jan Kowalski')[0] is False


@pytest.mark.django_db
def test_missing_token_stops_without_rejecting_evidence(monkeypatch):
    from django.core.management.base import CommandError
    get_user_model().objects.create_user('ordynator', password='x', is_staff=True)
    mp('Jan Kowalski', 'KO', '1')
    monkeypatch.delenv('X_POLITICAL_BEARER_TOKEN', raising=False)
    monkeypatch.setattr(command.requests, 'get', lambda *args, **kwargs: wikidata([('Jan Kowalski', 'jankowalski')]))
    with pytest.raises(CommandError):
        call_command('link_official_x_accounts', '--skip-discovery', '--wikidata', '--apply', '--confirmed-by', 'ordynator',
                     stdout=StringIO())
    assert SocialHandleEvidence.objects.get().status == 'pending_review'


@pytest.mark.django_db
def test_reopen_rejected_restores_technical_rejections():
    entry = mp('Jan Kowalski', 'KO', '1')
    SocialHandleEvidence.objects.create(roster_entry=entry, platform='x', handle='jankowalski', status='rejected',
                                        evidence_url='https://www.wikidata.org/wiki/Q1', extracted_url='https://x.com/jankowalski')
    call_command('link_official_x_accounts', '--skip-discovery', '--reopen-rejected', stdout=StringIO())
    assert SocialHandleEvidence.objects.get().status == 'pending_review'


def test_identity_rejects_squatted_short_surname_handle_and_fresh_accounts():
    from datetime import datetime, timezone as tz
    now = datetime(2026, 9, 28, tzinfo=tz.utc)
    # 28.09.2026: @AgaBak — obca osoba zajęła starą nazwę ministry; „bak” było tylko fragmentem „Agabak”.
    squatter = {'name': 'Agaba', 'username': 'Agabak', 'description': '', 'created_at': '2026-07-10T10:00:00.000Z',
                'public_metrics': {'followers_count': 2}}
    real = {'name': 'A. Dziemianowicz-Bąk', 'username': 'a_dziemianowicz', 'description': 'Ministra Rodziny, Pracy i Polityki Społecznej',
            'created_at': '2009-06-17T07:21:36.000Z', 'public_metrics': {'followers_count': 94346}}
    assert command.identity_problem(squatter, 'Agnieszka Dziemianowicz-Bąk')
    assert command.identity_problem(real, 'Agnieszka Dziemianowicz-Bąk', now) == ''
    fresh = {**real, 'created_at': '2026-06-01T00:00:00.000Z', 'public_metrics': {'followers_count': 150}}
    assert 'niedawno' in command.identity_problem(fresh, 'Agnieszka Dziemianowicz-Bąk', now)
    # długie nazwisko w samej nazwie użytkownika wystarcza (np. @donaldtusk przy nazwie „Donald Tusk”)
    assert command.identity_problem({'name': 'DT', 'username': 'donaldtusk'}, 'Donald Tusk') == ''

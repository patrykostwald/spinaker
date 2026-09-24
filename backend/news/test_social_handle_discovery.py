import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from news.political_admin import SocialHandleEvidenceAdmin
from news.political_models import ParliamentaryRosterEntry, PoliticalAccountCandidate, SocialHandleEvidence
from news.social_handle_discovery import SocialDiscoveryError, discover_for_entry, extract_x_links

pytestmark = pytest.mark.django_db


class Response:
    status_code = 200
    headers = {'Content-Type': 'text/html; charset=utf-8'}
    encoding = 'utf-8'
    def __init__(self, html): self.content = html.encode()


def entry(**overrides):
    values = {'source': 'sejm', 'external_id': '1', 'full_name': 'Anna Przykład',
        'profile_url': 'https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id=1',
        'source_url': 'https://api.sejm.gov.pl/sejm/term10/MP'}
    values.update(overrides)
    return ParliamentaryRosterEntry.objects.create(**values)


def test_extracts_only_explicit_account_links_from_html():
    links = extract_x_links('''<a href="https://x.com/Anna_Test">X</a>
      <a href="https://twitter.com/Drugi_2/status/11">drugi</a>
      <p>@NieWolnoZgadnac</p><a href="https://x.com/intent/post">share</a>''')
    assert links == [('Anna_Test', 'https://x.com/Anna_Test'), ('Drugi_2', 'https://twitter.com/Drugi_2/status/11')]


def test_discovery_stages_evidence_only_and_never_candidates_or_x_api():
    row = entry()
    evidence = discover_for_entry(row, http_get=lambda *args, **kwargs: Response('<a href="https://x.com/Anna_Test">X</a>'))
    assert len(evidence) == 1
    saved = SocialHandleEvidence.objects.get()
    assert saved.handle == 'Anna_Test'
    assert saved.status == 'pending_review'
    assert saved.candidate is None
    assert not PoliticalAccountCandidate.objects.filter(handle='Anna_Test').exists()


def test_discovery_fails_closed_for_unapproved_host_or_non_html():
    row = entry(profile_url='https://attacker.example/profile')
    with pytest.raises(SocialDiscoveryError, match='zatwierdzonym'):
        discover_for_entry(row, http_get=lambda *args, **kwargs: pytest.fail('network called'))
    row = entry(external_id='2')
    response = Response('<a href="https://x.com/Anna_Test">X</a>')
    response.headers = {'Content-Type': 'application/json'}
    with pytest.raises(SocialDiscoveryError, match='HTML'):
        discover_for_entry(row, http_get=lambda *args, **kwargs: response)


def test_admin_review_creates_manual_candidate_only():
    staff = get_user_model().objects.create_user('editor', is_staff=True)
    row = entry()
    evidence = SocialHandleEvidence.objects.create(roster_entry=row, handle='Anna_Test',
        evidence_url=row.profile_url, extracted_url='https://x.com/Anna_Test')
    model_admin = SocialHandleEvidenceAdmin(SocialHandleEvidence, admin.site)
    class Request: user = staff
    model_admin.message_user = lambda *args, **kwargs: None
    model_admin.create_candidates_after_review(Request(), SocialHandleEvidence.objects.filter(pk=evidence.pk))
    evidence.refresh_from_db()
    assert evidence.status == 'candidate_created'
    assert evidence.candidate.classification == 'independent'
    assert evidence.candidate.proposed_camp == ''


def test_command_dry_run_does_not_write(monkeypatch):
    entry()
    monkeypatch.setattr('news.management.commands.discover_official_social_handles.discover_for_entry',
        lambda row, persist: [('Anna_Test', 'https://x.com/Anna_Test')])
    call_command('discover_official_social_handles', source='sejm', limit=1, dry_run=True)
    assert not SocialHandleEvidence.objects.exists()
    with pytest.raises(CommandError, match='od 1 do 100'):
        call_command('discover_official_social_handles', source='sejm', limit=0)

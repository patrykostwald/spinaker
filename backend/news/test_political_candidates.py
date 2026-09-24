import pytest
from django.contrib.auth import get_user_model

from news.political_candidates import CandidateResolutionError, resolve_candidate
from news.political_models import PoliticalAccount, PoliticalAccountCandidate

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor():
    return get_user_model().objects.create_user(username='candidate-editor', is_staff=True)


def candidate(**overrides):
    values = {'handle': 'testhandle', 'display_name': 'Test account', 'classification': 'government',
              'proposed_camp': 'government', 'confirmation_url': 'https://example.org/proof'}
    values.update(overrides)
    return PoliticalAccountCandidate.objects.create(**values)


def test_public_candidate_resolves_to_public_account(editor, monkeypatch):
    item = candidate(handle='publicitem', classification='public', proposed_camp='')
    monkeypatch.setenv('X_POLITICAL_BEARER_TOKEN', 'test-token')
    class Response:
        status_code = 200
        def json(self): return {'data': {'id': '222222', 'username': 'publicitem'}}
    monkeypatch.setattr('news.political_candidates.requests.get', lambda *args, **kwargs: Response())
    account = resolve_candidate(item, editor)
    assert account.camp == 'public' and not account.enabled and account.is_confirmed()


def test_explicit_resolution_creates_confirmed_disabled_account(editor, monkeypatch, settings):
    settings.X_POLITICAL_BEARER_TOKEN = 'unused'
    monkeypatch.setenv('X_POLITICAL_BEARER_TOKEN', 'test-token')
    item = candidate()
    class Response:
        status_code = 200
        def json(self): return {'data': {'id': '123456', 'username': 'testhandle', 'name': 'Different display'}}
    monkeypatch.setattr('news.political_candidates.requests.get', lambda *args, **kwargs: Response())
    account = resolve_candidate(item, editor)
    assert account.user_id == '123456' and not account.enabled and account.is_confirmed()
    item.refresh_from_db()
    assert item.resolved_account_id == account.id and not item.resolution_error


def test_existing_handle_links_without_x_lookup(editor, monkeypatch):
    existing = PoliticalAccount.objects.create(
        user_id='987654', handle='ExistingHandle', display_name='Existing account',
        camp='government', confirmation_url='https://example.org/existing', enabled=True,
    )
    existing.confirm(editor)
    item = candidate(handle='existinghandle')
    monkeypatch.setattr('news.political_candidates.requests.get', lambda *args, **kwargs: pytest.fail('X called'))
    assert resolve_candidate(item, editor) == existing
    item.refresh_from_db(); existing.refresh_from_db()
    assert item.resolved_account_id == existing.id
    assert existing.enabled is True and existing.is_confirmed()

from django.core.files.uploadedfile import SimpleUploadedFile
from news.political_candidate_import import validate_candidate_csv, create_candidates_from_preview


def test_candidate_csv_preview_does_not_call_x_or_create_rows():
    before = PoliticalAccountCandidate.objects.count()
    upload = SimpleUploadedFile('candidates.csv', b'handle,display_name,classification,confirmation_url,confirmation_note,proposed_camp\npublicone,Public One,public,https://example.org/proof,Official reference,\n')
    rows, errors = validate_candidate_csv(upload)
    assert not errors and not rows[0]['errors']
    assert PoliticalAccountCandidate.objects.count() == before
    created = create_candidates_from_preview(rows)
    assert created[0].classification == 'public' and not created[0].resolved_account_id

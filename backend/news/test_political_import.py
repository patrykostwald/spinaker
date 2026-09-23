import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from news.political_import import create_from_preview, validate_csv
from news.political_models import PoliticalAccount


pytestmark = pytest.mark.django_db


HEADER = 'user_id,handle,display_name,camp,confirmation_url,confirmation_note,poll_interval_minutes\n'
ROW = '375146901,donaldtusk,Donald Tusk,government,https://example.org/tusk,Oficjalna strona,15\n'


def upload(text):
    return SimpleUploadedFile('accounts.csv', text.encode(), content_type='text/csv')


def test_preview_validates_without_writing_or_enabling():
    rows, errors = validate_csv(upload(HEADER + ROW))
    assert not errors and not rows[0]['errors']
    assert not PoliticalAccount.objects.exists()
    created = create_from_preview(rows)
    assert created[0].enabled is False
    assert created[0].confirmed_at is None


def test_preview_rejects_duplicates_and_bad_identifiers():
    rows, errors = validate_csv(upload(HEADER + ROW + 'not-an-id,donaldtusk,Again,government,https://example.org/again,Note,15\n'))
    assert not errors
    assert rows[1]['errors']
    assert not PoliticalAccount.objects.exists()


def test_import_page_requires_preview_and_creates_disabled_account():
    staff = get_user_model().objects.create_user(username='staff-import', password='secret', is_staff=True)
    client = Client(); client.force_login(staff)
    url = reverse('admin:news_politicalaccount_import_csv')
    response = client.post(url, {'csv_file': upload(HEADER + ROW)})
    assert response.status_code == 200 and response.context['can_import'] is True
    response = client.post(url, {'confirm_import': '1'})
    assert response.status_code == 302
    account = PoliticalAccount.objects.get(handle='donaldtusk')
    assert not account.enabled and not account.confirmed_at

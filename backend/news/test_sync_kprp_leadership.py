from io import StringIO

import pytest
from django.core.management import call_command

from news.management.commands.sync_kprp_leadership import KPRP_LEADERSHIP
from news.political_models import PublicFigure


@pytest.mark.django_db
def test_sync_kprp_leadership_uses_stable_official_keys():
    call_command('sync_kprp_leadership', stdout=StringIO())
    assert PublicFigure.objects.filter(import_key__startswith='kprp-leadership:', status='current').count() == len(KPRP_LEADERSHIP)
    assert PublicFigure.objects.get(import_key='kprp-leadership:chief-of-chancellery').canonical_name == 'Zbigniew Bogucki'


@pytest.mark.django_db
def test_sync_kprp_leadership_marks_absent_key_former(monkeypatch):
    PublicFigure.objects.create(canonical_name='Była osoba', role_category='government', role_title='Rola',
        evidence_url='https://kprp.example/roster', import_key='kprp-leadership:former', status='current')
    monkeypatch.setattr('news.management.commands.sync_kprp_leadership.KPRP_LEADERSHIP', KPRP_LEADERSHIP[:1])
    call_command('sync_kprp_leadership', stdout=StringIO())
    assert PublicFigure.objects.get(import_key='kprp-leadership:former').status == 'former'

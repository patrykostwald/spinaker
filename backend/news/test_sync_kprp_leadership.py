from io import StringIO

import pytest
from django.core.management import call_command

from news.management.commands.sync_kprp_leadership import KPRP_LEADERSHIP
from news.political_models import PublicFigure, PublicFigureRole, PublicOffice


@pytest.mark.django_db
def test_sync_kprp_leadership_uses_stable_official_keys():
    call_command('sync_kprp_leadership', stdout=StringIO())
    assert PublicFigure.objects.filter(import_key__startswith='kprp-leadership:', status='current').count() == len(KPRP_LEADERSHIP)
    office = PublicOffice.objects.get(import_key='public-office:kprp:chief-of-chancellery')
    assert office.current_holder.canonical_name == 'Zbigniew Bogucki'
    assert PublicFigureRole.objects.get(public_office=office, status='current').public_figure == office.current_holder


@pytest.mark.django_db
def test_sync_kprp_leadership_marks_absent_key_former(monkeypatch):
    PublicFigure.objects.create(canonical_name='Była osoba', role_category='government', role_title='Rola',
        evidence_url='https://kprp.example/roster', import_key='kprp-leadership:former:holder:byla-osoba', status='current')
    monkeypatch.setattr('news.management.commands.sync_kprp_leadership.KPRP_LEADERSHIP', KPRP_LEADERSHIP[:1])
    call_command('sync_kprp_leadership', stdout=StringIO())
    assert PublicFigure.objects.get(import_key='kprp-leadership:former:holder:byla-osoba').status == 'former'


@pytest.mark.django_db
def test_sync_kprp_leadership_archives_only_the_legacy_technical_duplicate():
    key, name, _ = KPRP_LEADERSHIP[0]
    legacy = PublicFigure.objects.create(canonical_name=name, role_category='government', role_title='Dawna forma wpisu',
        evidence_url='https://kprp.example/roster', import_key=f'kprp-leadership:{key}', status='former')
    call_command('sync_kprp_leadership', stdout=StringIO())
    legacy.refresh_from_db()
    assert legacy.archived is True
    assert PublicOffice.objects.get(import_key=f'public-office:kprp:{key}').current_holder.archived is False

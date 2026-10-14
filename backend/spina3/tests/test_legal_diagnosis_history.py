"""S2 pkt 3: log zatwierdzeń diagnozy (wersje: konto zespołu bez imienia, kiedy, model, źródła, etykieta)."""
from __future__ import annotations

import pytest

from spina3 import importer
from spina3.models import Box, DiagnosisApproval

from .conftest import make_user
from .test_importer import account, diagnosis, post

pytestmark = pytest.mark.django_db


def test_history_recorded_on_import_and_each_change(api):
    staff = make_user('zatwierdzajacy', staff=True)
    staff.first_name, staff.last_name = 'Anna', 'Nowak'
    staff.save()
    p = post(account())
    d = diagnosis(p, staff=staff)
    d.provider, d.model_name = 'anthropic', 'model-testowy'
    d.claims = [{'text': 'teza', 'source_url': 'https://www.gov.pl/dane'}]
    d.save()
    box, _ = importer.sync_diagnosis(d)
    importer.sync_diagnosis(d)   # bez zmian: bez nowej wersji
    assert DiagnosisApproval.objects.count() == 1
    d.summary = 'Poprawione podsumowanie.'
    d.save()
    importer.sync_diagnosis(d)
    post_box = Box.objects.get(post=p)
    history = api.get(f'/api/spina3/box/{post_box.pk}/').json()['diagnosis_history']
    assert [h['version'] for h in history] == [1, 2] and [h['change'] for h in history] == ['created', 'updated']
    first = history[0]
    assert first['approved_by'] == f'konto zespołu nr {staff.pk}' and first['model'] == 'anthropic/model-testowy'
    assert first['label'] == 'Diagnoza AI, zatwierdzona przez zespół spin.clinic' and first['approved_at']
    assert p.url in first['sources'] and 'https://www.gov.pl/dane' in first['sources']
    assert history[1]['current'] and not history[0]['current']
    assert 'Nowak' not in str(history) and 'Anna' not in str(history) and 'zatwierdzajacy' not in str(history)
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['diagnosis_history'] == history


def test_withdrawal_is_a_version():
    staff = make_user('zespol_w', staff=True)
    d = diagnosis(post(account()), staff=staff)
    box, _ = importer.sync_diagnosis(d)
    d.status = 'withdrawn'
    d.save()
    importer.sync_diagnosis(d)
    rows = list(DiagnosisApproval.objects.filter(diagnosis_box=box).order_by('version'))
    assert [r.change for r in rows] == ['created', 'withdrawn']
    assert not any(h['current'] for h in importer.diagnosis_history(box))

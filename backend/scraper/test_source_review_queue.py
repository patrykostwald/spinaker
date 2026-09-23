from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceType


@pytest.mark.django_db
def test_review_queue_separates_failed_official_rss_and_portal_candidates(tmp_path):
    broken = Source.objects.create(name='Broken', url='https://broken.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    official = Source.objects.create(name='Official', url='https://official.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    portal = Source.objects.create(name='Portal', url='https://portal.example', source_type=SourceType.PORTAL,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{broken.pk}', cursor={'audit_status': 'failed', 'rss': {'status': 'not_found'}})
    ImportState.objects.create(name=f'source-check:{official.pk}', cursor={'audit_status': 'completed', 'rss': {'status': 'working'}})
    output = tmp_path / 'queue.md'
    stream = StringIO()
    call_command('source_review_queue', '--output', str(output), stdout=stream)
    report = output.read_text(encoding='utf-8')
    assert 'Błędy techniczne — nie aktywować (1)' in report
    assert 'Instytucje z działającym RSS — sprawdzić warunki i kartę dostępu (1)' in report
    assert 'Wydawcy i organizacje — wymagają warunków lub zgody (1)' in report
    assert output.with_suffix('.json').exists()


@pytest.mark.django_db
def test_review_queue_can_export_only_institutional_rss_candidates(tmp_path):
    Source.objects.create(name='RSS', url='https://rss.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    other = Source.objects.create(name='Portal', url='https://portal.example', source_type=SourceType.PORTAL,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    rss = Source.objects.get(name='RSS')
    ImportState.objects.create(name=f'source-check:{rss.pk}', cursor={
        'audit_status': 'completed', 'rss': {'status': 'working'},
    })
    output = tmp_path / 'rss-only.md'
    call_command('source_review_queue', '--bucket', '02_instytucja_rss_do_warunkow',
        '--output', str(output), stdout=StringIO())
    report = output.read_text(encoding='utf-8')
    assert 'Kandydaci w raporcie: **1**. Wszystkich kandydatów: **2**.' in report
    assert 'RSS' in report
    assert other.name not in report

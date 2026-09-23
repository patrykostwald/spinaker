import json
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
import pytest
from news.models import Source, ImportState, SourceAccessInstruction
from scraper.source_probe import source_signature


@pytest.mark.django_db
def test_apply_verified_feed_requires_matching_approved_card(tmp_path):
    sources=[]
    for index in range(3):
        s=Source.objects.create(name=f'Publisher {index}',url=f'https://publisher{index}.pl',
            catalog_stage='candidate',is_active=False,scrape_enabled=False,scrape_frequency_minutes=12)
        ImportState.objects.create(name=f'source-check:{s.pk}',last_success=timezone.now(),cursor={
            'signature':source_signature(s),'audit_status':'completed','checked_at':timezone.now().isoformat(),
            'rss':{'status':'working','url':f'https://publisher{index}.pl/feed','usable_entry_count':10}})
        sources.append(s)
    SourceAccessInstruction.objects.create(
        source=sources[0], version=1, status='approved', channel='rss', allowed_scope='metadata',
        endpoint='https://publisher0.pl/feed', terms_url='https://publisher0.pl/terms',
        evidence={'review': 'publisher permits RSS metadata'}, minimum_interval_seconds=3,
        daily_request_cap=24, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=30))
    sources[1].rss_url='https://publisher1.pl/owner-feed'
    sources[1].save()
    sources[2].catalog_stage='excluded'
    sources[2].save()
    path=tmp_path/'applied.json'
    argv=[part for s in sources for part in ('--source-id',str(s.pk))]
    call_command('apply_audited_feeds',*argv,report=str(path))
    for s in sources:s.refresh_from_db()
    assert sources[0].is_active and sources[0].scrape_enabled
    assert sources[0].scrape_frequency_minutes==12
    assert sources[0].rss_url=='https://publisher0.pl/feed'
    assert sources[1].rss_url=='https://publisher1.pl/owner-feed' and not sources[1].is_active
    assert sources[2].catalog_stage=='excluded' and not sources[2].is_active
    result=json.loads(path.read_text('utf-8'))
    assert len(result['changes'])==1
    assert result['skipped'] == [
        {'id': sources[1].pk, 'reason': 'audit_not_current_or_feed_unusable'},
        {'id': sources[2].pk, 'reason': 'audit_not_current_or_feed_unusable'},
    ]


@pytest.mark.django_db
def test_apply_verified_feed_does_not_activate_without_editorial_card(tmp_path):
    source=Source.objects.create(name='No card',url='https://no-card.example',
        catalog_stage='candidate',is_active=False,scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}',last_success=timezone.now(),cursor={
        'signature':source_signature(source),'audit_status':'completed','checked_at':timezone.now().isoformat(),
        'rss':{'status':'working','url':'https://no-card.example/feed','usable_entry_count':1}})
    path=tmp_path/'report.json'
    call_command('apply_audited_feeds','--source-id',str(source.pk),'--report',str(path))
    source.refresh_from_db()
    assert not source.is_active and source.catalog_stage == 'candidate'
    assert json.loads(path.read_text('utf-8'))['skipped'] == [
        {'id': source.pk, 'reason': 'missing_approved_access_card'}]

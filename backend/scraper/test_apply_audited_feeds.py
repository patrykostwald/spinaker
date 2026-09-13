import json
from django.core.management import call_command
from django.utils import timezone
import pytest
from news.models import Source, ImportState
from scraper.source_probe import source_signature


@pytest.mark.django_db
def test_apply_verified_feed_preserves_frequency_and_rejects_changed_or_excluded_source(tmp_path):
    sources=[]
    for index in range(3):
        s=Source.objects.create(name=f'Publisher {index}',url=f'https://publisher{index}.pl',
            catalog_stage='candidate',is_active=False,scrape_enabled=False,scrape_frequency_minutes=12)
        ImportState.objects.create(name=f'source-check:{s.pk}',last_success=timezone.now(),cursor={
            'signature':source_signature(s),'audit_status':'completed','checked_at':timezone.now().isoformat(),
            'rss':{'status':'working','url':f'https://publisher{index}.pl/feed','usable_entry_count':10}})
        sources.append(s)
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
    assert len(result['changes'])==1 and result['skipped']==[sources[1].pk,sources[2].pk]

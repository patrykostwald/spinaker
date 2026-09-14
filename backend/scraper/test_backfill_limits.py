from unittest.mock import patch

import pytest

from news.models import ArchiveJob, Source
from scraper.archive import run_batch


@pytest.mark.django_db
def test_run_batch_enforces_limit_per_source():
    sources = [Source.objects.create(name=f'Pilot {index}', url=f'https://pilot-{index}.example') for index in range(2)]
    for source in sources:
        for index in range(3):
            ArchiveJob.objects.create(source=source, url=f'{source.url}/{index}', kind='page')
    handled = []
    with patch('scraper.archive.process', side_effect=lambda job: handled.append(job.source_id) or 0), patch('scraper.archive.time.sleep'):
        run_batch(6, source_ids=[source.pk for source in sources], per_source_limit=1)
    assert handled.count(sources[0].pk) == 1
    assert handled.count(sources[1].pk) == 1
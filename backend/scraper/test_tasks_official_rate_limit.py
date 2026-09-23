from unittest.mock import patch

import pytest

from news.models import ImportState
from scraper.tasks import import_official_task
from scraper.utils import HostRateLimited


@pytest.mark.django_db
def test_official_eli_task_defers_when_host_gateway_sets_retry_window():
    with patch('scraper.official.official_access_allowed', return_value=True), \
            patch('scraper.official.import_eli_changes', side_effect=HostRateLimited(1800)):
        result = import_official_task.run('eli')

    assert result == {'status': 'deferred', 'new_records': 0, 'retry_after_seconds': 1800}
    assert ImportState.objects.get(name='official:eli').last_error == 'host_rate_limited:1800.000'

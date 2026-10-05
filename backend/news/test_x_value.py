from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.mark.django_db
def test_value_plan_reads_valuable_accounts_often():
    from news import x_value
    from news.political_models import PoliticalAccount, PoliticalPost
    now = timezone.now()
    def acc(handle, uid):
        return PoliticalAccount.objects.create(handle=handle, user_id=uid, display_name=handle, camp='government', enabled=True, poll_interval_minutes=15)
    busy, quiet = acc('busy', '101'), acc('quiet', '102')
    for i in range(12):
        PoliticalPost.objects.create(account=busy, post_id=str(9000 + i), url='https://x.com/a', text='t', published_at=now - timedelta(days=1),
                                     response_sha256='x', camp_at_collection='government')
    plan = x_value.plan()
    assert plan[busy.pk][0] == x_value.NORMAL and plan[quiet.pk][0] == x_value.SLOW
    result = x_value.apply()
    assert result['changed'] == 2 and result['requests_day_after'] < result['requests_day_before']
    busy.refresh_from_db()
    assert busy.poll_interval_minutes == x_value.NORMAL

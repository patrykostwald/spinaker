from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from news.clinic_models import SpinDiagnosis
from news.test_clinic import account, post

pytestmark = pytest.mark.django_db


def test_ranking_counts_visibility_period_camps_and_ties():
    client = APIClient()
    now = timezone.now()
    day = timezone.localdate(now)
    for index, camp in enumerate(('government', 'opposition')):
        acc = account(camp=camp, handle=f'ranking_{index}', user_id=str(800 + index))
        expected = []
        for number, intensity in enumerate((20, 90, 70, 90, 50)):
            item = post(acc, post_id=f'{index}{number}', hours_ago=0)
            # Identical timestamps also exercise the stable PK tie-breaker.
            item.published_at = now
            item.save(update_fields=['published_at'])
            row = SpinDiagnosis.objects.create(post=item, status='approved', verdict='spin', intensity=intensity)
            expected.append(row)
        for number, fields, hours in (
            (6, {'status': 'pending_review'}, 0),
            (7, {'hidden_at': now}, 0),
            (8, {}, 24 * 9),
        ):
            SpinDiagnosis.objects.create(post=post(acc, post_id=f'{index}{number}', hours_ago=hours),
                                         verdict='spin', intensity=100, **({'status': 'approved'} | fields))
        params = {'camp': camp, 'sort': 'strong', 'page_size': 3,
                  'date_from': str(day - timedelta(days=6)), 'date_to': str(day)}
        response = client.get('/api/clinic/spins/', params)
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 5
        assert [row['id'] for row in data['results']] == [expected[i].pk for i in (3, 1, 2)]
        assert all(row['camp'] == camp for row in data['results'])
        assert data['next_page'] == 2
        second = client.get('/api/clinic/spins/', params | {'page': 2}).json()
        assert [row['id'] for row in second['results']] == [expected[i].pk for i in (4, 0)]
        assert second['count'] == 5 and second['next_page'] is None


@pytest.mark.parametrize('size', ['0', '-1', '21', 'abc', '1.5'])
def test_ranking_rejects_invalid_page_size(size):
    assert APIClient().get('/api/clinic/spins/', {'page_size': size}).status_code == 400

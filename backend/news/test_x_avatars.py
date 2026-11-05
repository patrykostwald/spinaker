"""Miniatury kont X (13.10): podstawione odpowiedzi API, walidacja hosta i tożsamości, budżet, dry-run, pierwszeństwo
danych wpisu przed miniaturą konta. Bez sieci."""
import json
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from news import x_avatars
from news.clinic import _post_avatar, author_data
from news.models import ImportState
from news.political_models import PoliticalAccount
from news.test_clinic import post, staff

pytestmark = pytest.mark.django_db

CONFIG = {'token': 'test', 'daily_requests': 100, 'monthly_usd': Decimal('5')}


def accounts(n=3):
    editor = staff()
    out = []
    for i in range(n):
        acc = PoliticalAccount.objects.create(user_id=str(1000 + i), handle=f'konto_{i}', display_name=f'Konto {i}', camp='government',
                                              enabled=True, confirmation_url='https://sejm.gov.pl', confirmation_note='ok')
        acc.confirm(editor)
        out.append(acc)
    return out


def x_payload(rows):
    return json.dumps({'data': rows}).encode()


@pytest.mark.parametrize('value,expected', [
    ('https://pbs.twimg.com/profile_images/1/a_normal.jpg', 'https://pbs.twimg.com/profile_images/1/a_bigger.jpg'),
    ('http://pbs.twimg.com/profile_images/1/a_normal.jpg', ''),
    ('https://pbs.twimg.com.evil.com/profile_images/1/a.jpg', ''),
    ('https://evil.com/profile_images/1/a.jpg', ''),
    ('https://pbs.twimg.com/media/abc.jpg', ''),
    ('https://pbs.twimg.com/profile_images/1/a.jpg?x=1', ''),
    ('javascript:alert(1)', ''),
    (None, ''),
])
def test_clean_avatar_host_validation(value, expected):
    assert x_avatars.clean_avatar(value) == expected


def test_refresh_one_call_per_100_with_identity_check(monkeypatch):
    acc = accounts(3)
    calls = []

    def fake_request(url, params, config):
        calls.append((url, params))
        return x_payload([
            {'id': '1000', 'username': 'konto_0', 'profile_image_url': 'https://pbs.twimg.com/profile_images/1/a_normal.jpg'},
            {'id': '9999', 'username': 'konto_1', 'profile_image_url': 'https://pbs.twimg.com/profile_images/2/b_normal.jpg'},
            {'id': '1002', 'username': 'KONTO_2', 'profile_image_url': 'https://evil.com/c.jpg'}])
    monkeypatch.setattr('news.political_polling.request_x', fake_request)
    result = x_avatars.refresh(config=CONFIG)
    assert len(calls) == 1 and calls[0][0] == 'https://api.x.com/2/users/by'
    assert calls[0][1] == {'usernames': 'konto_0,konto_1,konto_2', 'user.fields': 'profile_image_url'}
    assert result['updated'] == 1 and result['empty'] == 2
    acc[0].refresh_from_db()
    acc[1].refresh_from_db()
    assert acc[0].avatar_url == 'https://pbs.twimg.com/profile_images/1/a_bigger.jpg' and acc[0].avatar_checked_at
    assert acc[1].avatar_url == ''  # id z X nie zgadza się z kontem: bez zapisu
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['daily_requests'] == 1 and Decimal(budget['spent_upper_usd']) == Decimal('0.030') and not budget.get('lease')
    assert x_avatars.refresh(config=CONFIG)['accounts'] == 0  # odświeżenie najwyżej co 30 dni


def test_no_budget_stops_without_call(monkeypatch):
    accounts(2)
    ImportState.objects.create(name='political-x-budget', cursor={
        'month': timezone.now().strftime('%Y-%m'), 'day': timezone.now().date().isoformat(), 'daily_requests': 100,
        'spent_upper_usd': '0'})
    monkeypatch.setattr('news.political_polling.request_x', lambda *a: pytest.fail('nie wolno wołać API bez budżetu'))
    with pytest.raises(x_avatars.AvatarError) as error:
        x_avatars.refresh(config=CONFIG)
    assert 'brak budżetu' in str(error.value)
    assert PoliticalAccount.objects.filter(avatar_checked_at__isnull=False).count() == 0


def test_monthly_limit_and_lease_respected(monkeypatch):
    accounts(2)
    state = ImportState.objects.create(name='political-x-budget', cursor={
        'month': timezone.now().strftime('%Y-%m'), 'spent_upper_usd': '4.995'})
    with pytest.raises(x_avatars.AvatarError):
        x_avatars.refresh(config=CONFIG)
    state.cursor = {'lease_until': (timezone.now() + timezone.timedelta(minutes=1)).isoformat()}
    state.save()
    with pytest.raises(x_avatars.AvatarError) as error:
        x_avatars.refresh(config=CONFIG)
    assert 'zajęty' in str(error.value)


def test_dry_run_and_command(monkeypatch):
    accounts(3)
    monkeypatch.setattr('news.political_polling.request_x', lambda *a: pytest.fail('dry-run bez API'))
    result = x_avatars.refresh(dry_run=True)
    assert result == {'accounts': 3, 'calls': 1, 'usd_upper': '0.030', 'updated': 0, 'empty': 0, 'dry_run': True}
    call_command('x_avatary', 'odswiez', '--dry-run')
    monkeypatch.setattr('news.political_polling.configuration', lambda: None)
    with pytest.raises(CommandError):
        call_command('x_avatary', 'odswiez')


def test_post_data_wins_then_account_avatar():
    acc = accounts(1)[0]
    PoliticalAccount.objects.filter(pk=acc.pk).update(avatar_url='https://pbs.twimg.com/profile_images/9/z_bigger.jpg')
    acc.refresh_from_db()
    row = post(acc, post_id='777')
    assert _post_avatar(row) == 'https://pbs.twimg.com/profile_images/9/z_bigger.jpg'
    assert author_data(row, None)['avatar_url'] == 'https://pbs.twimg.com/profile_images/9/z_bigger.jpg'
    row.author_data = {'profile_image_url': 'https://pbs.twimg.com/profile_images/1/a_normal.jpg'}
    assert _post_avatar(row) == 'https://pbs.twimg.com/profile_images/1/a_bigger.jpg'

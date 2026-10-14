"""Fixtury testów spina3 (SQLite testowe, bez sieci: globalny strażnik w news/conftest.py nie działa tu, więc własny)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


@pytest.fixture(autouse=True)
def zakaz_sieci(monkeypatch):
    import requests
    from unittest.mock import Mock
    monkeypatch.setattr('requests.adapters.HTTPAdapter.send', Mock(side_effect=requests.ConnectionError('Zakaz sieci w testach')))


@pytest.fixture(autouse=True)
def spina3_settings(settings):
    """Model: bez okna otwartego i limitu stopnia w testach API (testowane osobno w modelu), zgoda art. 9 przez fixture."""
    settings.SPINA3 = {'scoring': {'open_window_hours': 0, 'level_step_per_day': 0, 'mode': 'zgodnosc', 'burst_max_pins': 10_000,
                                   'same_target_30d': {'T1': 10_000, 'T2': 10_000, 'T3': 10_000},
                                   'daily_pins': {'T0': 0, 'T1': 5, 'T2': 10_000, 'T3': 10_000, 'team': 0},
                                   'burst_max_ratings': 10_000,
                                   'daily_ratings': {'T0': 0, 'T1': 30, 'T2': 10_000, 'T3': 10_000, 'team': 10_000}},
                       'flags': {'enabled': True, 'pins_enabled': True, 'levels_visible': True, 'views_enabled': True,
                                 'url_pins_enabled': True, 'allow_image_pins': False, 'url_fetch_enabled': False,
                                 'election_silence_start': '', 'election_silence_end': '', 'auth_mode': 'session'}}
    from django.core.cache import cache
    cache.clear()
    return settings


def make_user(username: str, *, verified=True, days_old=30, staff=False, team=False, consent=True, tier='T2'):
    """Domyślnie konto dojrzałe (T2 nadane ręcznie: waga 1); testy wag i limitów podają tier='' (T1 z automatu)."""
    from news.account_models import AccountIdentity
    from spina3.models import Spina3Profile
    user = get_user_model().objects.create_user(username=username, email=f'{username}@example.org', password='x' * 12, is_staff=staff)
    user.date_joined = timezone.now() - timedelta(days=days_old)
    user.save(update_fields=['date_joined'])
    AccountIdentity.objects.create(user=user, email=user.email, email_verified=verified)
    profile = Spina3Profile.for_user(user)
    profile.is_team = team
    profile.tier_manual = tier if days_old >= 14 else ''
    profile.consent_art9_at = timezone.now() if consent else None
    profile.age_16_plus_at = profile.consent_art9_at   # S2: zgoda zawsze z oświadczeniem 16+
    profile.save()
    return user


def make_box(title='Box', kind='article', **kwargs):
    from spina3.models import Box
    from spina3.text import normalize
    counter = Box.objects.count() + 1
    defaults = dict(kind=kind, title=title, url=kwargs.pop('url', f'https://example.org/{kind}/{counter}'),
                    source_name='Portal Testowy', source_domain='example.org', published_at=timezone.now() - timedelta(hours=counter),
                    search_text=normalize(title), show_quote=True)
    defaults.update(kwargs)
    return Box.objects.create(**defaults)


def author_pin(user, box, target, comment='', stance=None, **kwargs):
    """Autor dodaje jedyne przypięcie do boxa z bazy (box bez przypięcia): dowód = inny box z bazy."""
    from spina3.pins import create_box_with_pin
    return create_box_with_pin(user, box_kind='box', box_target=box.pk, pin_kind='box', pin_target=target.pk,
                               comment=comment, stance=stance, **kwargs)[1]


def rate(user, pin, stance=1, **kwargs):
    """Ocena przypięcia autora: +1 zgadzam się, -1 nie zgadzam się."""
    from spina3.ratings import set_rating
    return set_rating(user, pin, stance, **kwargs)[0]


_seq = {'n': 0}


def rated_box(*stances, title='Box', author=None, raters=None, **box_kwargs):
    """Box z przypięciem autora i ocenami (stances). Zwraca (box, pin)."""
    _seq['n'] += 1
    box, thing = make_box(title, **box_kwargs), make_box(f'Dowód {title}')
    author = author or make_user(f'autor{_seq["n"]}')
    p = author_pin(author, box, thing)
    raters = raters or [make_user(f'r{_seq["n"]}x{i}') for i in range(len(stances))]
    for user, stance in zip(raters, stances):
        rate(user, p, stance)
    return box, p


@pytest.fixture
def user_factory(db):
    return make_user


@pytest.fixture
def box_factory(db):
    return make_box


@pytest.fixture
def api():
    from rest_framework.test import APIClient
    return APIClient()

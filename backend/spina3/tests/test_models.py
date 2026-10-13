"""Ograniczenia w bazie v2: jedno przypięcie na box, jedna ocena na użytkownika i przypięcie, dwa stany oceny, jeden "przydatny"."""
from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from spina3.models import Box, BoxLink, Comment, CommentVote, Pin, Rating

from .conftest import make_box, make_user

pytestmark = pytest.mark.django_db


def test_exactly_one_pin_per_box_removed_frees_slot():
    author, other, a, b, c = make_user('u1'), make_user('u1b'), make_box('A'), make_box('B'), make_box('C')
    first = Pin.objects.create(user=author, box=a, kind='box', pinned_box=b)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pin.objects.create(user=other, box=a, kind='box', pinned_box=c)
    first.status = 'removed'
    first.save()
    Pin.objects.create(user=other, box=a, kind='box', pinned_box=c)


def test_pin_cannot_target_itself():
    user, a = make_user('u2'), make_box('A')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pin.objects.create(user=user, box=a, kind='box', pinned_box=a)


def test_author_stance_optional_and_bounded():
    user, a, b, c = make_user('u3'), make_box('A'), make_box('B'), make_box('C')
    Pin.objects.create(user=user, box=a, kind='box', pinned_box=b, stance=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pin.objects.create(user=user, box=c, kind='box', pinned_box=b, stance=2)


def test_one_rating_per_user_and_pin_two_states_only():
    author, rater, a, b = make_user('u4'), make_user('u5'), make_box('A'), make_box('B')
    pin = Pin.objects.create(user=author, box=a, kind='box', pinned_box=b)
    Rating.objects.create(user=rater, pin=pin, box=a, stance=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Rating.objects.create(user=rater, pin=pin, box=a, stance=-1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Rating.objects.create(user=author, pin=pin, box=a, stance=0)
    # konta usunięte (user=None) nie kolidują
    Rating.objects.create(user=None, pin=pin, box=a, stance=1, anonymized=True)
    Rating.objects.create(user=None, pin=pin, box=a, stance=-1, anonymized=True)


def test_comment_vote_once():
    user, voter, a = make_user('u6c'), make_user('u7c'), make_box('A')
    comment = Comment.objects.create(box=a, user=user, text='Treść')
    CommentVote.objects.create(user=voter, comment=comment)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CommentVote.objects.create(user=voter, comment=comment)


def test_box_kind_needs_target_and_url_needs_url():
    user, a = make_user('u6'), make_box('A')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pin.objects.create(user=user, box=a, kind='box', pinned_box=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pin.objects.create(user=user, box=a, kind='url', url='')


def test_boxlink_one_current_diagnosis_with_history():
    post, d1, d2 = make_box('post', kind='post'), make_box('d1', kind='diagnosis'), make_box('d2', kind='diagnosis')
    BoxLink.objects.create(box=post, target=d1, kind='diagnosis_of', version=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BoxLink.objects.create(box=post, target=d2, kind='diagnosis_of', version=2)
    BoxLink.objects.filter(box=post, kind='diagnosis_of').update(is_current=False)
    BoxLink.objects.create(box=post, target=d2, kind='diagnosis_of', version=2)
    assert BoxLink.objects.filter(box=post, kind='diagnosis_of').count() == 2


def test_box_single_origin_constraint():
    from news.models import Article, Source
    source = Source.objects.create(name='S', url='https://s.example.org')
    article = Article.objects.create(source=source, title='T', url='https://s.example.org/1')
    Box.objects.create(kind='article', title='T', url='https://s.example.org/1', article=article)
    assert Box.objects.filter(article=article).count() == 1

"""Miniatura konta w postach przekazu dnia (v3): tylko https, wariant _bigger, brak zgadywania."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from news.clinic import _post_avatar


class PostAvatarTests(SimpleTestCase):
    def test_bigger_variant_for_https(self):
        post = SimpleNamespace(author_data={'profile_image_url': 'https://pbs.twimg.com/profile_images/1/abc_normal.jpg'})
        self.assertEqual(_post_avatar(post), 'https://pbs.twimg.com/profile_images/1/abc_bigger.jpg')

    def test_empty_when_missing_or_not_https(self):
        self.assertEqual(_post_avatar(SimpleNamespace(author_data=None)), '')
        self.assertEqual(_post_avatar(SimpleNamespace(author_data={})), '')
        self.assertEqual(_post_avatar(SimpleNamespace(author_data={'profile_image_url': 'http://x/a_normal.jpg'})), '')
        self.assertEqual(_post_avatar(SimpleNamespace(author_data={'profile_image_url': 'javascript:alert(1)'})), '')

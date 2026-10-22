"""Kolejka weryfikacji URL: normalizacja, SSRF, blokady, decyzja człowieka, duplikaty."""
from __future__ import annotations

import pytest

from spina3 import url_queue
from spina3.models import Box, Pin, UrlCheck

from .conftest import make_box, make_user

pytestmark = pytest.mark.django_db


def test_normalize_url():
    assert url_queue.normalize_url('HTTP://www.Example.org/a/amp/?utm_source=x&b=2&a=1#frag') == 'https://example.org/a?a=1&b=2'
    assert url_queue.normalize_url('example.org/x/') == 'https://example.org/x'
    assert url_queue.normalize_url('ftp://example.org/x') == ''
    assert url_queue.normalize_url('https://user:pass@example.org/') == ''
    assert url_queue.normalize_url('') == ''


def test_private_hosts_rejected_after_dns():
    assert url_queue.host_is_safe('localhost')[0] is False
    assert url_queue.host_is_safe('127.0.0.1')[0] is False
    assert url_queue.host_is_safe('10.0.0.5')[0] is False
    assert url_queue.host_is_safe('169.254.169.254')[0] is False
    assert url_queue.host_is_safe('intranet.local')[0] is False
    assert url_queue.host_is_safe('example.org', resolver=lambda h: ['192.168.1.1'])[0] is False
    assert url_queue.host_is_safe('example.org', resolver=lambda h: ['93.184.216.34'])[0] is True
    assert url_queue.host_is_safe('nx.example.org', resolver=lambda h: [])[0] is False


def test_automatic_checks_block_doxxing_and_copies():
    assert url_queue.automatic_checks('https://pastebin.com/abc')['verdict'] == 'rejected'
    assert url_queue.automatic_checks('https://example.org/osoba?email=jan@example.org')['verdict'] == 'rejected'
    assert url_queue.automatic_checks('https://example.org/dok/44051401359')['verdict'] == 'rejected'
    assert url_queue.automatic_checks('https://bit.ly/abc')['verdict'] == 'needs_review'
    assert url_queue.automatic_checks('https://instagram.com/jan_kowalski')['verdict'] == 'needs_review'
    assert url_queue.automatic_checks('https://sejm.gov.pl/druk/123')['verdict'] == 'queued'
    assert url_queue.automatic_checks('https://nieznany-blog.example/post')['verdict'] == 'needs_review'


def test_enqueue_and_process_without_network_goes_to_human():
    check = url_queue.enqueue('https://sejm.gov.pl/druk/123', actor='abc')
    assert check.status == 'queued'
    url_queue.process(check)
    check.refresh_from_db()
    assert check.status == 'needs_review' and 'url_fetch_enabled' in check.reason


def test_process_with_fake_fetcher_reads_title_and_canonical_duplicate():
    existing = make_box('Istniejący', url='https://example.org/kanon')
    check = url_queue.enqueue('https://example.org/kopia', actor='abc')

    def fetcher(url):
        return url_queue.FetchResult(status=200, final_url=url, content_type='text/html',
                                     body='<html><head><title>Tytuł strony</title><link rel="canonical" href="https://example.org/kanon"></head></html>')
    url_queue.process(check, fetcher)
    check.refresh_from_db()
    assert check.status == 'duplicate' and check.box_id == existing.pk
    assert check.fetched['title'] == 'Tytuł strony'


def test_fetcher_errors_go_to_review_not_publish():
    check = url_queue.enqueue('https://example.org/zly', actor='abc')
    url_queue.process(check, lambda url: url_queue.FetchResult(error='SSRF: domena wskazuje adres prywatny'))
    check.refresh_from_db()
    assert check.status == 'needs_review' and Box.objects.filter(url=check.url_normalized).count() == 0


def test_decide_accept_creates_reader_link_box_and_attaches_pins():
    staff = make_user('staff', staff=True)
    reader = make_user('reader', days_old=30)
    anchor = make_box('Kotwica')
    check = url_queue.enqueue('https://example.org/nowy-material', actor='r')
    pin = Pin.objects.create(user=reader, box=anchor, kind='url', url=check.url_normalized, url_check=check, stance=1, target_status='pending')
    url_queue.decide(check, staff, 'accept', 'ok', title='Nowy materiał')
    check.refresh_from_db()
    pin.refresh_from_db()
    box = check.box
    assert check.status == 'accepted' and box.reader_link and box.noindex and not box.show_thumbnail and not box.show_quote
    assert pin.target_status == 'ok' and pin.pinned_box_id == box.pk


def test_decide_reject_gives_seven_days():
    staff = make_user('staff2', staff=True)
    reader = make_user('reader2', days_old=30)
    anchor = make_box('Kotwica2')
    check = url_queue.enqueue('https://example.org/odrzucony', actor='r')
    pin = Pin.objects.create(user=reader, box=anchor, kind='url', url=check.url_normalized, url_check=check, stance=1, target_status='pending')
    url_queue.decide(check, staff, 'reject', 'kopia artykułu')
    pin.refresh_from_db()
    assert pin.target_status == 'rejected' and pin.replace_deadline is not None and pin.status == 'published'
    from spina3.pins import expire_unavailable
    from datetime import timedelta
    from django.utils import timezone
    assert expire_unavailable(timezone.now() + timedelta(days=8)) == 1
    pin.refresh_from_db()
    assert pin.status == 'hidden'


def test_requests_fetcher_blocks_private_before_request():
    result = url_queue.requests_fetcher('http://127.0.0.1/admin', resolver=lambda h: ['127.0.0.1'])
    assert result.error.startswith('SSRF')


def test_reject_url_anchor_box_hides_it_with_reason():
    from spina3.pins import create_box_with_pin
    staff, author = make_user('staff3', staff=True), make_user('autor3', days_old=30)
    box, pin, info = create_box_with_pin(author, box_kind='url', box_target='https://example.org/teza-do-odrzucenia', box_title='Teza',
                                         pin_kind='box', pin_target=make_box('Dowód').pk)
    assert box.status == 'pending' and 'czeka' in info['message']
    url_queue.decide(UrlCheck.objects.get(url_normalized=box.url), staff, 'reject', 'Kopia cudzego artykułu.')
    box.refresh_from_db()
    assert box.status == 'hidden' and box.hidden_reason == 'Kopia cudzego artykułu.'

from datetime import datetime, timezone

from news import deleted_posts


class FakeResponse:
    def __init__(self, rows):
        self.rows, self.text = rows, 'x' if rows else ''

    def raise_for_status(self):
        pass

    def json(self):
        return self.rows


def test_find_archive_picks_latest_capture_before_deletion(monkeypatch):
    calls = []

    def fake_get(url, params, **kwargs):
        calls.append(params)
        if params['url'].startswith('x.com'):
            return FakeResponse([['timestamp', 'original'], ['20260920100000', 'https://x.com/Jan/status/123']])
        return FakeResponse([['timestamp', 'original'], ['20260921080000', 'https://twitter.com/Jan/status/123']])

    monkeypatch.setattr(deleted_posts.requests, 'get', fake_get)
    found = deleted_posts.find_archive('https://x.com/Jan/status/123', datetime(2026, 9, 22, tzinfo=timezone.utc))
    assert found == 'https://web.archive.org/web/20260921080000/https://twitter.com/Jan/status/123'
    assert calls[0]['to'] == '20260922000000'


def test_find_archive_empty_and_offline(monkeypatch):
    monkeypatch.setattr(deleted_posts.requests, 'get', lambda *a, **k: FakeResponse([]))
    assert deleted_posts.find_archive('https://x.com/Jan/status/123', None) == ''

    def offline(*a, **k):
        raise deleted_posts.requests.ConnectionError('down')

    monkeypatch.setattr(deleted_posts.requests, 'get', offline)
    assert deleted_posts.find_archive('https://x.com/Jan/status/123', None) is None
    assert deleted_posts.find_archive('https://example.com/a', None) == ''

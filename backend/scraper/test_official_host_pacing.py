from unittest.mock import Mock

from scraper.utils import HostRateLimited


def test_paced_api_fetch_waits_only_for_host_gateway(monkeypatch):
    from scraper.official import fetch_json_paced
    fetch = Mock(side_effect=[HostRateLimited(0.5), {"items": []}])
    waited = Mock()
    monkeypatch.setattr("scraper.official.fetch_json", fetch)
    monkeypatch.setattr("scraper.official.sleep", waited)
    assert fetch_json_paced("/eli/changes/acts", since="2026-09-01", offset=0) == {"items": []}
    waited.assert_called_once_with(0.5)


def test_paced_api_fetch_does_not_retry_other_errors(monkeypatch):
    from scraper.official import fetch_json_paced
    fetch = Mock(side_effect=ValueError("bad response"))
    monkeypatch.setattr("scraper.official.fetch_json", fetch)
    try:
        fetch_json_paced("/eli/changes/acts")
    except ValueError as exc:
        assert str(exc) == "bad response"
    else:
        raise AssertionError("expected the non-host error")
    assert fetch.call_count == 1

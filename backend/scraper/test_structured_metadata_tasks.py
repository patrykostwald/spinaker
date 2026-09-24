from scraper.tasks import preflight_structured_metadata_source


def test_structured_metadata_task_delegates_to_narrow_preflight(monkeypatch):
    monkeypatch.setattr('scraper.structured_metadata.preflight', lambda key: {'source': key, 'contract': 'ok'})
    assert preflight_structured_metadata_source('dane_gov') == {'source': 'dane_gov', 'contract': 'ok'}

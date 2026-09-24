import json
from pathlib import Path
from urllib.parse import urlsplit


BACKLOG = Path(__file__).parent / 'data' / 'source_permission_backlog.json'
ALLOWED_SCOPES = {'metadata_archive', 'search_context', 'rag', 'model_training'}


def test_permission_backlog_is_fail_closed_and_actionable():
    rows = json.loads(BACKLOG.read_text(encoding='utf-8'))
    assert rows
    assert len({row['base_url'] for row in rows}) == len(rows)
    for row in rows:
        assert row['status'] in {'permission_required', 'manual_review'}
        assert row['contacted'] is False
        assert row['requested_scopes']
        assert set(row['requested_scopes']) <= ALLOWED_SCOPES
        assert urlsplit(row['base_url']).scheme == 'https'
        assert all(urlsplit(url).scheme == 'https' for url in row['evidence'])
        assert row['reason'].strip()

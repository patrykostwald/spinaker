import sqlite3
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.models import Article, Source


def _build_legacy_sqlite(path, rows):
    con = sqlite3.connect(str(path))
    con.execute('CREATE TABLE news_source (id INTEGER PRIMARY KEY, url TEXT)')
    con.execute('CREATE TABLE news_article (id INTEGER PRIMARY KEY, source_id INTEGER, '
        'title TEXT, author TEXT, description TEXT, url TEXT, published_date TEXT, '
        'ingestion_method TEXT, category TEXT, image_url TEXT, discovered_at TEXT, created_at TEXT)')
    con.execute("INSERT INTO news_source (id, url) VALUES (1, 'https://known.example')")
    con.execute("INSERT INTO news_source (id, url) VALUES (2, 'https://unknown.example')")
    con.executemany('INSERT INTO news_article (id, source_id, title, author, description, url, '
        'published_date, ingestion_method, category, image_url, discovered_at, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', rows)
    con.commit()
    con.close()


@pytest.mark.django_db
def test_dry_run_reports_without_writing(tmp_path):
    Source.objects.create(name='Known', url='https://known.example')
    sqlite_path = tmp_path / 'legacy.sqlite3'
    _build_legacy_sqlite(sqlite_path, [
        (1, 1, 'Nowy materiał', '', '', 'https://known.example/a', '2026-01-01', 'archive', 'article', '', None, None),
        (2, 2, 'Materiał bez znanego źródła', '', '', 'https://unknown.example/b', '2026-01-01', 'rss', 'article', '', None, None),
    ])
    out = StringIO()
    call_command('plan_legacy_sqlite_import', sqlite_path=str(sqlite_path), stdout=out)
    assert Article.objects.count() == 0
    assert '"new_candidates_total": 1' in out.getvalue()
    assert '"skipped_missing_target_source": 1' in out.getvalue()


@pytest.mark.django_db
def test_apply_refused_against_non_test_database(tmp_path):
    sqlite_path = tmp_path / 'legacy.sqlite3'
    _build_legacy_sqlite(sqlite_path, [])
    with pytest.raises(CommandError):
        call_command('plan_legacy_sqlite_import', sqlite_path=str(sqlite_path), apply=True)


@pytest.mark.django_db
def test_apply_is_idempotent_on_a_test_database(tmp_path):
    # The pytest-django test database is already an isolated, disposable
    # sandbox for this single test (rolled back on teardown), so this test
    # uses --force-non-test-db to exercise the write path directly instead
    # of mutating the live connection's settings_dict, which would corrupt
    # database routing for every test that runs afterwards in this process.
    source = Source.objects.create(name='Known', url='https://known.example')
    sqlite_path = tmp_path / 'legacy.sqlite3'
    _build_legacy_sqlite(sqlite_path, [
        (1, 1, 'Nowy materiał', '', '', 'https://known.example/a', '2026-01-01', 'archive', 'article', '', None, None),
    ])
    out = StringIO()
    call_command('plan_legacy_sqlite_import', sqlite_path=str(sqlite_path),
        apply=True, force_non_test_db=True, stdout=out)
    assert Article.objects.count() == 1
    article = Article.objects.get(url='https://known.example/a')
    assert article.source_id == source.pk
    assert 'legacy id=1' in article.evidence_note

    out2 = StringIO()
    call_command('plan_legacy_sqlite_import', sqlite_path=str(sqlite_path),
        apply=True, force_non_test_db=True, stdout=out2)
    assert Article.objects.count() == 1
    assert '"imported": 0' in out2.getvalue()

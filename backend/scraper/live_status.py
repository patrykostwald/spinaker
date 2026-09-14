"""Small read-only SQLite status probe used by the local VS Code dashboard."""
import json
import sqlite3
import sys


db = sqlite3.connect(sys.argv[1], timeout=2)
db.row_factory = sqlite3.Row
one = lambda sql: db.execute(sql).fetchone()[0]
jobs = {
    row['status']: row['n']
    for row in db.execute('select status, count(*) n from news_archivejob group by status')
}
error_rows = list(db.execute(
    "select lower(coalesce(last_error,'')) error, count(*) n "
    "from news_archivejob where status='error' group by lower(coalesce(last_error,''))"
))
quarantined_rows = list(db.execute(
    "select lower(coalesce(last_error,'')) error, count(*) n "
    "from news_archivejob where status='quarantined' group by lower(coalesce(last_error,''))"
))
manual_markers = ('robots_disallowed', '403', '401', 'forbidden', 'access_denied')
adapter_markers = ('missing_source_title', 'not_a_sitemap', 'unclassified_page',
                   'wordpress_missing_title', 'unsupported')
manual_review = sum(row['n'] for row in error_rows
                    if any(marker in row['error'] for marker in manual_markers))
adapter_review = sum(row['n'] for row in error_rows
                     if any(marker in row['error'] for marker in adapter_markers))
retry_review = sum(row['n'] for row in error_rows) - manual_review - adapter_review
access_statuses = {
    row['status']: row['n']
    for row in db.execute('select status, count(*) n from news_sourceaccessinstruction group by status')
}
recovery_statuses = {
    row['status']: row['n']
    for row in db.execute('select status, count(*) n from news_sourcerecoverycase group by status')
}
print(json.dumps({
    'boxes': one('select count(*) from news_article'),
    'new_10m': one("select count(*) from news_article where scraped_at >= datetime('now','-10 minutes')"),
    'archive_boxes': one("select count(*) from news_article where ingestion_method='archive'"),
    'archive_new_10m': one("select count(*) from news_article where ingestion_method='archive' and scraped_at >= datetime('now','-10 minutes')"),
    'pending': jobs.get('pending', 0),
    'running': jobs.get('running', 0),
    'done': jobs.get('done', 0),
    'errors': jobs.get('error', 0),
    'quarantined': jobs.get('quarantined', 0),
    'errors_retry_or_unclassified': retry_review,
    'errors_adapter_review': adapter_review,
    'errors_permission_review': manual_review,
    'active_sources': one("select count(distinct source_id) from news_archivejob where status='running'"),
    'queued_sources': one(
        "select count(distinct source_id) from news_archivejob where status in ('pending','error','running')"
    ),
    'completed_sources': one(
        "select count(distinct source_id) from news_archivejob where status in ('done','quarantined')"
    ),
    'legal_archive_sources': one("select count(distinct source_id) from news_sourceaccessinstruction where status='approved' and channel='sitemap' and minimum_interval_seconds >= 3 and terms_url <> '' and reviewed_at is not null and reviewed_by <> '' and evidence <> '{}'"),
    'access_instructions_approved': access_statuses.get('approved', 0),
    'access_instructions_draft': access_statuses.get('draft', 0),
    'recovery_open': sum(value for key, value in recovery_statuses.items() if key not in ('closed', 'retired')),
    'recovery_contact_required': recovery_statuses.get('contact_required', 0),
    'quarantine_terminal': sum(row['n'] for row in quarantined_rows
        if row['error'] in ('empty_directory', 'non_article_route', 'not_a_sitemap', 'robots_disallowed')),
    'quarantine_exhausted': sum(row['n'] for row in quarantined_rows
        if row['error'] not in ('empty_directory', 'non_article_route', 'not_a_sitemap', 'robots_disallowed')),
}))

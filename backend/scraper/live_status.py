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
print(json.dumps({
    'boxes': one('select count(*) from news_article'),
    'new_10m': one("select count(*) from news_article where scraped_at >= datetime('now','-10 minutes')"),
    'archive_boxes': one("select count(*) from news_article where ingestion_method='archive'"),
    'archive_new_10m': one("select count(*) from news_article where ingestion_method='archive' and scraped_at >= datetime('now','-10 minutes')"),
    'pending': jobs.get('pending', 0),
    'running': jobs.get('running', 0),
    'done': jobs.get('done', 0),
    'errors': jobs.get('error', 0),
    'active_sources': one("select count(distinct source_id) from news_archivejob where status='running'"),
    'queued_sources': one(
        "select count(distinct source_id) from news_archivejob where status in ('pending','error','running')"
    ),
    'completed_sources': one(
        "select count(distinct source_id) from news_archivejob where status='done'"
    ),
}))

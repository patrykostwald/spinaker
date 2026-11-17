from collections import Counter
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.core.management.base import CommandError

from news import senate_wikipedia as s

TEXT = (Path(__file__).parent / 'fixtures' / 'senat_wiki_2026-10-02.txt').read_text(encoding='utf-8')


def test_snapshot_gives_99_current_senators_with_clubs():
    rows = s.rows_from_wikitext(TEXT, 123)
    print(len(rows), Counter(r.club for r in rows))
    assert len(rows) == 99
    names = {r.full_name for r in rows}
    assert 'Stanisław Pawlak' in names and 'Krzysztof Kukucki' not in names and 'Bogdan Klich' not in names
    assert all(r.term == 11 and r.source_url.endswith('?oldid=123') for r in rows)
    assert Counter(r.club for r in rows)['PiS'] == 31


def test_tables_disagree_fail_closed():
    broken = TEXT.replace('* [[Halina Bieda]]\n', '', 1)
    with pytest.raises(CommandError, match='różnią'):
        s.rows_from_wikitext(broken)


def test_changed_page_format_fails_closed():
    with pytest.raises(CommandError, match='brak sekcji'):
        s.rows_from_wikitext(TEXT.replace('=== Stan aktualny ===', '=== Inny ==='))


def test_fetch_uses_descriptive_user_agent_and_reports_errors_without_details():
    response = Mock(json=Mock(return_value={'parse': {'wikitext': TEXT, 'revid': 5}}))
    get = Mock(return_value=response)
    rows = s.senat_rows(http_get=get)
    assert len(rows) == 99 and 'kontakt@' in get.call_args.kwargs['headers']['User-Agent']
    with pytest.raises(CommandError, match='niedostępna'):
        s.senat_rows(http_get=Mock(side_effect=ValueError('secret')))

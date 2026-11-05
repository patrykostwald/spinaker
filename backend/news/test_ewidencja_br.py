"""Ruch 10: ewidencja B+R / IP Box z historii git (lokalnie, bez sieci)."""
import csv
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
from django.core.management import call_command

from news.management.commands import ewidencja_br as ledger

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def commit(minutes, author='A', ai=False):
    return {'at': T0 + timedelta(minutes=minutes), 'author': author, 'ai': ai}


def test_sessions_lead_in_and_day_cap():
    rows = [commit(0), commit(60), commit(120), commit(600)]  # sesja 2 h + 0,5 h; po 8 h przerwy nowa sesja (minimum 0,5 h)
    ledger.estimate_hours(rows)
    assert round(sum(r['hours'] for r in rows[:3]), 2) == 2.5 and rows[3]['hours'] == 0.5
    long = [commit(i * 60) for i in range(14)]  # 13 h ciągłej pracy -> limit dnia 10 h
    ledger.estimate_hours(long)
    assert round(sum(r['hours'] for r in long), 2) == ledger.DAY_CAP_H


def test_project_and_area_classification():
    assert ledger.project_of('spin.clinic', ['frontend-spin/app/przeszlosc/page.tsx', 'backend/news/przeszlosc.py']) == 'przeszłość.today'
    assert ledger.project_of('spin.clinic', ['backend/news/clinic.py', 'backend/news/przeszlosc.py', 'x.py']) == 'spin.clinic'
    assert ledger.project_of('iapply (aplikacja)', ['a.py']) == 'iapply (aplikacja)'
    assert ledger.area_of('backend/news/clinic.py') == 'backend/news' and ledger.area_of('README.md') == '(główny katalog)'


def test_command_on_temporary_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git = lambda *a, **env: subprocess.run(['git', '-C', str(repo), *a], check=True, capture_output=True,
                                           env={**__import__('os').environ, **env})
    git('init', '-q')
    git('config', 'user.email', 't@example.org')
    git('config', 'user.name', 'Tester')
    for i, name in enumerate(['backend/news/a.py', 'frontend-spin/app/przeszlosc/b.tsx']):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x\n')
        git('add', '.')
        stamp = f'2026-10-0{i + 1}T10:00:00+02:00'
        git('commit', '-q', '-m', f'zmiana {i}', '-m', 'Co-Authored-By: Claude <noreply@anthropic.com>' if i else '',
            GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    out = tmp_path / 'out'
    call_command('ewidencja_br', '--repo', f'spin.clinic={repo}', '--repo', f'brak={tmp_path / "nie-ma"}',
                 '--od', '2026-09-01', '--do', '2026-10-31', '--wyjscie', str(out))
    with open(out / 'rejestr-commity.csv', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    assert [r['projekt'] for r in rows] == ['spin.clinic', 'przeszłość.today'] and [r['wsparcie_AI'] for r in rows] == ['nie', 'tak']
    monthly = (out / 'rejestr-miesieczny.csv').read_text(encoding='utf-8-sig')
    assert '2026-10;spin.clinic;1;1' in monthly and (out / 'koszty-szablon.csv').exists()
    assert 'do potwierdzenia przez księgową' in (out / 'metoda.txt').read_text(encoding='utf-8').lower()

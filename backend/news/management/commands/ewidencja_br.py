"""python manage.py ewidencja_br [--repo nazwa=ścieżka ...] [--od 2026-01-01] [--do 2026-12-31] [--wyjscie katalog]

Ewidencja prac B+R / IP Box (plan finansowy 6.10, ruch 10): czyta historię git wskazanych repozytoriów (tylko lokalnie,
bez sieci) i zapisuje:
- rejestr-commity.csv - każdy commit: data, projekt, obszary kodu, zmienione linie, szacowane godziny, wsparcie AI;
- rejestr-miesieczny.csv - miesiąc x projekt: commity, dni pracy, daty, obszary, szacowane godziny;
- koszty-szablon.csv - miesiące x kategorie kosztów do uzupełnienia z faktur (git nie zna kosztów);
- metoda.txt - jak liczymy godziny.
To materiał roboczy dla księgowej, nie porada podatkowa: kwalifikację prac i kosztów potwierdza księgowa lub doradca.

Metoda godzin (jawna i powtarzalna): commity jednej osoby sortujemy w czasie; przerwa krótsza niż SESSION_GAP_H
łączy je w jedną sesję pracy. Sesja = czas od pierwszego do ostatniego commitu + LEAD_IN_H na pracę przed pierwszym
commitem (najmniej MIN_SESSION_H). Dzień jednej osoby najwyżej DAY_CAP_H. Godziny sesji dzielimy po równo na jej commity.
Commity ze stopką Co-Authored-By modelu AI oznaczamy: godziny to czas nadzoru i decyzji człowieka, nie praca modelu.
"""
import csv
import re
import subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SESSION_GAP_H = 3.0
LEAD_IN_H = 0.5
MIN_SESSION_H = 0.5
DAY_CAP_H = 10.0
DEFAULT_REPOS = [
    ('spin.clinic', r'C:\Users\User\spin-clinic\.local\spinaker-mvp-frontend'),
    ('iapply (aplikacja)', r'C:\Users\User\iapply\app'),
    ('zbudujmi', r'C:\Users\User\zbudujmi'),
]
AI = re.compile(r'claude|codex|gpt|openai|anthropic|gemini|copilot', re.I)
SEP = '\x1f'
COST_CATEGORIES = ['wynagrodzenia i umowy (osoby przy B+R)', 'API modeli AI', 'serwer i hosting', 'dostęp do danych (np. API X)',
                   'narzędzia i licencje', 'usługi zewnętrzne (podwykonawcy)', 'sprzęt']


def project_of(repo_name, paths):
    """Repozytorium spin.clinic zawiera dwa programy: spin.clinic i przeszłość.today (po ścieżkach plików)."""
    if repo_name != 'spin.clinic':
        return repo_name
    hits = sum(bool(re.search(r'przeszlosc|pracownia_osint|public_record|odstepstw', p)) for p in paths)
    return 'przeszłość.today' if paths and hits * 2 >= len(paths) else 'spin.clinic'


def area_of(path):
    parts = path.replace('\\', '/').split('/')
    if len(parts) >= 3 and parts[0] in ('backend', 'packages', 'frontend-spin', 'frontend-przeszlosc', 'app', 'src'):
        return '/'.join(parts[:2])
    return parts[0] if len(parts) > 1 else '(główny katalog)'


def read_git(repo_name, path, since, until):
    if not (Path(path) / '.git').exists():
        return None
    fmt = SEP.join(['@@%H', '%aI', '%an', '%s', '%(trailers:key=Co-Authored-By,valueonly,separator=;)'])
    out = subprocess.run(['git', '-C', path, 'log', '--all', '--no-merges', f'--since={since}', f'--until={until} 23:59:59',
                          f'--pretty=format:{fmt}', '--numstat'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                         check=True).stdout
    commits, seen = [], set()
    for block in out.split('@@')[1:]:
        lines = block.strip('\n').split('\n')
        head = lines[0].split(SEP)
        if len(head) < 5 or head[0] in seen:
            continue
        seen.add(head[0])
        files, added, removed = [], 0, 0
        for line in lines[1:]:
            cols = line.split('\t')
            if len(cols) == 3:
                files.append(cols[2])
                added += int(cols[0]) if cols[0].isdigit() else 0
                removed += int(cols[1]) if cols[1].isdigit() else 0
        commits.append({'repo': repo_name, 'sha': head[0][:10], 'at': datetime.fromisoformat(head[1]), 'author': head[2],
                        'subject': head[3][:140], 'ai': bool(AI.search(head[4] or '')), 'files': files,
                        'added': added, 'removed': removed, 'project': project_of(repo_name, files),
                        'areas': sorted({area_of(f) for f in files})})
    return commits


def estimate_hours(commits):
    """Sesje jednej osoby (po wszystkich repozytoriach razem, żeby nie liczyć tej samej godziny dwa razy)."""
    by_author = defaultdict(list)
    for c in commits:
        by_author[c['author']].append(c)
    for rows in by_author.values():
        rows.sort(key=lambda c: c['at'])
        sessions, current = [], [rows[0]] if rows else []
        for c in rows[1:]:
            if (c['at'] - current[-1]['at']).total_seconds() / 3600 < SESSION_GAP_H:
                current.append(c)
            else:
                sessions.append(current)
                current = [c]
        if current:
            sessions.append(current)
        per_day = defaultdict(float)
        for s in sessions:
            span = (s[-1]['at'] - s[0]['at']).total_seconds() / 3600
            hours = max(MIN_SESSION_H, span + LEAD_IN_H)
            day = s[0]['at'].date()
            hours = max(0.0, min(hours, DAY_CAP_H - per_day[day]))
            per_day[day] += hours
            for c in s:
                c['hours'] = hours / len(s)
    return commits


class Command(BaseCommand):
    help = 'Ewidencja prac B+R / IP Box z historii git (CSV dla księgowej). Lokalnie, bez sieci, bez porad podatkowych.'

    def add_arguments(self, parser):
        parser.add_argument('--repo', action='append', default=[], help='nazwa=ścieżka (można powtarzać)')
        parser.add_argument('--od', default=f'{date.today().year}-01-01')
        parser.add_argument('--do', default=date.today().isoformat())
        parser.add_argument('--wyjscie', default=r'C:\Users\User\Desktop\projekty\iapply-gotowe\ip-box')

    def handle(self, *args, **options):
        repos = [tuple(r.split('=', 1)) for r in options['repo']] or DEFAULT_REPOS
        commits = []
        for name, path in repos:
            try:
                rows = read_git(name, path, options['od'], options['do'])
            except (OSError, subprocess.CalledProcessError) as error:
                raise CommandError(f'{name}: nie udało się odczytać historii git ({type(error).__name__}).') from error
            if rows is None:
                self.stdout.write(f'{name}: {path} nie jest repozytorium git - pomijam.')
                continue
            self.stdout.write(f'{name}: {len(rows)} commitów.')
            commits += rows
        if not commits:
            raise CommandError('Brak commitów w podanym okresie.')
        estimate_hours(commits)
        out = Path(options['wyjscie'])
        out.mkdir(parents=True, exist_ok=True)
        commits.sort(key=lambda c: c['at'])
        self.write(out / 'rejestr-commity.csv', ['data', 'godzina', 'miesiąc', 'projekt', 'repozytorium', 'commit', 'autor', 'opis',
                   'obszary', 'pliki', 'linie_dodane', 'linie_usunięte', 'szacowane_godziny', 'wsparcie_AI'],
                   [[c['at'].date().isoformat(), c['at'].strftime('%H:%M'), c['at'].strftime('%Y-%m'), c['project'], c['repo'], c['sha'],
                     c['author'], c['subject'], '; '.join(c['areas']), len(c['files']), c['added'], c['removed'],
                     f"{c['hours']:.2f}".replace('.', ','), 'tak' if c['ai'] else 'nie'] for c in commits])
        groups = defaultdict(list)
        for c in commits:
            groups[(c['at'].strftime('%Y-%m'), c['project'])].append(c)
        monthly = []
        for (month, project), rows in sorted(groups.items()):
            days = sorted({c['at'].date() for c in rows})
            areas = defaultdict(int)
            for c in rows:
                for a in c['areas']:
                    areas[a] += 1
            monthly.append([month, project, len(rows), len(days), ', '.join(d.strftime('%d') for d in days),
                            '; '.join(f'{a} ({n})' for a, n in sorted(areas.items(), key=lambda x: -x[1])[:6]),
                            f"{sum(c['hours'] for c in rows):.1f}".replace('.', ','),
                            f"{100 * sum(c['ai'] for c in rows) / len(rows):.0f}%"])
        self.write(out / 'rejestr-miesieczny.csv', ['miesiąc', 'projekt', 'commity', 'dni_pracy', 'dni_miesiąca', 'główne_obszary',
                   'szacowane_godziny', 'udział_commitów_z_AI'], monthly)
        months = sorted({m for m, _ in groups})
        self.write(out / 'koszty-szablon.csv', ['miesiąc', 'kategoria', 'kwota_netto_zł', 'nr_faktury', 'projekt', 'udział_B+R_%', 'uwagi'],
                   [[m, cat, '', '', '', '', ''] for m in months for cat in COST_CATEGORIES])
        (out / 'metoda.txt').write_text('Metoda godzin' + __doc__.split('Metoda godzin', 1)[1].rstrip() +
                                        f'\n\nParametry: przerwa {SESSION_GAP_H} h, rozbieg {LEAD_IN_H} h, minimum {MIN_SESSION_H} h, '
                                        f'limit dnia {DAY_CAP_H} h. Okres: {options["od"]} - {options["do"]}. '
                                        f'Wygenerowano: {datetime.now():%Y-%m-%d %H:%M}.\n'
                                        'To szacunek z historii zmian kodu, nie lista obecności. Do potwierdzenia przez księgową.\n',
                                        encoding='utf-8')
        total = sum(c['hours'] for c in commits)
        self.stdout.write(f'Zapisano w {out}: {len(commits)} commitów, {len(monthly)} wierszy miesięcznych, ok. {total:.0f} h.')

    @staticmethod
    def write(path, header, rows):
        with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle, delimiter=';')
            writer.writerow(header)
            writer.writerows(rows)

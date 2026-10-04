"""Analiza gości Kanału Zero (zlecenie właściciela 5.10): wszystkie materiały z oficjalnego API YouTube,
gość / prowadzący / data / tytuł / seria, politycy według obozów i procenty. Tylko metadane, bez pobierania filmów.

Użycie: manage.py kanal_zero [--csv /tmp/kanal_zero.csv] [--bez-shortow]
Koszt: ok. 1 jednostka API na 50 materiałów (playlistItems) + 1 na 50 (videos), liczone we wspólnym limicie."""
import csv
import re
import unicodedata
from collections import Counter

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

CHANNEL = 'UClhEl4bMD8_escGCCTmRAYg'  # Kanał Zero
API = 'https://www.googleapis.com/youtube/v3/'
GOVERNMENT = {'KO', 'PSL-TD', 'Polska2050', 'Lewica'}
OPPOSITION = {'PiS', 'Konfederacja', 'Konfederacja_KP', 'Razem'}
NAME_AT_START = re.compile(r'^\s*([A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż\-]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż\-]+){1,2})\s*[:\-–|]')
HOST = re.compile(r'(?:prowadz\w*|rozmawia|rozmowę prowadzi|host)\s*[:\-]?\s*([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż\-]+){1,2})')
DURATION = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').casefold()) if not unicodedata.combining(c))


def seconds(value):
    m = DURATION.match(value or '')
    return sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0


def series(title):
    """Seria programu: tekst po ostatnim „|” w tytule (np. „Raport Międzynarodowy”)."""
    parts = [p.strip() for p in title.split('|')]
    return parts[-1] if len(parts) > 1 and 2 < len(parts[-1]) < 60 else ''


def get(path, params):
    from news.youtube_collect import spend
    spend(path)
    response = requests.get(API + path, params={**params, 'key': settings.YOUTUBE_API_KEY}, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_all():
    uploads = 'UU' + CHANNEL[2:]
    items, token = [], None
    while True:
        data = get('playlistItems', {'part': 'snippet', 'playlistId': uploads, 'maxResults': 50, **({'pageToken': token} if token else {})})
        items += [i['snippet'] for i in data.get('items', [])]
        token = data.get('nextPageToken')
        if not token:
            break
    rows = []
    for start in range(0, len(items), 50):
        ids = [i['resourceId']['videoId'] for i in items[start:start + 50]]
        data = get('videos', {'part': 'snippet,contentDetails', 'id': ','.join(ids), 'maxResults': 50})
        for v in data.get('items', []):
            s = v['snippet']
            rows.append({'id': v['id'], 'date': s['publishedAt'][:10], 'title': s['title'], 'description': s.get('description', ''),
                         'tags': s.get('tags', []), 'seconds': seconds(v['contentDetails'].get('duration'))})
    return rows


def figures():
    """Osoby z rejestru: znormalizowane pełne imię i nazwisko → (nazwa, partia, obóz)."""
    from news.clinic import party_data
    from news.political_models import PublicFigure
    result = {}
    for f in PublicFigure.objects.filter(archived=False).prefetch_related('public_roles').select_related('parliamentary_roster_entry'):
        name = ' '.join(f.canonical_name.split())
        if len(name.split()) < 2:
            continue
        code = (party_data(f).get('party') or {}).get('code')
        role = fold(f.role_title)
        camp = ('rządzący' if code in GOVERNMENT or (not code and re.search(r'minist|premier|wicepremier', role))
                else 'opozycja' if code in OPPOSITION else 'polityk bez przypisania')
        result[fold(name)] = (name.title() if name.isupper() else name, code or '', camp)
    return result


class Command(BaseCommand):
    help = 'Goście Kanału Zero: politycy według obozów i pozostali, z procentami (oficjalne API YouTube, tylko metadane).'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='/tmp/kanal_zero.csv')
        parser.add_argument('--bez-shortow', action='store_true', help='Pomiń materiały krótsze niż 3 minuty.')

    def handle(self, *args, **opts):
        rows = fetch_all()
        people = figures()
        hosts = Counter()
        for r in rows:
            text = fold(r['title'] + ' ' + r['description'][:1500])
            found = [v for k, v in people.items() if re.search(r'(?<![a-z])' + re.escape(k) + r'(?![a-z])', text)]
            r['politycy'] = found
            m = NAME_AT_START.match(r['title'])
            r['gosc_z_tytulu'] = m.group(1).title() if m and not found else ''
            h = HOST.search(r['description'])
            r['prowadzacy'] = h.group(1) if h else ''
            hosts[r['prowadzacy']] += bool(r['prowadzacy'])
            r['seria'] = series(r['title'])
            r['short'] = r['seconds'] < 180
        if opts['bez_shortow']:
            rows = [r for r in rows if not r['short']]
        total = len(rows)
        with open(opts['csv'], 'w', newline='', encoding='utf-8') as stream:
            w = csv.writer(stream)
            w.writerow(['data', 'tytuł', 'seria', 'prowadzący', 'politycy (partia, obóz)', 'gość spoza rejestru (z tytułu)', 'długość min', 'link'])
            for r in sorted(rows, key=lambda r: r['date']):
                w.writerow([r['date'], r['title'], r['seria'], r['prowadzacy'], '; '.join(f'{n} ({p or "-"}, {c})' for n, p, c in r['politycy']),
                            r['gosc_z_tytulu'], round(r['seconds'] / 60), f"https://youtu.be/{r['id']}"])

        def pct(n):
            return f'{n} ({100 * n / max(1, total):.1f}%)'
        gov = sum(any(c == 'rządzący' for _, _, c in r['politycy']) for r in rows)
        opp = sum(any(c == 'opozycja' for _, _, c in r['politycy']) for r in rows)
        other_pol = sum(bool(r['politycy']) and not any(c in ('rządzący', 'opozycja') for _, _, c in r['politycy']) for r in rows)
        non_pol = sum(not r['politycy'] and bool(r['gosc_z_tytulu']) for r in rows)
        unknown = total - sum(bool(r['politycy']) or bool(r['gosc_z_tytulu']) for r in rows)
        out = self.stdout.write
        out(f"Kanał Zero: {total} materiałów ({rows[-1]['date'] if rows else '-'} - {rows[0]['date'] if rows else '-'}); "
            f"w tym krótkich (<3 min): {sum(r['short'] for r in rows)}")
        out(f'Z politykiem obozu rządzącego:  {pct(gov)}')
        out(f'Z politykiem opozycji:          {pct(opp)}')
        out(f'Z politykiem bez przypisania:   {pct(other_pol)}')
        out(f'Z gościem spoza polityki:       {pct(non_pol)}  (imię i nazwisko z tytułu, do weryfikacji)')
        out(f'Bez rozpoznanego gościa:        {pct(unknown)}  (monologi, formaty autorskie, tytuły bez nazwiska)')
        out('Uwaga: materiał z politykami obu stron liczy się w obu obozach.')
        pol = Counter((n, p, c) for r in rows for n, p, c in r['politycy'])
        out('\nNajczęstsi politycy:')
        for (n, p, c), k in pol.most_common(40):
            out(f'  {k:>3}  {n} ({p or "-"}, {c})')
        out('\nNajczęstsi goście spoza rejestru (z tytułu):')
        for n, k in Counter(r['gosc_z_tytulu'] for r in rows if r['gosc_z_tytulu']).most_common(30):
            out(f'  {k:>3}  {n}')
        out('\nProwadzący (z opisów):')
        for n, k in hosts.most_common(10):
            if n:
                out(f'  {k:>3}  {n}')
        out('\nSerie programów:')
        for n, k in Counter(r['seria'] for r in rows if r['seria']).most_common(20):
            out(f'  {k:>3}  {n}')
        out(f"\nPełna lista: {opts['csv']}")

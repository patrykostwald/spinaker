"""Weryfikacja wdrożenia i rejestr sprostowań przeszłość.today (Śledczy R2: P2-9, P0-8).

wersja: hash commita, czas builda i flagi funkcji (tylko prawda/fałsz, żadnych sekretów ani wartości środowiska).
poprawki: lista sprostowań przyjętych przez zespół (zgłoszenie „[Sprostowanie]” ze statusem „naprawione”).
Ograniczenie: osobnego modelu sprostowań nie ma, więc rejestr korzysta ze zgłoszeń błędów (BugReport) i pokazuje tylko datę,
rekord i nazwę; treści zgłoszenia, kontaktu i użytkownika nie ujawniamy."""
import os
import subprocess
from pathlib import Path

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

COMMIT_ENV = ('GIT_COMMIT', 'GIT_SHA', 'SOURCE_VERSION', 'RAILWAY_GIT_COMMIT_SHA', 'COMMIT_SHA')
BUILT_ENV = ('BUILD_TIME', 'BUILT_AT', 'BUILD_DATE')
_cache = {}


def _git(*args):
    try:
        out = subprocess.run(['git', *args], cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def build_info():
    """(commit, czas builda, źródło). Najpierw zmienne builda, potem repozytorium; brak = pusty tekst, nie zgadujemy."""
    if 'info' not in _cache:
        commit = next((os.environ[k].strip() for k in COMMIT_ENV if os.environ.get(k, '').strip()), '')
        built = next((os.environ[k].strip() for k in BUILT_ENV if os.environ.get(k, '').strip()), '')
        source = 'env' if commit else ''
        if not commit:
            commit = _git('rev-parse', 'HEAD')
            source = 'git' if commit else ''
        if not built and commit:
            built = _git('show', '-s', '--format=%cI', commit)
        _cache['info'] = (commit, built, source)
    return _cache['info']


def flags():
    from news import przeszlosc
    from news.przeszlosc_dostep import FEATURE_GATES, FEATURES, beta, has
    return {'przeszlosc_enabled': przeszlosc.enabled(), 'beta_all_features': beta(),
            'features': {f[0]: {'tier': f[6], 'open': f[0] not in FEATURE_GATES or has(FEATURE_GATES[f[0]])} for f in FEATURES}}


@api_view(['GET'])
@permission_classes([AllowAny])
def wersja_view(request):
    """GET /api/przeszlosc/wersja/ - czy działa wdrożony commit, który oczekujemy. Działa także przy wyłączonym podglądzie."""
    commit, built, source = build_info()
    response = Response({'commit': commit, 'commit_short': commit[:7], 'built_at': built, 'source': source,
                         'flags': flags()})
    response['Cache-Control'] = 'no-store'
    return response


PREFIX = '[Sprostowanie]'
LIMIT = 200


def corrections_list():
    from news.feedback_models import BugReport
    rows = []
    for report in BugReport.objects.filter(status='fixed', text__startswith=PREFIX).order_by('-created_at')[:LIMIT]:
        lines = report.text[len(PREFIX):].strip().split('\n')
        record, label = lines[0].strip()[:80], (lines[1].strip() if len(lines) > 1 else '')[:120]
        kind, _, ident = record.partition(':')
        href = f'/przeszlosc/osoba/{ident}' if kind == 'osoba' and ident else ''
        rows.append({'id': report.pk, 'date': report.created_at.date().isoformat(), 'record': record, 'label': label, 'href': href})
    return rows


@api_view(['GET'])
@permission_classes([AllowAny])
def corrections_view(request):
    """GET /api/przeszlosc/poprawki/ - rejestr przyjętych sprostowań, bez treści i danych zgłaszającego."""
    rows = corrections_list()
    return Response({'count': len(rows), 'results': rows, 'limit': LIMIT,
                     'note': 'Lista obejmuje sprostowania przyjęte i wprowadzone przez zespół. Treści zgłoszeń nie publikujemy.'})

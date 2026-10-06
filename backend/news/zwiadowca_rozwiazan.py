"""Zwiadowca rozwiązań (właściciel 7.10.2026: „mieć podłączone wszystkie najlepsze technologie”).

Po co: badacze (Ekspert AI, Technolog, Mechanik, Pracownia OSINT) przegapili Inception Mercury (100 mln darmowych tokenów),
bo nikt nie miał zadania „znajdź, co obniża koszt albo zdejmuje limit”, i nikt takich ustaleń nie odbierał:
- Ekspert AI czyta tylko znaleziska Pielgrzyma i pyta „które modele warto egzaminować” (jakość, nie koszt);
- Technolog czyta wydania otwartych narzędzi (TECH_FEEDS) z zastrzeżeniem „nic, co wysyła dane na zewnątrz” - API dostawców
  są poza jego zakresem z założenia;
- Rekruter widzi tylko katalogi dostawców, do których mamy klucz (nowy dostawca bez klucza jest niewidzialny);
- Mechanik naprawia tylko istniejące miejsca w Konsylium; Badacz odkrywa kanały RSS, ale nikt nie pyta go o koszty.

Pętla (trzy kroki, każdy z odbiorcą i bezpiecznikiem):
1. Obserwatorzy (codziennie, bez modeli): publiczne katalogi (OpenRouter, Hugging Face), kanały zmian dostawców (RSS),
   wydania otwartych narzędzi z naszych dziedzin (GitHub), nowe zbiory (dane.gov.pl, data.europa.eu). Różnica wobec
   rejestru tego, co już używamy (council_registry, skład Konsylium, Inception, kanały Pracowni i Badacza).
   Nowy darmowy model albo dostawca = SYGNAŁ od razu („bezpiecznik Inception”): do Rekrutera, gdy mamy klucz;
   do właściciela mailem, gdy klucz trzeba założyć (tylko właściciel zakłada konta i klucze).
   Pierwszy przebieg to linia bazowa: zapisuje stan bez sygnałów (żeby nie zalać panelu starymi pozycjami).
2. Zwiad tygodnia (poniedziałek; Inception pierwszy, potem łańcuch darmowych modeli - common.ask_any): ocena pozycji z tygodnia
   według kryteriów (CRITERIA): co konkretnie odblokowuje, legalność, regulamin (trenowanie na danych z API, treści polityczne),
   wysiłek S/M/L, zgodność z twardymi zasadami. Najwyżej 10 ustaleń z dowodami (adresy tylko z danych wejściowych), bez powtórek.
3. Odbiorcy działają sami: modele -> kolejka Rekrutera (egzamin jak dla każdego kandydata; okres cienia wejdzie ze zleceniem Z5);
   darmowe pule i dostawcy -> rejestr pojemności Dyrygenta i lista zamienników Mechanika; narzędzia, dane, funkcje -> Architekt
   (jedyny autor biletów; Zwiadowca nic nie buduje); ryzyko prawne -> Prawnik. Raport pętli: sekcja „Nowe możliwości tygodnia”;
   sygnał bez odbiorcy ponad SLA = bezpiecznik (po próbie naprawy: ponowienie Rekrutera).

Tylko udokumentowane publiczne punkty końcowe i kanały; bez logowania, bez scrapowania za zgodą. GITHUB_TOKEN (opcjonalny)
podnosi limit zapytań GitHub; ZWIADOWCA_FEEDS (JSON nazwa -> adres) dokłada kanały."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import timedelta
from difflib import SequenceMatcher

import requests
from django.utils import timezone

from news import council_registry as registry

logger = logging.getLogger(__name__)

AGENT = 'rozwiazania'
STATE = 'zwiadowca-znane'
UA = {'User-Agent': 'spin.clinic Zwiadowca rozwiazan (+https://spin.clinic)'}
TIMEOUT = (5, 20)
RECENT_DAYS = 7
RECENT_MAX = 400
MAX_FINDINGS = 10
CHEAP_USD_PER_M = 0.10  # „tani”: poniżej 0,10 USD za 1 mln tokenów wejścia
MIN_CONTEXT = 16000
SIMILAR = .85
KINDS = ('model', 'provider', 'tool', 'source', 'feature')
ACTIONS = ('rekruter', 'dyrygent', 'architekt', 'prawnik', 'właściciel')
CHAT_SKIP = re.compile(r'embed|guard|safety|whisper|tts|audio|speech|rerank|ocr|vision|image|moderation|reward|retriev|edit|voice|coder', re.I)

# Kanały zmian dostawców i wydania narzędzi: tylko udokumentowane publiczne kanały RSS/Atom.
PROVIDER_FEEDS = {
    'Cloudflare (dziennik zmian, w tym Workers AI)': 'https://developers.cloudflare.com/changelog/rss/index.xml',
    'Google for Developers (Gemini API, AI Studio)': 'https://developers.googleblog.com/feeds/posts/default?alt=rss',
    'NVIDIA Technical Blog (NIM)': 'https://developer.nvidia.com/blog/feed',
    'Hugging Face (blog)': 'https://huggingface.co/blog/feed.xml',
    'Simon Willison (modele, ceny, narzędzia)': 'https://simonwillison.net/atom/everything/',
}
# Otwarte narzędzia z naszych dziedzin: fact-checking, OSINT, NLP dla polskiego, sankcje i PEP, łączenie podmiotów.
GITHUB_RELEASES = {
    'OpenSanctions yente (dopasowanie podmiotów, sankcje, PEP)': 'opensanctions/yente',
    'FollowTheMoney (format danych OSINT)': 'alephdata/followthemoney',
    'Datashare (ICIJ)': 'ICIJ/datashare',
    'spaCy (NER, także polski)': 'explosion/spaCy',
    'Splink (łączenie rekordów)': 'moj-analytical-services/splink',
    'Dedupe (łączenie podmiotów)': 'dedupeio/dedupe',
    'LiteLLM (wspólny klient wielu dostawców)': 'BerriAI/litellm',
    'vLLM (własne serwowanie modeli)': 'vllm-project/vllm',
    'Ollama (modele lokalne)': 'ollama/ollama',
}
GITHUB_TOPICS = ('fact-checking', 'osint', 'disinformation', 'entity-resolution', 'sanctions', 'polish-nlp')
DATA_QUERIES = ('sejm', 'posłowie', 'partie polityczne', 'zamówienia publiczne', 'dotacje', 'krs', 'oświadczenia majątkowe', 'lobbing',
                'media', 'wybory')
EU_QUERIES = ('Poland parliament', 'Poland public procurement', 'Poland political parties', 'disinformation', 'lobbying transparency')

# Darmowe albo tanie alternatywy znane bez sieci (stan wiedzy 10.2026; liczby do sprawdzenia na stronie dostawcy).
# Pola: usługa, nazwa, zmienna klucza, co daje za darmo, rola u nas (gdy już podłączone).
KNOWN_FREE = (
    ('inception', 'Inception Labs (Mercury 2.5, model dyfuzyjny)', 'INCEPTION_API_KEY', '100 mln darmowych tokenów na start; potem od 0,04 USD/1M', 'zadania poboczne; kandydat Konsylium przez Rekrutera'),
    ('groq', 'Groq', 'GROQ_API_KEY', 'darmowy poziom z dziennym limitem na model', 'Konsylium'),
    ('gemini', 'Google AI Studio (Gemini)', 'GEMINI_API_KEY', 'darmowy poziom z limitami dziennymi; wyszukiwarka do faktów', 'Konsylium (fakty)'),
    ('cloudflare', 'Cloudflare Workers AI', 'CLOUDFLARE_AI_TOKEN', '10 tys. neuronów dziennie za darmo', 'Konsylium'),
    ('nim', 'NVIDIA NIM (build.nvidia.com)', 'NIM_API_KEY', 'darmowe kredyty zapytań dla deweloperów', 'Konsylium'),
    ('mistral', 'Mistral La Plateforme', 'MISTRAL_API_KEY', 'poziom eksperymentalny za darmo (limit zapytań)', 'Konsylium'),
    ('openrouter', 'OpenRouter (modele :free)', 'OPENROUTER_API_KEY', 'modele :free z dziennym limitem zapytań', 'Konsylium (zapas)'),
    ('hf', 'Hugging Face Inference Providers', 'HF_TOKEN', 'miesięczna pula kredytów za darmo; wielu dostawców pod jednym API', 'Konsylium'),
    ('cerebras', 'Cerebras Cloud', 'CEREBRAS_API_KEY', 'darmowy poziom (ok. 1 mln tokenów dziennie), API zgodne z OpenAI', ''),
    ('sambanova', 'SambaNova Cloud', 'SAMBANOVA_API_KEY', 'darmowy poziom deweloperski, API zgodne z OpenAI', ''),
    ('github-models', 'GitHub Models', 'GITHUB_TOKEN', 'darmowy poziom dla kont GitHub (limit zapytań dziennie)', ''),
    ('together', 'Together AI', 'TOGETHER_API_KEY', 'tylko jednorazowe kredyty startowe (bez stałego darmowego poziomu)', ''),
    ('deepinfra', 'DeepInfra', 'DEEPINFRA_API_KEY', 'płatny od początku; tanie modele otwarte (poniżej 0,10 USD/1M)', ''),
)
# Dane i narzędzia z raportu źródeł 6.10 (TAK/WARUNKOWO), których jeszcze nie podłączyliśmy: do planu --plan.
KNOWN_DATA_GAPS = (
    ('GUS BDL (liczby lokalne)', 'https://api.stat.gov.pl/Home/BdlApi', 'CC BY 4.0; sprawdzanie liczb z wypowiedzi', 'M'),
    ('EUR-Lex / CELLAR (czy ustawa wdraża dyrektywę)', 'https://eur-lex.europa.eu/content/help/data-reuse/webservice.html', 'ponowne wykorzystanie dozwolone', 'M'),
    ('SAOS (orzeczenia KIO i TK)', 'https://www.saos.org.pl/help/index.php/dokumentacja-api/api-pobierania-danych', 'bez klucza; bez deanonimizacji', 'S'),
    ('Biała lista VAT (API MF)', 'https://www.gov.pl/web/kas/api-wykazu-podatnikow-vat', 'tylko spółki; trop, nie dowód', 'S'),
    ('EUvsDisinfo (zbieżność narracji)', 'https://euvsdisinfo.eu/disinformation-cases/', 'warunkowo: opisywać jako zbieżność', 'S'),
    ('RCL (projekty rządowe, OSR, uwagi z konsultacji)', 'https://legislacja.rcl.gov.pl/', 'dokumenty urzędowe', 'M'),
    ('SUDOP (pomoc publiczna)', 'https://dane.gov.pl/', 'publiczne API UOKiK', 'M'),
    ('Bluesky Jetstream (wpisy polityków bez kosztu X)', 'https://docs.bsky.app/blog/jetstream', 'warunkowo: tylko konta publiczne', 'S'),
)
CRITERIA = [
    'Oszczędność albo odblokowanie: podaj KONKRETNY limit lub funkcję (np. „zdejmuje dzienny limit 300 zapytań Groq w przesiewaniu X”, '
    '„100 mln darmowych tokenów na zadania poboczne”, „kontekst 128k pozwala ocenić cały wywiad”). Bez ogólników.',
    'Legalność: tylko oficjalne API i publiczne dane; bez obchodzenia logowania, płatnych murów i blokad; dane osób publicznych tylko '
    'w związku z działalnością publiczną (RODO); licencja musi pozwalać na użycie komercyjne (CC BY-NC tylko po wykupieniu licencji).',
    'Regulamin dostawcy: czy dane z API trenują modele (domyślnie włączone = „trenuje domyślnie”: zadania z danymi osób prywatnych tylko '
    'po wyłączeniu); czy regulamin zakazuje treści politycznych albo analizy wypowiedzi polityków (political_content_ok=false).',
    'Wysiłek: S (do pół dnia: klucz + wpis w konfiguracji), M (1-2 dni: nowy moduł), L (3+ dni).',
    'Twarde zasady: bez pieniędzy partii i polityków, ta sama miara dla wszystkich stron, nic budowanego pod jedną partię, RODO. '
    'hard_rules_ok=false, gdy rozwiązanie je narusza.',
    'Działanie (action): rekruter - model do egzaminu Konsylium (mamy klucz do dostawcy); właściciel - nowy dostawca wymaga założenia '
    'konta i klucza; dyrygent - darmowa pula lub limit do rejestru pojemności i zamienników; architekt - narzędzie, zbiór danych albo '
    'funkcja do planu (bilet z dowodem); prawnik - gdy legalność lub regulamin wymaga oceny.',
]
TEXT = {'type': 'string'}
INT = {'type': 'integer'}
FINDING = {'type': 'object', 'properties': {
    'title': TEXT, 'kind': {'type': 'string', 'enum': list(KINDS)}, 'provider': TEXT, 'model': TEXT,
    'unlocks': TEXT, 'saving': TEXT, 'legality': {'type': 'string', 'enum': ['dozwolone', 'warunkowo', 'niedozwolone', 'do sprawdzenia']},
    'tos_training': {'type': 'string', 'enum': ['nie trenuje', 'trenuje domyślnie', 'nieznane']},
    'political_content_ok': {'type': 'boolean'}, 'effort': {'type': 'string', 'enum': ['S', 'M', 'L']},
    'hard_rules_ok': {'type': 'boolean'}, 'score': INT, 'evidence_urls': {'type': 'array', 'items': TEXT},
    'action': {'type': 'string', 'enum': list(ACTIONS)}, 'note': TEXT},
    'required': ['title', 'kind', 'unlocks', 'saving', 'legality', 'tos_training', 'political_content_ok', 'effort', 'hard_rules_ok',
                 'score', 'evidence_urls', 'action']}
SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'findings': {'type': 'array', 'items': FINDING}}, 'required': ['summary', 'findings']}
PROMPT = ('Jesteś Zwiadowcą rozwiązań spin.clinic i przeszłość.today. Cel właściciela: mieć podłączone wszystkie najlepsze darmowe albo '
          'tanie technologie, dane i funkcje. Masz pozycje z tygodnia (items: katalogi modeli, kanały zmian dostawców, wydania narzędzi, '
          'nowe zbiory danych) i to, czego już używamy (we_use). Wybierz do 10 ustaleń, które realnie obniżają koszt, zdejmują limit '
          'albo dodają możliwość, której nie mamy. Oceń każde według rules; score 0-100 (100 = duża oszczędność, legalne, S). '
          'evidence_urls WYŁĄCZNIE z items (url). Pomijaj to, co już używamy, i previous (wcześniejsze ustalenia). Po polsku, konkretnie.')


# --- stan -------------------------------------------------------------------------------------------------------------

def load():
    from news.models import ImportState
    state = ImportState.objects.filter(name=STATE).first()
    return dict(state.cursor or {}) if state else {}


def save(data):
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name=STATE)
    state.cursor = {**data, 'at': timezone.now().isoformat(timespec='minutes')}
    state.save(update_fields=['cursor'])


def _get(url, **kwargs):
    headers = {**UA, **kwargs.pop('headers', {})}
    response = requests.get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True, **kwargs)
    response.raise_for_status()
    return response


def _json(url, **kwargs):
    return _get(url, **kwargs).json()


# --- rejestr: co już używamy (bez sieci) --------------------------------------------------------------------------------

def used_providers():
    """Dostawcy modeli z konfiguracji: nazwa -> zmienna klucza i czy klucz jest ustawiony (nie czytamy .env, tylko środowisko)."""
    return {service: {'key_env': env, 'configured': bool(registry.credentials(service))} for service, env in registry.KEYS.items()}


def used_models():
    from news.clinic_council import DEFAULT_COUNCIL, _members
    members = set(_members('CLINIC_COUNCIL', DEFAULT_COUNCIL))
    try:
        from news.clinic_models import CouncilSeat
        members |= {(s.provider, s.model) for s in CouncilSeat.objects.all()}
    except Exception:  # noqa: BLE001 - brak bazy nie zatrzymuje rejestru
        pass
    try:
        from news import inception
        members.add(inception.member())
    except Exception:  # noqa: BLE001
        pass
    return members


def used_feeds():
    out = {}
    try:
        from news import pracownia_osint
        out.update(pracownia_osint.FEEDS)
        out.update(pracownia_osint.TECH_FEEDS)
    except Exception:  # noqa: BLE001
        pass
    try:
        from news import badacz
        out.update({row.get('name', url): url for url, row in badacz.load().items()})
    except Exception:  # noqa: BLE001
        pass
    return out


def we_use():
    """Krótki opis dla modelu i dla planu: dostawcy (z kluczem / bez), modele Konsylium, liczba kanałów."""
    providers = used_providers()
    return {'providers_with_key': sorted(s for s, p in providers.items() if p['configured']),
            'providers_without_key': sorted(s for s, p in providers.items() if not p['configured']),
            'models': sorted(f'{s}:{m}' for s, m in used_models()), 'feeds': len(used_feeds())}


# --- obserwatorzy (bez modeli) -----------------------------------------------------------------------------------------

def _price(value):
    try:
        return float(value) * 1_000_000  # USD za token -> USD za 1 mln
    except (TypeError, ValueError):
        return None


def watch_openrouter():
    """Publiczny katalog OpenRouter: modele :free i tanie (cena wejścia poniżej CHEAP_USD_PER_M)."""
    items = []
    for row in _json('https://openrouter.ai/api/v1/models').get('data', []):
        name = str(row.get('id') or '')
        if not name or CHAT_SKIP.search(name):
            continue
        pricing = row.get('pricing') or {}
        prompt, completion = _price(pricing.get('prompt')), _price(pricing.get('completion'))
        free = name.endswith(':free') or (prompt == 0 and completion == 0)
        cheap = free or (prompt is not None and prompt < CHEAP_USD_PER_M)
        if not cheap:
            continue
        params = set(row.get('supported_parameters') or [])
        items.append({'kind': 'model', 'id': f'openrouter:{name}', 'provider': 'openrouter', 'model': name, 'title': f'OpenRouter: {name}',
                      'url': f'https://openrouter.ai/{name.split(":")[0]}', 'free': free, 'cheap': cheap,
                      'context': int(row.get('context_length') or 0), 'json': bool(params & {'response_format', 'structured_outputs'}),
                      'summary': f"wejście {prompt if prompt is not None else '?'} USD/1M, wyjście {completion if completion is not None else '?'} USD/1M, "
                                 f"kontekst {row.get('context_length') or '?'}"})
    return items


def watch_huggingface():
    """Router Hugging Face (publiczny): modele i dostawcy wnioskowania; trending modele tekstowe z publicznego API."""
    items, providers = [], {}
    for row in _json('https://router.huggingface.co/v1/models').get('data', []):
        name = str(row.get('id') or '')
        live = [p for p in row.get('providers') or [] if p.get('status', 'live') == 'live']
        if not name or not live or CHAT_SKIP.search(name):
            continue
        for p in live:
            providers.setdefault(str(p.get('provider') or ''), 0)
            providers[str(p.get('provider') or '')] += 1
        items.append({'kind': 'model', 'id': f'hf:{name}', 'provider': 'hf', 'model': f"{name}:{live[0].get('provider')}",
                      'title': f'Hugging Face: {name}', 'url': f'https://huggingface.co/{name}', 'free': False, 'cheap': True,
                      'context': int(live[0].get('context_length') or 0), 'json': True,
                      'summary': 'dostawcy: ' + ', '.join(sorted({str(p.get('provider')) for p in live}))})
    for name, count in providers.items():
        if name:
            items.append({'kind': 'provider', 'id': f'hf-provider:{name}', 'provider': name, 'title': f'Dostawca wnioskowania HF: {name}',
                          'url': f'https://huggingface.co/inference/models?provider={name}', 'free': False, 'cheap': True,
                          'summary': f'{count} modeli przez router Hugging Face (jeden klucz HF_TOKEN)'})
    try:
        trending = _json('https://huggingface.co/api/models', params={'sort': 'trendingScore', 'direction': -1, 'limit': 30,
                                                                      'pipeline_tag': 'text-generation'})
    except (requests.RequestException, ValueError):
        trending = []
    for row in trending if isinstance(trending, list) else []:
        name = str(row.get('id') or row.get('modelId') or '')
        if name:
            items.append({'kind': 'tool', 'id': f'hf-trending:{name}', 'title': f'Model na fali (HF): {name}', 'url': f'https://huggingface.co/{name}',
                          'summary': f"polubienia {row.get('likes', 0)}, pobrania {row.get('downloads', 0)}", 'free': True, 'cheap': True})
    return items


def feeds():
    extra = {}
    try:
        extra = json.loads(os.environ.get('ZWIADOWCA_FEEDS', '') or '{}')
    except ValueError:
        logger.info('zwiadowca: ZWIADOWCA_FEEDS nie jest poprawnym JSON')
    out = {**PROVIDER_FEEDS, **{name: f'https://github.com/{repo}/releases.atom' for name, repo in GITHUB_RELEASES.items()}}
    out.update({str(k): str(v) for k, v in extra.items() if str(v).startswith('https://')})
    return out


def watch_feeds(limit=5):
    """Kanały RSS/Atom dostawców i wydań narzędzi (feedparser)."""
    import feedparser
    items = []
    for name, url in feeds().items():
        try:
            parsed = feedparser.parse(_get(url).content)
        except requests.RequestException:
            continue
        for entry in parsed.entries[:limit]:
            link = str(entry.get('link') or '')
            if not link.startswith('https://'):
                continue
            kind = 'tool' if 'github.com' in link else 'provider'
            items.append({'kind': kind, 'id': f'feed:{link}', 'title': f"{name}: {str(entry.get('title') or '')[:160]}", 'url': link,
                          'summary': re.sub(r'<[^>]+>', ' ', str(entry.get('summary') or ''))[:400], 'free': None, 'cheap': None,
                          'provider': name.split(' (')[0].lower()})
    return items


def github_headers():
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    return {'Accept': 'application/vnd.github+json', **({'Authorization': f'Bearer {token}'} if token else {})}


def watch_github(days=RECENT_DAYS):
    """Publiczne wyszukiwanie repozytoriów GitHub po tematach z naszych dziedzin, zmienione w ostatnich dniach."""
    since = (timezone.localdate() - timedelta(days=days)).isoformat()
    items, seen = [], set()
    for topic in GITHUB_TOPICS:
        try:
            data = _json('https://api.github.com/search/repositories', headers=github_headers(),
                         params={'q': f'topic:{topic} pushed:>{since} stars:>50', 'sort': 'stars', 'order': 'desc', 'per_page': 10})
        except (requests.RequestException, ValueError) as error:
            logger.info('zwiadowca github %s: %s', topic, type(error).__name__)
            continue
        for row in data.get('items', []):
            full = str(row.get('full_name') or '')
            if not full or full in seen:
                continue
            seen.add(full)
            items.append({'kind': 'tool', 'id': f'github:{full}', 'title': f'GitHub: {full}', 'url': str(row.get('html_url') or f'https://github.com/{full}'),
                          'summary': f"{str(row.get('description') or '')[:200]} (gwiazdki {row.get('stargazers_count', 0)}, licencja "
                                     f"{((row.get('license') or {}).get('spdx_id')) or 'brak'}, temat {topic})", 'free': True, 'cheap': True,
                          'license': ((row.get('license') or {}).get('spdx_id')) or ''})
    return items


def watch_dane_gov(days=RECENT_DAYS):
    """Nowe zbiory w katalogu dane.gov.pl (oficjalne API) dla naszych haseł."""
    since = (timezone.localdate() - timedelta(days=days)).isoformat()
    items, seen = [], set()
    for query in DATA_QUERIES:
        try:
            data = _json('https://api.dane.gov.pl/1.4/datasets', params={'q': query, 'per_page': 10, 'sort': '-created'})
        except (requests.RequestException, ValueError):
            continue
        for row in data.get('data', []):
            a = row.get('attributes') or {}
            created = str(a.get('created') or '')[:10]
            if row.get('id') in seen or (created and created < since):
                continue
            seen.add(row.get('id'))
            url = str((row.get('links') or {}).get('self') or '').replace('api.dane.gov.pl/1.4', 'dane.gov.pl/pl')
            items.append({'kind': 'source', 'id': f"dane-gov:{row.get('id')}", 'title': f"dane.gov.pl: {str(a.get('title') or '')[:160]}", 'url': url,
                          'summary': f"licencja {a.get('license_name') or '?'}, utworzono {created}, hasło „{query}”", 'free': True, 'cheap': True,
                          'license': str(a.get('license_name') or '')})
    return items


def watch_eu(days=RECENT_DAYS):
    """Portal data.europa.eu (publiczne API wyszukiwania): nowe zbiory dla naszych zapytań."""
    since = (timezone.localdate() - timedelta(days=days)).isoformat()
    items, seen = [], set()
    for query in EU_QUERIES:
        try:
            data = _json('https://data.europa.eu/api/hub/search/search', params={'q': query, 'limit': 10, 'sort': 'modified+desc', 'filter': 'dataset'})
        except (requests.RequestException, ValueError):
            continue
        for row in ((data.get('result') or {}).get('results') or []):
            ident = str(row.get('id') or '')
            modified = str(row.get('modified') or '')[:10]
            if not ident or ident in seen or (modified and modified < since):
                continue
            seen.add(ident)
            title = row.get('title') or {}
            title = title.get('en') or title.get('pl') or next(iter(title.values()), '') if isinstance(title, dict) else str(title)
            items.append({'kind': 'source', 'id': f'eu:{ident}', 'title': f'data.europa.eu: {str(title)[:160]}', 'url': f'https://data.europa.eu/data/datasets/{ident}',
                          'summary': f"zmieniono {modified}, zapytanie „{query}”", 'free': True, 'cheap': True})
    return items


WATCHERS = (('openrouter', watch_openrouter), ('huggingface', watch_huggingface), ('feeds', watch_feeds), ('github', watch_github),
            ('dane-gov', watch_dane_gov), ('eu-open-data', watch_eu))


# --- sygnały (bezpiecznik Inception) ----------------------------------------------------------------------------------

def _recruiter_knows(provider, model):
    try:
        from news.clinic_models import CouncilRecruitment, CouncilSeat
        return (CouncilSeat.objects.filter(provider=provider, model=model).exists()
                or CouncilRecruitment.objects.filter(provider=provider, model=model).exists())
    except Exception:  # noqa: BLE001
        return False


def signal_for(item):
    """Sygnał natychmiastowy albo None: nowy darmowy model czatu (duży kontekst) albo nowy dostawca.
    Odbiorca: Rekruter (mamy klucz), właściciel (klucz do założenia), Mechanik (nowy dostawca pod routerem HF)."""
    kind = item.get('kind')
    if kind == 'model':
        if not item.get('free') or not item.get('json', True) or int(item.get('context') or 0) < MIN_CONTEXT:
            return None
        if (item['provider'], item['model']) in used_models() or _recruiter_knows(item['provider'], item['model']):
            return None
        configured = used_providers().get(item['provider'], {}).get('configured')
        return {'consumer': 'rekruter' if configured else 'właściciel', 'level': 'info' if configured else 'owner',
                'title': f"Nowy darmowy model: {item['model']} ({item['provider']})",
                'why': 'darmowy model czatu ze schematem JSON i kontekstem ' + str(item.get('context') or '?') + (
                    '; mamy klucz: Rekruter egzaminuje' if configured else f"; brak klucza {registry.KEYS.get(item['provider'], '?')}: tylko właściciel zakłada konta")}
    if kind == 'provider' and item.get('id', '').startswith('hf-provider:'):
        return {'consumer': 'mechanik', 'level': 'info', 'title': f"Nowy dostawca pod routerem Hugging Face: {item['provider']}",
                'why': item.get('summary', '') + '; do listy zamienników Mechanika i rejestru pojemności Dyrygenta'}
    return None


def emit_signal(item, signal, now):
    from news import agents_common as common
    from news.agent_models import AgentNote
    body = '\n'.join([signal['why'], '', f"Źródło: {item.get('url', '')}", item.get('summary', ''),
                      f"Odbiorca: {signal['consumer']}. Sygnał Zwiadowcy rozwiązań (bez modeli AI: sama różnica wobec rejestru)."])
    note = AgentNote.objects.create(agent=AGENT, kind='signal', status='new', title=signal['title'][:240], body=body,
                                    sources=[item['url']] if item.get('url') else [],
                                    scores={'item': {k: v for k, v in item.items() if k != 'summary'}, 'consumer': signal['consumer'],
                                            'level': signal['level'], 'consumed': ''})
    if signal['level'] == 'owner':
        common.notify(note)
    return note


def run_watchers(now=None):
    """Krok dzienny: wszystkie obserwatory, różnica wobec znanych pozycji, sygnały; pierwszy przebieg = linia bazowa."""
    now = now or timezone.now()
    today = timezone.localtime(now).date().isoformat()
    data = load()
    known = dict(data.get('known') or {})
    baseline = not known
    items, errors = [], {}
    for name, watcher in WATCHERS:
        try:
            items += watcher()
        except Exception as error:  # noqa: BLE001 - jeden katalog nie zatrzymuje pozostałych
            errors[name] = type(error).__name__
            logger.info('zwiadowca %s: %s', name, error)
    new = [i for i in items if i['id'] not in known]
    for item in items:
        known.setdefault(item['id'], today)
    signals = []
    if not baseline:
        for item in new:
            signal = signal_for(item)
            if signal:
                signals.append(emit_signal(item, signal, now).pk)
    cutoff = (now - timedelta(days=RECENT_DAYS)).date().isoformat()
    recent = [r for r in (data.get('recent') or []) if r.get('seen', '') >= cutoff and r['id'] not in {i['id'] for i in new}]
    recent += [{**{k: v for k, v in i.items() if k in ('kind', 'id', 'title', 'url', 'summary', 'provider', 'model', 'free', 'cheap', 'context', 'license')},
                'seen': today} for i in new]
    data.update(known=known, recent=recent[-RECENT_MAX:], errors=errors, last_run=now.isoformat(timespec='minutes'),
                counts={'items': len(items), 'new': len(new), 'signals': len(signals)})
    consumed = mark_consumed(now)
    save(data)
    return {'items': len(items), 'new': len(new), 'signals': len(signals), 'baseline': baseline, 'errors': errors, 'consumed': consumed}


# --- zwiad tygodnia (model) ----------------------------------------------------------------------------------------------

def previous_titles(limit=60):
    from news.agent_models import AgentNote
    titles = []
    for note in AgentNote.objects.filter(agent=AGENT, kind='finding')[:8]:
        titles += [f.get('title', '') for f in (note.scores or {}).get('findings', []) if isinstance(f, dict)]
    return titles[:limit]


def _similar(a, b):
    return SequenceMatcher(None, (a or '').lower(), (b or '').lower()).ratio() >= SIMILAR


def _clean(findings, urls, previous):
    out = []
    for f in findings:
        if not isinstance(f, dict) or not str(f.get('title', '')).strip():
            continue
        evidence = [u for u in f.get('evidence_urls', []) if isinstance(u, str) and u in urls]
        if not evidence or f.get('kind') not in KINDS or f.get('action') not in ACTIONS:
            continue
        title = str(f['title'])[:200]
        if any(_similar(title, p) for p in previous) or any(_similar(title, o['title']) for o in out):
            continue
        try:
            score = max(0, min(100, int(f.get('score') or 0)))
        except (TypeError, ValueError):
            score = 0
        if not f.get('hard_rules_ok', True) or f.get('legality') == 'niedozwolone':
            score = 0
        action = f['action']
        if f.get('legality') in ('warunkowo', 'do sprawdzenia') or f.get('tos_training') == 'trenuje domyślnie' or not f.get('political_content_ok', True):
            f['legal_risk'] = True
        if f.get('kind') == 'model' and action == 'rekruter' and not used_providers().get(str(f.get('provider', '')), {}).get('configured'):
            action = 'właściciel'  # bez klucza Rekruter nie zrobi egzaminu
        out.append({**{k: f.get(k) for k in FINDING['properties']}, 'title': title, 'score': score, 'evidence_urls': evidence[:5], 'action': action,
                    'legal_risk': bool(f.get('legal_risk')), 'effort': f.get('effort') if f.get('effort') in ('S', 'M', 'L') else 'M'})
    out.sort(key=lambda f: -f['score'])
    return out[:MAX_FINDINGS]


def scout(force=False, now=None):
    """Zwiad tygodnia: ocena pozycji z 7 dni (Inception pierwszy, potem łańcuch darmowych modeli), do 10 ustaleń z dowodami."""
    from news import agents_common as common
    from news.agent_models import AgentNote
    now = now or timezone.now()
    data = load()
    recent = [r for r in (data.get('recent') or []) if r.get('url')]
    if not recent:
        raise common.WindowClosed('Brak nowych pozycji z obserwatorów w tym tygodniu.')
    recent = sorted(recent, key=lambda r: (r.get('kind') != 'model', not r.get('free'), r.get('seen', '')), reverse=False)[:80]
    previous = previous_titles()
    payload = {'items': recent, 'we_use': we_use(), 'rules': CRITERIA, 'previous': previous[:40]}
    answer, member = common.ask_any(PROMPT, payload, SCHEMA, force)
    findings = _clean(answer.get('findings', []) if isinstance(answer, dict) else [], {r['url'] for r in recent}, previous)
    routed = route(findings, data)
    save(data)
    summary = str(answer.get('summary', '') if isinstance(answer, dict) else '')[:600]
    lines = [summary, ''] + [f"{n}. [{f['kind']}, {f['effort']}, {f['score']}/100 -> {f['action']}] {f['title']}: {f['unlocks']}. "
                             f"Oszczędność: {f['saving']}. Prawo: {f['legality']}; trenowanie: {f['tos_training']}. ({f['evidence_urls'][0]})"
                             for n, f in enumerate(findings, 1)]
    note = AgentNote.objects.create(agent=AGENT, kind='finding', status='new', title=f'Nowe możliwości tygodnia: {len(findings)} ({timezone.localdate():%d.%m.%Y})',
                                    body='\n'.join(lines).strip(), score=max([f['score'] for f in findings], default=0),
                                    sources=sorted({u for f in findings for u in f['evidence_urls']}),
                                    scores={'summary': summary, 'findings': findings, 'routed': routed, 'authors': [':'.join(member)]})
    return note


def route(findings, data):
    """Kierowanie bez budowania: modele -> kolejka Rekrutera; pule i dostawcy -> rejestr pojemności (Dyrygent, Mechanik);
    reszta czeka na Architekta (czyta ostatnie ustalenie) i Prawnika (legal_risk)."""
    queue = {q['model']: q for q in data.get('recruiter_queue') or [] if isinstance(q, dict)}
    capacity = {c['title']: c for c in data.get('capacity') or [] if isinstance(c, dict)}
    routed = {'rekruter': 0, 'dyrygent': 0, 'architekt': 0, 'prawnik': 0, 'właściciel': 0}
    for f in findings:
        if not f['score']:
            continue  # łamie twarde zasady albo niedozwolone: zostaje w ustaleniu (jawnie), bez odbiorcy
        routed[f['action']] = routed.get(f['action'], 0) + 1
        if f['action'] == 'rekruter' and f.get('provider') and f.get('model'):
            queue[f['model']] = {'provider': f['provider'], 'model': f['model'], 'added': timezone.localdate().isoformat(), 'title': f['title']}
        if f['action'] in ('dyrygent', 'właściciel') or f['kind'] == 'provider':
            capacity[f['title']] = {'title': f['title'], 'provider': f.get('provider', ''), 'saving': f['saving'], 'unlocks': f['unlocks'],
                                    'configured': bool(used_providers().get(str(f.get('provider', '')), {}).get('configured')),
                                    'added': timezone.localdate().isoformat(), 'url': f['evidence_urls'][0]}
        if f.get('legal_risk') and f['action'] != 'prawnik':
            routed['prawnik'] += 1  # Prawnik czyta też ustalenia z ryzykiem skierowane gdzie indziej
    data['recruiter_queue'] = list(queue.values())[-40:]
    data['capacity'] = list(capacity.values())[-40:]
    return routed


# --- odbiorcy ------------------------------------------------------------------------------------------------------------

def recruiter_candidates():
    """Dla Rekrutera (council_recruiter.discover): modele wskazane przez Zwiadowcę; egzamin, progi i Karta bez zmian."""
    try:
        rows = load().get('recruiter_queue') or []
    except Exception:  # noqa: BLE001 - brak bazy nie zatrzymuje zwiadu Rekrutera
        return []
    return [{'provider': q['provider'], 'model': q['model'], 'context': 0, 'scout': True} for q in rows if isinstance(q, dict)
            and registry.configured((q['provider'], q['model']))]


def capacity_lines(limit=5):
    """Dla planu dnia Dyrygenta: darmowe pule i dostawcy poza Konsylium (co mamy, czego brakuje)."""
    try:
        rows = load().get('capacity') or []
    except Exception:  # noqa: BLE001
        rows = []
    lines = [f"- {c['title']}: {c['saving']} ({'klucz jest' if c.get('configured') else 'bez klucza'})" for c in rows[-limit:]]
    return (['Wolne moce poza Konsylium (Zwiadowca rozwiązań):'] + lines) if lines else []


def fallbacks(service, model):
    """Dla Mechanika, gdy nie ma następcy w rodzinie: inne darmowe drogi do tego samego modelu bazowego."""
    from news.council_recruiter import base_name
    base = base_name(model)
    try:
        recent = load().get('recent') or []
    except Exception:  # noqa: BLE001
        return []
    return sorted({f"{r.get('provider')}:{r.get('model')}" for r in recent if r.get('kind') == 'model' and r.get('model')
                   and base_name(str(r['model'])) == base and r.get('provider') != service})[:5]


def mark_consumed(now=None):
    """Sygnały i ustalenia uznane za odebrane: Rekruter egzaminował model, klucz dostawcy założony, Architekt napisał plan
    po ustaleniu. Status done z zapisem odbiorcy (nic nie usuwamy)."""
    from news.agent_models import AgentNote
    now = now or timezone.now()
    done = 0
    for note in AgentNote.objects.filter(agent=AGENT, status__in=('new', 'pending')):
        scores = dict(note.scores or {})
        item = scores.get('item') or {}
        who = ''
        if note.kind == 'signal':
            if scores.get('consumer') == 'rekruter' and _recruiter_knows(item.get('provider'), item.get('model')):
                who = 'rekruter'
            elif scores.get('consumer') == 'właściciel' and used_providers().get(item.get('provider'), {}).get('configured'):
                who = 'właściciel (klucz dodany)'
            elif scores.get('consumer') == 'mechanik':
                who = 'mechanik (lista zamienników)'
        elif note.kind == 'finding':
            if AgentNote.objects.filter(agent='architekt', kind='report', created_at__gt=note.created_at).exists():
                who = 'architekt'
        if who:
            scores['consumed'] = who
            AgentNote.objects.filter(pk=note.pk, status__in=('new', 'pending')).update(status='done', scores=scores, decided_at=now)
            done += 1
    return done


def unconsumed_signals(now, hours=None):
    """Sygnały bez odbiorcy dłużej niż SLA (ZWIADOWCA_SIGNAL_SLA_H, domyślnie 72 h)."""
    from news.agent_models import AgentNote
    try:
        hours = hours or max(1, int(os.environ.get('ZWIADOWCA_SIGNAL_SLA_H', '72')))
    except ValueError:
        hours = 72
    return AgentNote.objects.filter(agent=AGENT, kind='signal', status__in=('new', 'pending'), created_at__lt=now - timedelta(hours=hours)), hours


def top(now=None, limit=5):
    """Dla Raportu pętli: najlepsze ustalenia z 7 dni i otwarte sygnały."""
    from news.agent_models import AgentNote
    now = now or timezone.now()
    rows = []
    for note in AgentNote.objects.filter(agent=AGENT, kind='finding', created_at__gte=now - timedelta(days=7))[:3]:
        for f in (note.scores or {}).get('findings', []):
            if isinstance(f, dict):
                rows.append({'title': f.get('title', ''), 'score': f.get('score', 0), 'action': f.get('action', ''), 'saving': f.get('saving', ''),
                             'url': (f.get('evidence_urls') or [''])[0], 'note': note.pk})
    rows.sort(key=lambda r: -int(r['score'] or 0))
    signals = [{'title': n.title, 'consumer': (n.scores or {}).get('consumer', ''), 'id': n.pk}
               for n in AgentNote.objects.filter(agent=AGENT, kind='signal', status__in=('new', 'pending'))[:5]]
    return {'findings': rows[:limit], 'signals': signals}


def report_lines(now=None):
    data = top(now)
    lines = [f"- {r['score']}/100 -> {r['action']}: {r['title']} ({r['saving']}) {r['url']}" for r in data['findings']] or ['Brak nowych ustaleń w tym tygodniu.']
    lines += [f"- SYGNAŁ czeka na: {s['consumer']}: {s['title']}" for s in data['signals']]
    return lines


# --- plan startowy (bez sieci) -------------------------------------------------------------------------------------------

def plan():
    """Co używamy wobec znanych darmowych alternatyw i luk w danych; tylko środowisko (nazwy kluczy) i wiedza wbudowana."""
    providers = used_providers()
    rows = []
    for service, name, env, free, role in KNOWN_FREE:
        known = service in providers
        configured = bool(os.environ.get(env, '').strip()) if not known else providers[service]['configured']
        status = 'podłączone' if known and configured else 'w kodzie, bez klucza' if known else 'nie używamy'
        rows.append({'service': service, 'name': name, 'env': env, 'free': free, 'role': role or '-', 'status': status})
    models = sorted(f'{s}:{m}' for s, m in used_models())
    gaps = [r for r in rows if r['status'] != 'podłączone']
    return {'providers': rows, 'models': models, 'gaps': gaps, 'data_gaps': [{'name': n, 'url': u, 'note': l, 'effort': e} for n, u, l, e in KNOWN_DATA_GAPS],
            'feeds': len(used_feeds())}


def plan_text():
    p = plan()
    lines = ['Zwiadowca rozwiązań - linia bazowa (bez sieci; stan wiedzy 10.2026, liczby do sprawdzenia u dostawcy)', '',
             f"Modele Konsylium i zadań pobocznych: {len(p['models'])}", *[f'  - {m}' for m in p['models']], '',
             f"Kanały, które już czytamy (Pracownia, Badacz): {p['feeds']}", '', 'Dostawcy modeli: co mamy, co znane za darmo:']
    for r in p['providers']:
        lines.append(f"  [{r['status']}] {r['name']} - {r['free']}; klucz: {r['env']}; rola: {r['role']}")
    lines += ['', 'Luka: dostawcy do rozważenia (klucz zakłada właściciel; model wchodzi do Konsylium tylko przez egzamin Rekrutera):']
    lines += [f"  - {r['name']} ({r['env']}): {r['free']}" for r in p['gaps']] or ['  brak']
    lines += ['', 'Luka: dane i narzędzia z raportu źródeł 6.10 (TAK/WARUNKOWO), jeszcze nie podłączone:']
    lines += [f"  - [{d['effort']}] {d['name']}: {d['note']} ({d['url']})" for d in p['data_gaps']]
    lines += ['', 'Co dalej: obserwatorzy codziennie 5:40 (bez modeli), zwiad tygodnia w poniedziałek 4:10; wyniki w Raporcie pętli',
              '(„Nowe możliwości tygodnia”) i w panelu agentów (Zwiadowca rozwiązań). Zmienne: GITHUB_TOKEN (opcjonalnie, wyższy limit GitHub),',
              'ZWIADOWCA_FEEDS (opcjonalnie, JSON nazwa -> adres kanału), ZWIADOWCA_SIGNAL_SLA_H (domyślnie 72).']
    return '\n'.join(lines)

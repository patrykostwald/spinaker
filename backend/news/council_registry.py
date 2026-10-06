"""Konfiguracja dostawców, pochodzenie modeli i lokalne limity zapytań."""
import hashlib
import logging
import math
import os
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
# Optional per-call guard, used only by background proposal agents.
reservation_guard = ContextVar('council_reservation_guard', default=None)
# Treść ma pierwszeństwo (Dyrygent: treść > strażnicy > ...): zapytania diagnozy mogą zużyć cały dzienny limit członka,
# wszystko inne (przesiewanie zaległości X, syntezy, Recenzent, Inkwizytor, agenci) najwyżej część poza rezerwą.
content_purpose = ContextVar('council_content_purpose', default=False)
KEYS = {'groq': 'GROQ_API_KEY', 'nim': 'NIM_API_KEY', 'gemini': 'GEMINI_API_KEY',
        'mistral': 'MISTRAL_API_KEY', 'openrouter': 'OPENROUTER_API_KEY',
        'cloudflare': 'CLOUDFLARE_AI_TOKEN', 'hf': 'HF_TOKEN', 'pllum': 'PLLUM_API_KEY',
        # Inception (Mercury): tylko kandydat Rekrutera, nie stały członek; własny strażnik darmowej puli tokenów (news/inception.py)
        'inception': 'INCEPTION_API_KEY'}
URLS = {'groq': 'https://api.groq.com/openai/v1/chat/completions',
        'nim': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'mistral': 'https://api.mistral.ai/v1/chat/completions',
        'openrouter': 'https://openrouter.ai/api/v1/chat/completions',
        'hf': 'https://router.huggingface.co/v1/chat/completions',
        'inception': 'https://api.inceptionlabs.ai/v1/chat/completions'}
POLISH_MODELS = ('bielik', 'pllum')
CHARTER_SUMMARY = ('\nKarta Konsylium: 1. Bez sympatii politycznych. 2. Badaj słowa, nie ludzi. '
                   '3. Ta sama miara dla obu stron. 4. Nie zgaduj intencji. '
                   '5. Każde twierdzenie ma status (potwierdzone, sprzeczne, mylące, niezweryfikowane); ocena faktu wymaga źródła. 6. Wierne cytaty. '
                   '7. Ujawniaj zakres i braki analizy. 8. Pokazuj różnice zdań. '
                   '9. Automatyczna publikacja; człowiek tylko wycofuje diagnozę. '
                   '10. Prawo do zgłoszenia błędu i odpowiedzi; operator może tylko ukryć diagnozę. 11. Jawne modele, wersje, role i narzędzia. '
                   '12. Bez pieniędzy partii i polityków; wsparcie nie wpływa na ocenę.')


def credentials(service):
    return os.environ.get(KEYS.get(service, ''), '').strip()


def configured(member):
    service, model = member
    ok = bool(credentials(service))
    if service == 'cloudflare':
        ok = ok and bool(os.environ.get('CLOUDFLARE_ACCOUNT_ID', '').strip())
    if service == 'pllum':
        ok = ok and os.environ.get('PLLUM_API_URL', '').strip().startswith('https://')
    if service == 'openrouter':
        ok = ok and model.endswith(':free')
    if not ok:
        logger.debug('council provider %s skipped: missing configuration', service)
    return bool(ok)


def is_polish(member):
    return any(name in member[1].lower() for name in POLISH_MODELS)


def metadata(member):
    service, model = member
    lower = model.lower()
    company = next((company for token, company in (
        ('bielik', 'SpeakLeash / Cyfronet'), ('pllum', 'Konsorcjum PLLuM'),
        # Nowe darmowe modele w katalogu OpenRouter (3.10.2026); bez nazwy firmy Rekruter je pomijał.
        ('thinkingmachines/', 'Thinking Machines Lab'), ('inclusionai/', 'Inclusion AI (Ant Group)'), ('poolside/', 'Poolside'),
        ('liquid/', 'Liquid AI'), ('dots-studio/', 'rednote hi lab'), ('mercury', 'Inception Labs'),
        ('gpt', 'OpenAI'), ('qwen', 'Alibaba'), ('nemotron', 'NVIDIA'),
        ('gemini', 'Google'), ('mistral', 'Mistral AI'), ('llama', 'Meta'),
        ('deepseek', 'DeepSeek'), ('kimi', 'Moonshot AI'), ('gemma', 'Google'), ('glm', 'Zhipu AI'), ('phi-', 'Microsoft'),
        ('command', 'Cohere'), ('granite', 'IBM'), ('olmo', 'Ai2'), ('hermes', 'Nous Research'), ('minimax', 'MiniMax'),
        ('ernie', 'Baidu'), ('grok', 'xAI'), ('jamba', 'AI21'), ('magistral', 'Mistral AI'), ('ministral', 'Mistral AI')) if token in lower), 'unknown')
    return {'model': model, 'company': company, 'provider': service, 'role': 'członek'}


def limit_key(member):
    digest = hashlib.sha256(':'.join(member).encode()).hexdigest()[:20]
    return f'council:daily:{timezone.now().date()}:{digest}'


# Domyślne limity dzienne (zapytania na model) — poniżej darmowych pul dostawców, ale z zapasem na 16 diagnoz dziennie
# z ponowieniami, role przewodniczącego/językoznawcy/recenzenta, Rekrutera i inkwizytora. 50 wyczerpywało się do południa.
DEFAULT_DAILY_LIMITS = {'groq': 300, 'nim': 200, 'hf': 150, 'cloudflare': 200, 'gemini': 150, 'mistral': 200, 'openrouter': 50,
                        'inception': 1000}  # Inception: limit zapytań tylko dla porządku - rządzi pula tokenów (news/inception.py)


def daily_limit(member):
    default = DEFAULT_DAILY_LIMITS.get(member[0], 50)
    # Wyższa z wartości: stary wpis „50” w .env.production nie może obniżyć limitu poniżej domyślnego.
    try:
        return max(default, int(os.environ.get(f'CLINIC_{member[0].upper()}_DAILY_LIMIT', '') or 0))
    except ValueError:
        return default


def available(member):
    return configured(member) and cache.get(limit_key(member), 0) < daily_limit(member)


def content_reserve_share():
    """Część dziennego limitu każdego członka zarezerwowana dla diagnoz (COUNCIL_CONTENT_RESERVE, domyślnie 35%)."""
    try:
        return min(0.9, max(0.0, float(os.environ.get('COUNCIL_CONTENT_RESERVE', '') or 0.35)))
    except ValueError:
        return 0.35


def side_limit(member):
    """Pułap dla zadań pobocznych: dzienny limit bez rezerwy na diagnozy."""
    return max(1, daily_limit(member) - math.ceil(daily_limit(member) * content_reserve_share()))


@contextmanager
def for_content():
    """Zapytania w tym bloku to treść serwisu (diagnoza) - mogą sięgnąć do rezerwy."""
    token = content_purpose.set(True)
    try:
        yield
    finally:
        content_purpose.reset(token)


def content_reserved(member):
    """True, gdy członek ma jeszcze limit, ale tylko w rezerwie na diagnozy albo poza pułapem zadania (musi poczekać)."""
    return not content_purpose.get() and cache.get(limit_key(member), 0) < daily_limit(member)


def reserve(member):
    key = limit_key(member)
    cache.add(key, 0, timeout=86400)
    used = cache.incr(key)
    guard = reservation_guard.get()
    if guard is not None and not guard(member, used):
        cache.decr(key)
        return False
    # Zadania z własnym pułapem (agenci: agents_common.ceiling, 60%) decydują sami; bez pułapu - rezerwa na treść.
    if guard is None and not content_purpose.get() and used > side_limit(member):
        cache.decr(key)  # odmowa nie zużywa limitu
        return False
    granted = used <= daily_limit(member)
    if granted:
        from news.petle_koszty import count_call
        count_call()  # Koszty pętli (7.10): zapytanie na konto zadania, które właśnie biegnie
    return granted


def reserve_side(member):
    """Zapytanie spoza Konsylium (np. strażnik przesiewający wpisy X) do modelu, który zasiada w Konsylium:
    liczone w tym samym limicie i tylko do pułapu poza rezerwą. Model spoza składu - bez ograniczeń."""
    from news.council_quorum import roster
    try:
        if tuple(member) not in roster():
            return True
    except Exception:  # noqa: BLE001 - brak bazy nie może zatrzymać przesiewania
        return True
    try:
        share = min(1.0, max(0.0, float(os.environ.get('COUNCIL_SIDE_SHARE', '') or 0.25)))
    except ValueError:
        share = 0.25
    # Masowe zadania (przesiewanie zaległości) odpuszczają członka wcześnie: zużycie liczymy w zapytaniach,
    # a dostawca liczy tokeny - zapas musi zostać dla diagnoz.
    if not content_purpose.get() and cache.get(limit_key(member), 0) >= math.floor(daily_limit(member) * share):
        return False
    return reserve(member)


def endpoint(service):
    if service == 'cloudflare':
        return f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID'].strip()}/ai/v1/chat/completions"
    if service == 'pllum':
        return os.environ['PLLUM_API_URL'].strip()
    if service == 'nim':
        return os.environ.get('CLINIC_NIM_URL', '').strip() or URLS[service]
    return URLS[service]


def select_members(candidates, target=4):
    """Polski model najpierw, następnie różne firmy; OpenRouter dopiero jako zapas."""
    candidates = list(dict.fromkeys(m for m in candidates if available(m)))
    candidates.sort(key=lambda m: (m[0] == 'openrouter', not is_polish(m)))
    selected, companies = [], set()
    for member in candidates:
        company = metadata(member)['company']
        if company not in companies:
            selected.append(member)
            companies.add(company)
        if len(selected) >= target:
            return selected
    return (selected + [m for m in candidates if m not in selected])[:target]


def diversity(members):
    companies = {metadata(m)['company'] for m in members} - {'unknown'}
    return {'members': len(members), 'companies': len(companies),
            'polish': any(is_polish(m) for m in members),
            'sufficient': len(members) >= 4 and len(companies) >= 3}

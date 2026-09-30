"""Konfiguracja dostawców, pochodzenie modeli i lokalne limity zapytań."""
import hashlib
import logging
import os

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
KEYS = {'groq': 'GROQ_API_KEY', 'nim': 'NIM_API_KEY', 'gemini': 'GEMINI_API_KEY',
        'mistral': 'MISTRAL_API_KEY', 'openrouter': 'OPENROUTER_API_KEY',
        'cloudflare': 'CLOUDFLARE_AI_TOKEN', 'hf': 'HF_TOKEN', 'pllum': 'PLLUM_API_KEY'}
URLS = {'groq': 'https://api.groq.com/openai/v1/chat/completions',
        'nim': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'mistral': 'https://api.mistral.ai/v1/chat/completions',
        'openrouter': 'https://openrouter.ai/api/v1/chat/completions',
        'hf': 'https://router.huggingface.co/v1/chat/completions'}
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
        ('gpt', 'OpenAI'), ('qwen', 'Alibaba'), ('nemotron', 'NVIDIA'),
        ('gemini', 'Google'), ('mistral', 'Mistral AI'), ('llama', 'Meta'),
        ('deepseek', 'DeepSeek'), ('kimi', 'Moonshot AI'), ('gemma', 'Google'), ('glm', 'Zhipu AI'), ('phi-', 'Microsoft'),
        ('command', 'Cohere'), ('granite', 'IBM'), ('olmo', 'Ai2'), ('hermes', 'Nous Research'), ('minimax', 'MiniMax'),
        ('ernie', 'Baidu'), ('grok', 'xAI'), ('jamba', 'AI21'), ('magistral', 'Mistral AI'), ('ministral', 'Mistral AI')) if token in lower), 'unknown')
    return {'model': model, 'company': company, 'provider': service, 'role': 'członek'}


def limit_key(member):
    digest = hashlib.sha256(':'.join(member).encode()).hexdigest()[:20]
    return f'council:daily:{timezone.now().date()}:{digest}'


def daily_limit(member):
    return max(0, int(os.environ.get(f'CLINIC_{member[0].upper()}_DAILY_LIMIT', '50')))


def available(member):
    return configured(member) and cache.get(limit_key(member), 0) < daily_limit(member)


def reserve(member):
    key = limit_key(member)
    cache.add(key, 0, timeout=86400)
    return cache.incr(key) <= daily_limit(member)


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

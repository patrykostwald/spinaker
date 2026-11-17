"""Jedno ograniczone wywołanie Gemini, z trwałą rezerwacją całego kosztu."""
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_UP

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from news.models import RepairerState

MODEL = 'gemini-2.5-flash'
MAX_OUTPUT = 2500
# Rezerwa wyższa niż taryfa Flash: 1 USD wejście i 5 USD wyjście / milion tokenów.
INPUT_USD = Decimal('1')
OUTPUT_USD = Decimal('5')


def reserve(tokens):
    from news.clinic_ai import ClinicAIError
    from news.daily_schedule import bounds
    try:
        limit = Decimal(str(settings.DAILY_MESSAGE_PAID_FALLBACK_USD))
        if not limit.is_finite() or limit < 0:
            limit = Decimal(0)
    except (InvalidOperation, ValueError):
        limit = Decimal(0)
    cost = ((Decimal(tokens) * INPUT_USD + MAX_OUTPUT * OUTPUT_USD) / 1_000_000).quantize(Decimal('.000001'), rounding=ROUND_UP)
    with transaction.atomic():
        row, _ = RepairerState.objects.get_or_create(key=f'message-paid:{bounds(timezone.now())[0].date()}')
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        spent = Decimal(row.data.get('reserved_usd', '0'))
        if spent + cost > limit:
            raise ClinicAIError('daily_message_paid_budget')
        row.data = {'reserved_usd': str(spent + cost), 'calls': row.data.get('calls', 0) + 1}
        row.save(update_fields=['data'])
    return cost


def generate(system, prompt, schema):
    from news.clinic_ai import ClinicAIError, gemini_daily_budget, gemini_spent_today, record_gemini_spend
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise ClinicAIError('gemini_missing_key')
    if gemini_daily_budget() > 0 and gemini_spent_today() >= gemini_daily_budget():
        raise ClinicAIError('gemini_daily_budget')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}'
    headers = {'x-goog-api-key': key}
    contents = [{'role': 'user', 'parts': [{'text': system + '\n' + prompt + '\nJSON: ' + json.dumps(schema, ensure_ascii=False)}]}]
    try:
        # countTokens nie generuje treści i nie uruchamia płatnej analizy.
        count = requests.post(url + ':countTokens', headers=headers, json={'contents': contents}, timeout=(5, 20))
        if count.status_code != 200:
            raise ClinicAIError('gemini_token_count')
        tokens = count.json()['totalTokens']
        if type(tokens) is not int or not 0 < tokens <= 16000:
            raise ClinicAIError('gemini_token_count')
        cost = reserve(tokens)
        # Bez automatycznej ponownej próby. Przy błędzie rezerwa pozostaje zajęta.
        response = requests.post(url + ':generateContent', headers=headers, timeout=(5, 90), json={
            'contents': contents, 'generationConfig': {'temperature': 0, 'maxOutputTokens': MAX_OUTPUT,
                'thinkingConfig': {'thinkingBudget': 0}, 'responseMimeType': 'application/json'}})
        if response.status_code != 200:
            raise ClinicAIError(f'gemini_{response.status_code}')
        payload = response.json()
        record_gemini_spend('message', payload)
        candidate = payload['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ClinicAIError('gemini_incomplete_message')
        data = json.loads(''.join(part.get('text', '') for part in candidate['content']['parts'] if not part.get('thought')))
        return data, {'model': MODEL, 'reserved_usd': str(cost), 'paid_fallback': True}
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
        raise ClinicAIError('gemini_message_failed')

"""Tanie kontrole dostępności co sześć godzin; odpowiedzi nie zapisujemy."""
import os
import shutil
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from news.models import DutyAlarm, RepairerState
from news.repairer import stamp


def probe(provider):
    if provider == 'x-read':
        key = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
        if not key:
            return 'warning', 'Brak klucza zbierania X.'
        url = 'https://api.x.com/2/usage/tweets'
        headers = {'Authorization': 'Bearer ' + key}
    elif provider == 'x':
        from news.x_publish import KEYS, _oauth_header
        if not all(os.environ.get(k, '').strip() for k in KEYS):
            return 'warning', 'Brak pełnych kluczy publikacji X.'
        url = 'https://api.x.com/2/users/me'
        headers = {'Authorization': _oauth_header('GET', url)}
    else:
        key = os.environ.get({'gemini': 'GEMINI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY', 'groq': 'GROQ_API_KEY'}[provider], '').strip()
        if not key:
            return 'warning', 'Brak klucza dostawcy.'
        url, headers = {
            'gemini': ('https://generativelanguage.googleapis.com/v1beta/models', {'x-goog-api-key': key}),
            'anthropic': ('https://api.anthropic.com/v1/models', {'x-api-key': key, 'anthropic-version': '2023-06-01'}),
            'groq': ('https://api.groq.com/openai/v1/models', {'Authorization': 'Bearer ' + key}),
        }[provider]
    try:
        response = requests.get(url, headers=headers, timeout=(4, 10), allow_redirects=False)
        return ('ok', 'Klucz odpowiada.') if response.status_code == 200 else ('warning', f'Dostawca odpowiedział HTTP {response.status_code}.')
    except requests.RequestException:
        return 'warning', 'Brak odpowiedzi dostawcy.'


def run(now=None):
    from news.daily_schedule import pulse, WARSAW
    now = now or timezone.now()
    local = now.astimezone(WARSAW)
    slot = f'{local.date()}:{local.hour // 6}'
    with transaction.atomic():
        row, _ = RepairerState.objects.get_or_create(key='schedule-health')
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        if row.data.get('slot') == slot:
            return {'status': 'already_run'}
        row.data = {**row.data, 'slot': slot, 'attempted_at': now.isoformat()}
        row.save(update_fields=['data'])
    checks = {provider: probe(provider) for provider in ('x', 'x-read', 'gemini', 'anthropic', 'groq')}
    try:
        disk = shutil.disk_usage(settings.BASE_DIR)
        percent = disk.free * 100 / disk.total
        checks['disk'] = ('ok' if percent > 10 else 'warning', f'Wolny dysk: {percent:.1f}%.')
    except OSError:
        checks['disk'] = ('warning', 'Nie można odczytać wolnego miejsca.')
    # Kilka niezależnych zadań; puls samej kontroli nie dowodzi działania beat.
    events = [stamp(pulse(name).get('last_event')) for name in ('duty-15m', 'clinic-screen-5m', 'political-x-minute')]
    fresh = sum(bool(event and timedelta(0) <= now - event <= timedelta(minutes=30)) for event in events)
    checks['beat'] = ('ok' if fresh >= 2 else 'warning', f'Aktualne pulsy zadań: {fresh}/3. To pośrednia kontrola beat.')
    for key, (status, detail) in checks.items():
        if status == 'ok':
            DutyAlarm.objects.filter(key='health:' + key, status='open').update(status='closed', closed_at=now)
        else:
            DutyAlarm.objects.update_or_create(key='health:' + key, defaults={
                'rule': 'schedule-health', 'severity': 'warning', 'title': 'Kontrola dostępności: ' + key,
                'details': {'detail': detail}, 'instruction': 'Sprawdź konfigurację i stan usługi.',
                'status': 'open', 'closed_at': None, 'last_seen': now})
    RepairerState.objects.filter(pk=row.pk).update(data={'slot': slot, 'attempted_at': now.isoformat(), 'checked_at': now.isoformat(),
        'checks': {key: {'status': status, 'detail': detail} for key, (status, detail) in checks.items()}})
    return {'status': 'ok', 'errors': sum(status != 'ok' for status, _ in checks.values())}


def snapshot():
    row = RepairerState.objects.filter(key='schedule-health').first()
    return row.data if row else {'checks': {}}

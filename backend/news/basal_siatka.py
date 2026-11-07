"""Siatka BASAL za Strażnikiem, na razie w trybie cichym (właściciel 21.10).

BASAL (github.com/rkinas/basal, Apache-2.0) zwraca decyzję „puść / do rady” z prawdopodobieństwem. Tryb cichy:
zdanie BASAL trafia tylko do triage['basal'], status wpisu ustala nadal Strażnik. Gdy BASAL_URL jest pusty,
moduł nic nie robi. Test 21.10 na 546 sprawach: wpisy odrzucone przez Strażnika z p >= 0,9 to ok. 4%,
w tym przeoczenia (np. wpisy z mową nienawiści ocenione przez Strażnika na 20/100).
"""
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

QUESTION = {
    'type': 'choice',
    'instructions': 'Wpis polityka w mediach społecznościowych. Czy wymaga oceny rady modeli pod kątem technik '
                    'perswazji i manipulacji?',
    'criteria': {'pusc': 'Neutralny, informacyjny albo grzecznościowy wpis bez technik perswazji',
                 'rada': 'Zawiera możliwe techniki perswazji lub manipulacji, potrzebna ocena rady'},
}


def base_url() -> str:
    return os.environ.get('BASAL_URL', '').strip().rstrip('/')


def escalate_threshold() -> float:
    return float(os.environ.get('BASAL_ESCALATE_THRESHOLD', '0.9'))


def opinion(text: str) -> dict | None:
    """Zdanie BASAL o jednym wpisie albo None (wyłączony, błąd, przekroczony czas). Nigdy nie podnosi wyjątku."""
    url = base_url()
    if not url or not (text or '').strip():
        return None
    started = time.monotonic()
    try:
        response = requests.post(f'{url}/v1/systemone', timeout=float(os.environ.get('BASAL_TIMEOUT', '10')),
                                 json={'state': text, 'questions': {'decyzja': QUESTION}})
        response.raise_for_status()
        data = response.json()
        answer = data['answers']['decyzja']
        p = float(answer['probabilities']['rada'])
    except Exception as error:  # siatka jest dodatkiem: jej awaria nie może zatrzymać Strażnika
        log.warning('BASAL niedostępny: %s', type(error).__name__)
        return None
    return {'p_rada': round(p, 4), 'confidence': round(float(answer.get('confidence', 0)), 4),
            'would_escalate': p >= escalate_threshold(), 'model': str(data.get('model', ''))[:64],
            'latency_ms': int((time.monotonic() - started) * 1000), 'mode': 'shadow'}


def shadow_summary(days: int = 7) -> dict:
    """Ile wpisów odrzuconych przez Strażnika BASAL wysłałby do rady (do raportu i decyzji o włączeniu)."""
    from datetime import timedelta
    from django.utils import timezone
    from news.clinic_models import SpinDiagnosis
    rows = SpinDiagnosis.objects.filter(created_at__gte=timezone.now() - timedelta(days=days),
                                        triage__basal__isnull=False).select_related('post__account')
    rejected = [row for row in rows if row.status == 'not_applicable']
    escalated = [row for row in rejected if row.triage['basal'].get('would_escalate')]
    return {'days': days, 'with_basal': rows.count(), 'rejected': len(rejected), 'would_escalate': len(escalated),
            'examples': [{'id': row.pk, 'account': row.post.account.handle, 'guard': row.screen_score,
                          'p_rada': row.triage['basal']['p_rada'], 'text': row.post.text[:200]}
                         for row in sorted(escalated, key=lambda r: -r.triage['basal']['p_rada'])[:20]]}

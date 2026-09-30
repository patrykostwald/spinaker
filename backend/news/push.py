"""Opt-in Web Push. Never log endpoints, keys or message contents."""
import json
import logging
from django.conf import settings
from news.push_models import PushSubscription

logger = logging.getLogger(__name__)
TOPICS = ('spin-dnia', 'nitki-dr-spina', 'obserwowani')
CONSENT_VERSION = '2026-09-30'


def enabled():
    return bool(settings.PUSH_ENABLED and settings.VAPID_PUBLIC_KEY
                and settings.VAPID_PRIVATE_KEY and settings.VAPID_SUBJECT)


def _send(rows, payload):
    if not enabled():
        return 0
    from pywebpush import webpush, WebPushException
    sent = 0
    for row in rows.iterator():
        try:
            webpush(subscription_info={'endpoint': row.endpoint, 'keys': row.keys},
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={'sub': settings.VAPID_SUBJECT}, ttl=3600, timeout=10)
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, 'status_code', None)
            if status in (404, 410):
                row.delete()
            else:
                logger.warning('Push delivery failed (status=%s)', status)
        except Exception:
            logger.warning('Push delivery failed')
    return sent


def send_to_topic(topic, payload):
    if topic not in TOPICS or not enabled():
        return 0
    # JSON containment is not supported by SQLite used in tests.
    ids = [r.pk for r in PushSubscription.objects.only('pk', 'topics').iterator() if topic in r.topics]
    return _send(PushSubscription.objects.filter(pk__in=ids), payload)


def send_to_user(user, payload):
    if not enabled() or not getattr(user, 'pk', None):
        return 0
    rows = PushSubscription.objects.filter(user=user)
    ids = [r.pk for r in rows.only('pk', 'topics') if 'obserwowani' in r.topics]
    return _send(rows.filter(pk__in=ids), payload)

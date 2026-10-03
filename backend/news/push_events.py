"""Push hooks isolated from account and thread implementation."""
import datetime
import logging
from celery import shared_task
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from news.models import Thread
from news.push import enabled, send_to_staff, send_to_topic
from news.clinic_models import SpinDiagnosis
from news.push_models import PushEvent


@shared_task(name='news.push_events.deliver_event')
def deliver_event(key, topic, payload):
    if not enabled():
        return 0
    _, created = PushEvent.objects.get_or_create(key=key)
    if not created:
        return 0
    return send_to_topic(topic, payload)


@shared_task(name='news.push_events.deliver_staff_event')
def deliver_staff_event(key, payload):
    if not enabled():
        return 0
    _, created = PushEvent.objects.get_or_create(key=key)
    if not created:
        return 0
    return send_to_staff(payload)


QUIET_FROM, QUIET_TO = 23, 7  # nocą nie budzimy czytelników — alert przychodzi o 7:00


def _morning_eta(now=None):
    now = timezone.localtime(now)
    if QUIET_TO <= now.hour < QUIET_FROM:
        return None
    day = now.date() if now.hour < QUIET_TO else now.date() + datetime.timedelta(days=1)
    return timezone.make_aware(datetime.datetime(day.year, day.month, day.day, QUIET_TO, 0))


def _enqueue(key, topic, payload, eta=None):
    try:
        if eta:
            deliver_event.apply_async((key, topic, payload), eta=eta)
        else:
            deliver_event.delay(key, topic, payload)
    except Exception:
        logging.getLogger(__name__).warning('Push queue unavailable')


@receiver(post_save, sender=Thread)
def dr_spin_published(sender, instance, raw=False, **kwargs):
    if raw or not enabled() or not instance.published or instance.created_by_id is not None:
        return
    if not instance.slug.startswith('dr-spin-kontekst-'):
        return
    key = f'dr-spin:{instance.pk}'
    payload = {'title': 'Nowy trop Dr. Spina', 'body': instance.title,
               'url': f'/thread/{instance.slug}', 'tag': key}
    transaction.on_commit(lambda: _enqueue(key, 'nitki-dr-spina', payload))


@shared_task(name='news.push_events.evening_spin')
def evening_spin():
    if not enabled():
        return 0
    from news.clinic import spin_of_day_by_camp
    daily = spin_of_day_by_camp()
    if not any(daily.get('spins', {}).values()):
        return 0
    day = timezone.localdate().isoformat()
    return deliver_event(f'spin-dnia:{day}', 'spin-dnia', {
        'title': 'Spin dnia', 'body': 'Zobacz diagnozy Dr. Spina. Ta sama miara dla obu stron.',
        'url': '/klinika', 'tag': f'spin-dnia:{day}'})


@receiver(post_save, sender=SpinDiagnosis)
def spin_diagnosis_changed(sender, instance, raw=False, **kwargs):
    """Alert na żywo: zatwierdzona diagnoza ze spinem → push do subskrybentów „spiny-na-zywo”.
    Diagnoza czekająca na decyzję → push do zespołu, żeby zatwierdzenie nie opóźniało alertu."""
    if raw or not enabled():
        return
    author = instance.post.account.display_name or f'@{instance.post.account.handle}'
    if instance.status == 'pending_review' and instance.verdict in ('spin', 'partial'):
        key = f'review:{instance.pk}'
        payload = {'title': 'Diagnoza czeka na decyzję', 'body': f'{author}: {instance.headline}'[:180],
                   'url': f'/admin/news/spindiagnosis/{instance.pk}/change/', 'tag': key}
        transaction.on_commit(lambda: _enqueue_staff(key, payload))
        return
    if (instance.status != 'approved' or instance.hidden_at or not instance.reviewed_at
            or instance.verdict not in ('spin', 'partial')):
        return
    key = f'spin:{instance.pk}'
    label = 'Spin' if instance.verdict == 'spin' else 'Częściowy spin'
    payload = {'title': f'{label}: {author}', 'body': (instance.headline or instance.summary)[:180],
               'url': f'/klinika/{instance.pk}', 'tag': key}
    eta = _morning_eta()
    transaction.on_commit(lambda: _enqueue(key, 'spiny-na-zywo', payload, eta))


def _enqueue_staff(key, payload):
    try:
        deliver_staff_event.delay(key, payload)
    except Exception:
        logging.getLogger(__name__).warning('Push queue unavailable')

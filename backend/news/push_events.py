"""Push hooks isolated from account and thread implementation."""
import logging
from celery import shared_task
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from news.models import Thread
from news.push import enabled, send_to_topic
from news.push_models import PushEvent


@shared_task(name='news.push_events.deliver_event')
def deliver_event(key, topic, payload):
    if not enabled():
        return 0
    _, created = PushEvent.objects.get_or_create(key=key)
    if not created:
        return 0
    return send_to_topic(topic, payload)


def _enqueue(key, topic, payload):
    try:
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
    payload = {'title': 'Nowa nitka Dr. Spina', 'body': instance.title,
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

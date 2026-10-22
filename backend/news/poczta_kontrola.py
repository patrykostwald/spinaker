"""Kontrola Dyżurnego dla Poczty: skrzynka z kompletem zmiennych, której IMAP nie odpowiada ponad 2 godziny.
Najpierw naprawa (jedno ponowienie zadania poczta_task na 2 h, właściciel 6.10: „naprawy są częścią alertów”),
alarm krytyczny dopiero, gdy po ponowieniu błąd trwa. Tylko baza i cache; nazwy zmiennych, nigdy wartości."""
from datetime import timedelta

from django.core.cache import cache

GRACE = timedelta(hours=2)
REPAIR_KEY = 'poczta:repair:'


def retrigger(name):
    try:
        from news.tasks import poczta_task
        poczta_task.apply_async(countdown=5)
        return True
    except Exception:  # noqa: BLE001 - brak brokera nie zatrzymuje Dyżurnego
        return False


def check_poczta(ctx):
    from news import poczta
    from news.duty import alarm
    from news.poczta_models import MailboxState
    if not poczta.enabled():
        return []
    alarms = []
    for name in poczta.names():
        cfg = poczta.config(name)
        if not poczta.imap_ready(cfg):
            continue  # wyłączona (brak zmiennych): pokazuje ją `poczta --stan`, nie alarm
        state = MailboxState.objects.filter(mailbox=name).first()
        if not state or not state.last_error_at or (state.last_ok_at and state.last_ok_at >= state.last_error_at):
            cache.delete(REPAIR_KEY + name)
            continue
        since = state.last_ok_at or state.last_error_at
        if ctx.now - since < GRACE:
            continue
        if cache.add(REPAIR_KEY + name, 1, timeout=int(GRACE.total_seconds())):
            retrigger(name)  # naprawa: ponowienie zadania; alarm dopiero przy następnej kontroli po 2 h, gdy błąd trwa
            continue
        hours = round((ctx.now - since).total_seconds() / 3600, 1)
        alarms.append(alarm(f'poczta:{name}', 'critical', f'Poczta {cfg["label"]}: IMAP nie działa ponad {hours:g} h',
                            {'mailbox': name, 'error': state.last_error, 'hours': hours, 'consecutive_errors': state.consecutive_errors,
                             'repair': 'ponowiono zadanie poczta_task, błąd trwa'}, since,
                            f'Sprawdź hasło i host skrzynki (zmienne {poczta.env_name(name, "IMAP_HOST")}, {poczta.env_name(name, "IMAP_USER")}, '
                            f'{poczta.env_name(name, "IMAP_PASSWORD")}) i uruchom: python manage.py poczta --stan', 'poczta-10m'))
    return alarms

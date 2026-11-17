from celery.schedules import crontab


beat_schedule = {
    "teraz-zbierz-nalezne-zrodla": {
        "task": "teraz.tasks.zbierz_nalezne_zrodla",
        "schedule": crontab(minute="*"),
        "options": {"expires": 120},
    },
    "teraz-usun-stare-zrzuty": {
        "task": "teraz.tasks.usun_stare_zrzuty",
        "schedule": crontab(hour=4, minute=20),
        "options": {"expires": 3600},
    },
}

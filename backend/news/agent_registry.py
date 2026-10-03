"""Reviewed agent identities. Scheduling and telemetry come from Celery and cache."""
from copy import copy
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

from news.repairer import flag, stamp
from news.task_heartbeat import cadence

WARSAW = ZoneInfo('Europe/Warsaw')


def agent(name, description, task, env='', default=False, collector=False, cost=''):
    return dict(name=name, description=description, task=task, flag=env,
                default=default, collector=collector, cost=cost)


REGISTRY = {
    'schedule-health': agent('Kontrola dostępności', 'Sprawdza klucze, wolny dysk i pulsy zadań co 6 godzin.', 'news.tasks.schedule_health_task', default=True),
    'video-stats': agent('Koszt filmów', 'Sprawdza dzienny koszt opracowania filmów.', 'news.tasks.clinic_video_stats_task', default=True),
    'social-assistant': agent('Asystent social media', 'Odpowiada na pytania osoby od publikacji. Tylko darmowe modele, domyślnie do 30 prób dziennie.', 'news.social_assistant.answer_question', default=True),
    'plain-editor': agent('Redaktor prostoty', 'Pisze krótki pierwszy ekran po korekcie języka diagnozy.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-meter': agent('Miernik', 'Bez AI sprawdza długość, powtórzenia i proste słowa.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-guard': agent('Strażnik rzetelności', 'Bez AI sprawdza cytaty, techniki i słownik zarzutów.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-reader': agent('Czytelnik testowy', 'Co tydzień czyta do 20 losowych prostych diagnoz i zapisuje raporty w panelu.', 'news.tasks.plain_reader_task', 'PLAIN_READER_ENABLED'),
    'dr-spin': agent('Dr. Spin', 'Diagnozuje wpisy polityków z pomocą Konsylium.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED', cost='diagnoses'),
    'council': agent('Konsylium', 'Uzupełnia deklaracje Karty członków Konsylium.', 'news.tasks.council_charter_missing_task'),
    'screen': agent('Strażnik wpisów', 'Wybiera wpisy warte diagnozy.', 'news.tasks.clinic_screen_task', 'CLINIC_AI_ENABLED'),
    'warden': agent('Strażnik kont', 'Sprawdza tożsamość i aktywność obserwowanych kont.', 'news.tasks.account_warden_task', cost='warden'),
    'repairer': agent('Naprawiacz', 'Analizuje błędy i proponuje działania właścicielowi. Nie zmienia produkcji.', 'news.tasks.repairer_task', 'REPAIRER_ENABLED', True),
    'auditor': agent('Audytor', 'Sprawdza kondycję i wyniki Konsylium.', 'news.tasks.council_audit_task'),
    'inquisitor': agent('Inkwizytor', 'Niezależnie kontroluje jakość diagnoz.', 'news.tasks.inquisitor_task'),
    'recruiter': agent('Rekruter', 'Sprawdza kandydatów do Konsylium.', 'news.tasks.council_recruiter_task'),
    'strateg': agent('Strateg', 'Proponuje rozwój serwisu w wolnym oknie modeli.', 'news.tasks.agents_window_task', 'AGENTS_ENABLED'),
    'pilgrim': agent('Pielgrzym', 'Szuka usprawnień Konsylium na zmianę ze Strategiem.', 'news.tasks.agents_window_task', 'AGENTS_ENABLED'),
    'reports': agent('Raporty Stratega i Pielgrzyma', 'Podsumowuje propozycje tygodnia lub miesiąca.', 'news.tasks.agents_report_task', 'AGENTS_ENABLED'),
    'duty': agent('Dyżurny', 'Wykrywa anomalie wyników i zleca bezpieczne naprawy.', 'news.tasks.duty_task', 'DUTY_ENABLED', True),
    'krs': agent('Agent KRS', 'Sprawdza powiązania osób z podmiotami KRS.', 'news.tasks.krs_agent_task', 'KRS_AGENT_ENABLED', cost='krs'),
    'seba': agent('Seba', 'Krytycznie ocenia propozycje agentów.', 'news.tasks.seba_task', 'SEBA_ENABLED'),
    'second-key': agent('Drugi klucz', 'Weryfikuje podejrzenia Strażnika kont.', 'news.tasks.warden_second_key_task', 'WARDEN_SECOND_KEY_ENABLED'),
    'interviews': agent('Wywiad dnia', 'Przygotowuje transkrypcję i diagnozę wywiadu.', 'news.tasks.clinic_interview_task', 'CLINIC_INTERVIEW_ENABLED', cost='interviews'),
    'interview-pick': agent('Wybór wywiadu', 'Wybiera materiał do wywiadu dnia.', 'news.tasks.clinic_interview_pick_task', 'CLINIC_INTERVIEW_ENABLED'),
    'spin-thread': agent('Wątek Dr. Spina', 'Przygotowuje kontekst spinu dnia.', 'news.tasks.dr_spin_thread_task', 'DR_SPIN_THREADS_ENABLED'),
    'messages': agent('Przekaz dnia', 'Porównuje przekaz obu obozów politycznych.', 'news.tasks.clinic_daily_messages_task', 'CLINIC_AI_ENABLED'),
    'weekly': agent('Raport tygodnia', 'Przygotowuje tygodniowe podsumowanie.', 'news.tasks.weekly_report_task'),
    'x-publish': agent('Publikacja X', 'Publikuje zatwierdzone wątki w granicach limitów.', 'news.tasks.x_publish_task', 'X_POST_ENABLED'),
    'social': agent('Publikacja społecznościowa', 'Przygotowuje publikacje w kanałach społecznościowych.', 'news.tasks.social_publish_task', 'SOCIAL_POST_ENABLED'),
    'notifications': agent('Powiadomienia', 'Obsługuje zdarzenia powiadomień czytelników.', 'news.notification_tasks.process_notification_events'),
    'digests': agent('Podsumowania czytelników', 'Wysyła zamówione podsumowania powiadomień.', 'news.notification_tasks.send_notification_digests'),
    'push': agent('Wieczorny spin', 'Przygotowuje wieczorne powiadomienie.', 'news.push_events.evening_spin'),
}

# Explicit allowlist: a new beat task cannot silently become a collector.
for task, name, env in (
    ('import_official_task', 'Zbieracz Sejmu i ELI', ''),
    ('discover_archives', 'Odkrywca archiwów', ''),
    ('check_data_quality', 'Kontrola jakości źródeł', ''),
    ('enrich_data_quality', 'Uzupełnianie metadanych', ''),
    ('archive_batch', 'Zbieracz archiwów', ''),
    ('discover_kprm_html', 'Zbieracz KPRM', ''),
    ('discover_mswia_metadata', 'Zbieracz MSWiA', ''),
    ('discover_ministry_finance_metadata', 'Zbieracz Ministerstwa Finansów', ''),
    ('discover_named_gov_metadata', 'Zbieracz instytucji publicznych', ''),
    ('audit_source_access', 'Kontrola dostępu do źródeł', ''),
    ('backfill_voting_history', 'Zbieracz historii głosowań', ''),
    ('scrape_rss_sources_task', 'Zbieracz RSS', ''),
    ('preflight_structured_metadata_source', 'Kontrola źródeł danych publicznych', ''),
    ('import_bzp_metadata', 'Zbieracz BZP', 'BZP_API_ENABLED'),
    ('scrape_newsapi_batch_task', 'Zbieracz NewsAPI', ''),
    ('sync_source_mailbox', 'Skrzynka źródeł', 'SOURCE_MAIL_IMAP_ENABLED'),
    ('gdelt_daily_topics', 'Zbieracz GDELT', 'GDELT_ENABLED'),
    ('discover_senat_metadata', 'Zbieracz Senatu', 'SENAT_METADATA_ENABLED'),
):
    REGISTRY[task] = agent(name, 'Zbiera lub sprawdza źródła zgodnie z zatwierdzonym dostępem.',
                           'scraper.tasks.' + task, env, collector=True)
for task, name, env in (
    ('youtube_official_task', 'Zbieracz YouTube', ''),
    ('youtube_leftover_task', 'Zbieracz pozostałego limitu YouTube', ''),
    ('source_social_task', 'Zbieracz kanałów źródeł', ''),
    ('deleted_posts_task', 'Kontrola usuniętych wpisów', ''),
    ('sejm_career_task', 'Zbieracz karier poselskich', ''),
    ('political_poll_task', 'Zbieracz X', 'X_POLITICAL_POLL_ENABLED'),
    ('sync_live_public_rosters_task', 'Zbieracz składów instytucji', ''),
):
    REGISTRY[task] = agent(name, 'Aktualizuje dane z publicznych źródeł w granicach limitów.',
                           'news.tasks.' + task, env, collector=True)


def enabled(spec):
    return not spec['flag'] or flag(spec['flag'], spec['default'])


def task_enabled(task):
    specs = [s for s in REGISTRY.values() if s['task'] == task]
    return any(enabled(s) for s in specs) if specs else True


def schedule_label(schedule):
    if hasattr(schedule, 'run_every'):
        return f'co {schedule.run_every.total_seconds() / 60:g} min'
    minute, hour = schedule._orig_minute, schedule._orig_hour
    if str(hour) == '*' and str(minute).startswith('*/'):
        return f'co {str(minute)[2:]} min'
    if str(hour) == '*' and str(minute) == '*':
        return 'co 1 min'
    if str(hour) == '*':
        return f'co godzinę, minuta: {minute}'
    if len(schedule.hour) == len(schedule.minute) == 1:
        at = f'{min(schedule.hour)}:{min(schedule.minute):02d}'
        if str(schedule._orig_day_of_month) != '*':
            return f'co miesiąc, dzień: {schedule._orig_day_of_month}, godz. {at}'
        if str(schedule._orig_day_of_week) != '*':
            days = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota']
            return f'co tydzień: {", ".join(days[d] for d in sorted(schedule.day_of_week))}, {at}'
        return f'codziennie {at}'
    return f'codziennie, godziny: {hour}, minuty: {minute}'


def next_run(schedule, now):
    schedule = copy(schedule)
    local = now.astimezone(WARSAW)
    schedule.nowfun = lambda: local
    return now + schedule.remaining_estimate(local)


def snapshot(now=None):
    from config.celery import app
    from news.duty import daily_costs
    now = now or timezone.now()
    costs = daily_costs(now)
    entries = app.conf.beat_schedule
    pulses = cache.get_many(['heartbeat:' + key for key in entries])
    rows = []
    for identity, spec in REGISTRY.items():
        matching = [(key, entry) for key, entry in entries.items() if entry['task'] == spec['task']]
        for key, entry in matching or [(None, None)]:
            pulse = pulses.get('heartbeat:' + key, {}) if key else {}
            last = stamp(pulse.get('started_at'))
            interval = cadence(entry['schedule']) if entry else None
            active = enabled(spec)
            stale = bool(last and interval and (now - last).total_seconds() > 3 * interval)
            state = ('error' if pulse.get('result') == 'error' else 'warn'
                     if stale or not pulse or pulse.get('result') == 'skipped' else 'ok')
            due = next_run(entry['schedule'], now) if entry and active else None
            if spec['task'] == 'news.tasks.agents_window_task':
                from news.models import RepairerState
                backoff = RepairerState.objects.filter(key='agents-window').first()
                retry_at = stamp((backoff.data if backoff else {}).get('next_attempt'))
                if due and retry_at and retry_at > due:
                    due = next_run(entry['schedule'], retry_at - timedelta(microseconds=1))
            rows.append(dict(id=f'{identity}:{key or "soon"}', name=spec['name'], description=spec['description'],
                collector=spec['collector'], task=spec['task'], beat=key, flag=spec['flag'], enabled=active,
                schedule=schedule_label(entry['schedule']) if entry else 'wkrótce',
                last_run=last, result=state, summary=pulse.get('summary', 'Brak pulsu.'), next_run=due,
                cost_today_usd=costs.get(spec['cost']), cost_note='Szacunek z zapisanych danych.' if spec['cost'] else '',
                source=', '.join(str(a) for a in entry.get('args', [])) if entry else ''))
    return rows

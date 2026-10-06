"""Celery tasks owned by the editorial-news domain."""
from io import StringIO

from celery import shared_task
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState


@shared_task(name='news.tasks.institutional_reports_task', soft_time_limit=540, time_limit=600)
def institutional_reports_task():
    from news.raportysta import run
    return run()


@shared_task(name='news.tasks.warden_second_key_task', soft_time_limit=600, time_limit=660)
def warden_second_key_task():
    from news.warden_second_key import run
    return run()


@shared_task(name='news.tasks.seba_task', soft_time_limit=840, time_limit=900)
def seba_task():
    from news.seba import run
    return run()


@shared_task(soft_time_limit=840, time_limit=900)
def agents_window_task():
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news.agents_common import window_step
    return window_step()


@shared_task
def agents_report_task(agent):
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    if agent not in ('strateg', 'pielgrzym'):
        raise ValueError('Unknown agent')
    from news.agents_common import report
    return report(agent)


@shared_task
def ekspert_ai_task():
    """Stan wiedzy o AI raz w tygodniu (zadanie codzienne, krok sam pomija, gdy raport ma mniej niż 6 dni)."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import ekspert_ai
    from news.agents_common import WindowClosed
    try:
        note = ekspert_ai.step()
    except WindowClosed as error:
        return {'status': 'closed', 'reason': str(error)}
    return {'status': 'ok', 'note': note.pk, 'state': note.status}


@shared_task(name='news.tasks.repairer_task', soft_time_limit=210, time_limit=240)
def repairer_task():
    from news.repairer import run
    return run()


@shared_task(name='news.tasks.duty_task', soft_time_limit=120, time_limit=150)
def duty_task():
    from news.duty import run
    return run()


@shared_task(name='news.tasks.schedule_rescue_task', soft_time_limit=1900, time_limit=2000)
def schedule_rescue_task(key, stored_key, token):
    from news.rescuer import execute
    return execute(key, stored_key, token)


@shared_task(name='news.tasks.schedule_health_task', soft_time_limit=100, time_limit=120)
def schedule_health_task():
    from news.schedule_health import run
    return run()


@shared_task(bind=True, name='news.tasks.clinic_archive_task', max_retries=60, rate_limit='6/m',
             soft_time_limit=25, time_limit=30)
def clinic_archive_task(self, post_id, job_id=''):
    """Osobna kolejka; wspólna blokada zachowuje odstęp także przy wielu workerach."""
    import re
    import requests
    from news.clinic_lab import archive_request
    from news.political_models import PoliticalPost
    post = PoliticalPost.objects.filter(pk=post_id).first()
    if post is None or post.archive_url:
        return {'status': 'pominięto'}
    if not cache.add('clinic-archive:spacing', 1, timeout=11):
        raise self.retry(countdown=11)
    try:
        result = archive_request(post.url, job_id)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        raise self.retry(countdown=60)
    if not isinstance(result, dict):
        return {'status': 'brak odpowiedzi'}
    if result.get('status') == 'success' and re.fullmatch(r'\d{14}', str(result.get('timestamp', ''))):
        url = f"https://web.archive.org/web/{result['timestamp']}/{post.url}"
        if len(url) > 500:
            return {'status': 'url_too_long'}
        PoliticalPost.objects.filter(pk=post.pk, archive_url='').update(archive_url=url, archive_checked_at=timezone.now())
        return {'status': 'ok', 'archive_url': url}
    next_job = result.get('job_id') or job_id
    if next_job and result.get('status') not in ('error', 'pominięto'):
        raise self.retry(args=[post_id, next_job], countdown=15)
    return {'status': result.get('status', 'brak odpowiedzi')}


@shared_task(name="news.tasks.clinic_diagnose_task", soft_time_limit=1500, time_limit=1600)
def clinic_diagnose_task():
    """Diagnozy nowych postów polityków (Klinika spinu). Wyłączone bez CLINIC_AI_ENABLED i klucza."""
    from news.council_health import record_run
    if not cache.add("clinic-diagnose-lock", "1", timeout=1700):
        record_run({'status': 'locked'})
        return {"status": "locked"}
    try:
        from news.clinic import fill_x_threads, run_diagnoses
        result = run_diagnoses(limit=2)
        record_run(result)
        # Syntezy do wątków na X dla starszych diagnoz (darmowy model, po kilka na raz).
        result['x_threads'] = fill_x_threads(limit=3)
        return result
    except Exception:
        record_run({'status': 'error'})
        raise
    finally:
        cache.delete("clinic-diagnose-lock")


@shared_task(name="news.tasks.clinic_screen_task", soft_time_limit=600, time_limit=660)
def clinic_screen_task(include_old=False, post_ids=None):
    """Strażnik Kliniki: darmowa ocena nowych postów (Groq, zapasowo NVIDIA NIM)."""
    if not cache.add("clinic-screen-lock", "1", timeout=700):
        return {"status": "locked"}
    try:
        from news.clinic import run_screening
        result = run_screening(limit=100 if post_ids is not None else 30,
            include_old=include_old, post_ids=post_ids)
        if result.get('screened', {}).get('queued'):
            # Existing diagnosis task keeps its budget, pacing and thresholds.
            clinic_diagnose_task.apply_async(priority=0)
        return result
    finally:
        cache.delete("clinic-screen-lock")


@shared_task(name="news.tasks.clinic_daily_messages_task", soft_time_limit=600, time_limit=660)
def clinic_daily_messages_task():
    from news.clinic import run_daily_messages
    return run_daily_messages()


@shared_task(name="news.tasks.political_poll_task", soft_time_limit=90, time_limit=100)
def political_poll_task():
    """Run due official X groups, or one account in timeline mode.

    ``political_poll_cycle`` is independently opt-in, budgeted and leased.  A
    frequent scheduler tick therefore does not itself make a paid request when
    polling is disabled or no account is due.
    """
    from news.political_polling import political_poll_cycle
    return political_poll_cycle()


@shared_task(name='news.tasks.sync_live_public_rosters_task', soft_time_limit=600, time_limit=660)
def sync_live_public_rosters_task():
    """Refresh only rosters backed by a live, exact official source.

    This intentionally excludes static editorial lists such as KPRP leadership
    until each has its own live source adapter.  A failed source
    cannot block the other rosters or silently overwrite its last good state.
    No social account is discovered, confirmed or read here.
    """
    if not cache.add('lock:live-public-rosters', True, 900):
        return {'status': 'already_running', 'completed': [], 'failed': []}
    state, _ = ImportState.objects.get_or_create(name='public-figure:live-rosters')
    state.last_started = timezone.now()
    state.save(update_fields=['last_started'])
    completed, failed = [], []
    commands = [
        ('sejm-roster', 'sync_parliamentary_roster', {'source': 'sejm'}),
        ('sejm-profiles', 'sync_parliamentary_public_figures', {'source': 'sejm'}),
        ('senat-roster', 'sync_parliamentary_roster', {'source': 'senat'}),
        ('senat-profiles', 'sync_parliamentary_public_figures', {'source': 'senat'}),
        ('ep-roster', 'sync_parliamentary_roster', {'source': 'ep'}),
        ('ep-profiles', 'sync_parliamentary_public_figures', {'source': 'ep'}),
        ('voivodes', 'sync_voivodes', {}),
        ('cabinet', 'sync_public_figures', {'source': 'cabinet'}),
    ]
    try:
        for label, command, options in commands:
            if label.endswith('-profiles') and label.replace('-profiles', '-roster') not in completed:
                failed.append({'roster': label, 'error': 'roster_not_refreshed'})
                continue
            try:
                call_command(command, stdout=StringIO(), **options)
                completed.append(label)
            except Exception as exc:  # Preserve other independently official rosters.
                failed.append({'roster': label, 'error': type(exc).__name__})
        status = 'partial' if failed else 'ok'
        state.last_error = '' if not failed else 'Nie wszystkie oficjalne rostery odświeżono; szczegóły w stanie zadania.'
        if not failed:
            state.last_success = timezone.now()
        state.cursor = {'completed_at': timezone.now().isoformat(), 'status': status,
                        'completed': completed, 'failed': failed}
        state.save(update_fields=['last_success', 'last_error', 'cursor'])
        return {'status': status, 'completed': completed, 'failed': failed}
    finally:
        cache.delete('lock:live-public-rosters')



@shared_task(name="news.tasks.clinic_interview_task", soft_time_limit=1700, time_limit=1800)
def clinic_interview_task(day=None):
    """Wywiad dnia: transkrypcja (Gemini) i diagnoza Dr. Spina dla wklejonego linku. Wyłączone bez kluczy."""
    if not cache.add("clinic-interview-lock", "1", timeout=1790):
        return {"status": "locked"}
    try:
        from news.clinic_interview import run_interviews
        return run_interviews(limit=1, day=day)
    finally:
        cache.delete("clinic-interview-lock")



@shared_task(name="news.tasks.youtube_official_task", soft_time_limit=600, time_limit=660)
def youtube_official_task():
    """Najnowsze filmy z potwierdzonych oficjalnych kanałów YouTube (1 jednostka limitu na kanał)."""
    from news.youtube_collect import collect_latest
    return collect_latest()


@shared_task(name="news.tasks.weekly_report_task", soft_time_limit=600, time_limit=660)
def weekly_report_task():
    """Niedziela wieczorem: raport tygodnia Dr. Spina (dane + podsumowanie darmowym modelem)."""
    from news.weekly_report import generate
    report = generate()
    return {"status": "ok", "week_end": str(report.week_end), "summary": bool(report.summary)}


@shared_task(name="news.tasks.deleted_posts_task", soft_time_limit=600, time_limit=660)
def deleted_posts_task():
    """Strażnica usuniętych postów polityków — darmowy oEmbed X, do 60 wpisów na przebieg."""
    if not cache.add("deleted-posts-lock", "1", timeout=700):
        return {"status": "locked"}
    try:
        from news.deleted_posts import check_batch
        return check_batch()
    finally:
        cache.delete("deleted-posts-lock")


@shared_task(name="news.tasks.source_social_task", soft_time_limit=1500, time_limit=1600)
def source_social_task():
    """W nocy: linki YouTube i X na stronach źródeł — sprawdzenia starsze niż 30 dni albo ze starszej wersji."""
    if not cache.add("source-social-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        out = StringIO()
        call_command("discover_source_social_links", "--limit", "80", "--apply", stdout=out)
        return {"status": "ok", "summary": out.getvalue().strip().splitlines()[-1:]}
    finally:
        cache.delete("source-social-lock")


@shared_task(name="news.tasks.youtube_leftover_task", soft_time_limit=1500, time_limit=1600)
def youtube_leftover_task():
    """Przed resetem darmowego limitu (ok. 9:00): reszta jednostek na archiwum oficjalnych kanałów."""
    if not cache.add("youtube-leftover-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        from news.youtube_collect import backfill_leftover
        return backfill_leftover()
    finally:
        cache.delete("youtube-leftover-lock")


@shared_task(name="news.tasks.clinic_interview_pick_task", soft_time_limit=600, time_limit=660)
def clinic_interview_pick_task():
    """Rano: wynik zamkniętego o 7:00 głosowania trafia do kolejki wywiadu dnia."""
    from news.clinic_interview import pick_yesterday
    return pick_yesterday()


@shared_task(name="news.tasks.clinic_interview_candidates_task", soft_time_limit=600, time_limit=660)
def clinic_interview_candidates_task():
    from datetime import timedelta
    from news.daily_schedule import WARSAW
    from news.interview_votes import refresh_candidates
    from news.repairer import flag
    if not flag('CLINIC_INTERVIEW_ENABLED', False):
        return {'status': 'disabled'}
    if not cache.add('interview-candidates-lock', '1', timeout=660):
        return {'status': 'locked'}
    try:
        now = timezone.now().astimezone(WARSAW)
        day = now.date() - timedelta(days=1) if now.hour < 7 else now.date()
        return {'day': str(day), 'candidates': refresh_candidates(day)}
    finally:
        cache.delete('interview-candidates-lock')


@shared_task(name="news.tasks.newsletter_confirmation_task", soft_time_limit=60, time_limit=90)
def newsletter_confirmation_task(subscriber_id):
    """Mail z linkiem potwierdzającym zapis na newsletter."""
    from news.newsletter import send_confirmation
    return send_confirmation(subscriber_id)


@shared_task(name="news.tasks.krs_agent_task", soft_time_limit=1500, time_limit=1600)
def krs_agent_task():
    """Codziennie kilka kolejnych osób publicznych: podmioty z KRS (KRS_AGENT_ENABLED, KRS_AGENT_DAILY, KRS_DAILY_BUDGET_USD)."""
    if not cache.add("krs-agent-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        from news.krs_agent import run
        return run()
    finally:
        cache.delete("krs-agent-lock")


@shared_task(name="news.tasks.sejm_career_task", soft_time_limit=900, time_limit=960)
def sejm_career_task():
    """Kariera sejmowa (kadencje, daty mandatu, klub) z oficjalnego API Sejmu — raz w tygodniu."""
    from news.sejm_career import run
    return run()


@shared_task(name="news.tasks.social_publish_task", soft_time_limit=900, time_limit=960)
def social_publish_task():
    """Silne spiny na Facebooku, Instagramie, Bluesky i mail z filmem na TikTok i Shorts (SOCIAL_POST_ENABLED i klucze)."""
    if not cache.add("social-publish-lock", "1", timeout=1000):
        return {"status": "locked"}
    try:
        from news.social_publish import run
        return run()
    finally:
        cache.delete("social-publish-lock")


@shared_task(name="news.tasks.x_publish_task", soft_time_limit=300, time_limit=360)
def x_publish_task():
    """Wątki silnych spinów z konta spin.clinic (X_POST_ENABLED i klucze z uprawnieniem zapisu)."""
    if not cache.add("x-publish-lock", "1", timeout=400):
        return {"status": "locked"}
    try:
        from news.x_publish import run
        return run()
    finally:
        cache.delete("x-publish-lock")


@shared_task(name="news.tasks.dr_spin_thread_task", soft_time_limit=300, time_limit=360)
def dr_spin_thread_task():
    """Codzienna spinka kontekstowa; domyślnie wyłączona."""
    if not cache.add('dr-spin-thread-lock', '1', timeout=400):
        return {'status': 'locked'}
    try:
        from news.dr_spin_threads import build_daily_thread
        return build_daily_thread()
    finally:
        cache.delete('dr-spin-thread-lock')


@shared_task(name="news.tasks.account_warden_task", soft_time_limit=6000, time_limit=6300)
def account_warden_task():
    from news.account_warden import run
    return run()


@shared_task(name="news.tasks.council_recruiter_task", soft_time_limit=1500, time_limit=1600)
def council_recruiter_task():
    """Rekruter Konsylium (co noc): zawieszenia martwych członków, powroty, egzamin jednego kandydata."""
    if not cache.add("council-recruiter-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        from news.council_recruiter import run
        return run()
    finally:
        cache.delete("council-recruiter-lock")


@shared_task(name="news.tasks.konsylium_powtorz_task", soft_time_limit=1500, time_limit=1600)
def konsylium_powtorz_task():
    """Noc (2:40, po resecie limitów): powtórka diagnoz z ostatnich 7 dni wystawionych bez kworum Konsylium."""
    import os
    if os.environ.get("CLINIC_AI_ENABLED", "").lower() != "true":
        return {"status": "disabled"}
    if not cache.add("konsylium-powtorz-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        from news import council_rerun
        result = council_rerun.run(council_rerun.default_since(), limit=8)
        result.pop("rows", None)
        result["produced"] = result.get("done", 0)
        return result
    finally:
        cache.delete("konsylium-powtorz-lock")


@shared_task(name='news.tasks.council_audit_task', soft_time_limit=210, time_limit=240)
def council_audit_task():
    from news.council_auditor import run
    return run()


@shared_task(bind=True, name='news.tasks.inquisitor_task', soft_time_limit=900, time_limit=960, max_retries=15)
def inquisitor_task(self):
    from news.inquisitor import run
    result = run()
    if result['status'] == 'locked':
        raise self.retry(countdown=120)
    return result


# Register account tasks with Celery autodiscovery.
@shared_task(name='news.tasks.plain_reader_task', soft_time_limit=5700, time_limit=6000)
def plain_reader_task():
    if not cache.add('plain-reader-lock', '1', timeout=6100):
        return {'status': 'locked'}
    try:
        from news.plain_reader import run
        return run()
    finally:
        cache.delete('plain-reader-lock')


from news.notification_tasks import process_notification_events, send_notification_digests  # noqa: F401,E402

from news.account_lifecycle import send_password_reset, send_account_verification  # noqa: F401


@shared_task(name='news.tasks.clinic_video_stats_task', soft_time_limit=210, time_limit=240)
def clinic_video_stats_task():
    """Codzienny raport filmów i wspólne powiadomienie o kosztach oraz równowadze."""
    from news.clinic_video_stats import notify
    return {'sent': notify(daily=True)}


@shared_task(name="news.tasks.council_charter_missing_task", soft_time_limit=600, time_limit=660)
def council_charter_missing_task():
    """Po resecie darmowych limitów (2:15): Kartę przyjmują modele, które jeszcze nie odpowiedziały (np. po 429 lub 402)."""
    from io import StringIO
    from django.core.management import call_command
    out, err = StringIO(), StringIO()
    call_command('council_charter', missing=True, stdout=out, stderr=err)
    return {'status': 'ok', 'accepted': out.getvalue().count('\n'), 'no_answer': err.getvalue().count('\n')}


@shared_task(name='news.tasks.narrative_thread_task', soft_time_limit=120, time_limit=180)
def narrative_thread_task():
    from news.narrative_threads import build_narratives
    return build_narratives()


@shared_task(name='news.tasks.signal_threads_task', soft_time_limit=240, time_limit=300)
def signal_threads_task():
    from news.signal_threads import build_lobbying, build_new_narratives
    return {'lobbying': build_lobbying(), 'narratives': build_new_narratives()}


@shared_task(name='news.tasks.thread_reviews_task', soft_time_limit=840, time_limit=900)
def thread_reviews_task():
    from news.features import threads_enabled
    from news.thread_review import run_queue, backfill_queue
    if not threads_enabled():
        return {'status': 'disabled'}
    backfill_queue()
    return run_queue(limit=10)


@shared_task
def mechanik_task():
    """Co godzinę: modele Konsylium z błędem 404/400 albo zawieszone - sprawdzenie u dostawcy, próba, zamiennik nazwy."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import mechanik
    return mechanik.step()


@shared_task
def recenzent_task():
    """Co 2 godziny: Recenzent czyta nowe teksty (spinki Dr. Spina, przekazy, raporty, diagnozy) i wytyka błędy."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import recenzent
    from news.agents_common import WindowClosed
    from news import dyrygent
    try:
        with dyrygent.tier('strażnicy'):
            note = recenzent.step()
    except WindowClosed as error:
        return {'status': 'waiting', 'reason': str(error)}
    return {'status': 'ok', 'note': note.pk if note else None, 'produced': 1 if note else 0}


@shared_task
def projektant_task():
    """Raz w tygodniu (krok sam pomija, gdy raport ma mniej niż 6 dni): stan wiedzy UX/UI i przegląd stron."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import projektant
    from news.agents_common import WindowClosed
    from news import dyrygent
    try:
        with dyrygent.tier('nauka'):
            note = projektant.step()
    except WindowClosed as error:
        return {'status': 'waiting', 'reason': str(error)}
    return {'status': 'ok', 'note': note.pk, 'produced': 1}


@shared_task
def dyrygent_task():
    """Co 15 minut tryb według wolnych limitów; raz dziennie plan dnia (hierarchia pętli, kolizje, kolejka budowy)."""
    from news import dyrygent
    mode, free = dyrygent.decide()
    note = dyrygent.plan()
    return {'status': 'ok', 'free_pct': round(free * 100), 'plan': note.pk}


@shared_task
def sprint_intake_task():
    """6:00: w poniedziałek Sprint tygodnia (do 8 biletów budowy), w inne dni dopełnienie, gdy otwartych jest mniej niż 3."""
    from news import sprint
    return {'status': 'ok', **sprint.intake()}


@shared_task
def badacz_task():
    """Raz dziennie: pętla researchu - nowe źródła dla wszystkich agentów (Badacz, właściciel 5.10)."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import badacz
    from news.agents_common import WindowClosed
    try:
        from news import dyrygent
        with dyrygent.tier('nauka'):
            done = badacz.step()
        return {'status': 'ok', **{k.replace('ź', 'z').replace('ę', 'e').replace('ś', 's'): v for k, v in done.items()}}
    except WindowClosed as error:
        return {'status': 'waiting', 'reason': str(error)}


@shared_task(soft_time_limit=600, time_limit=660)
def zmiana_zdania_task():
    """Co 30 minut: Zmiana zdania - wcześniejsze wypowiedzi tej samej osoby przy nowych diagnozach (bez AI), potem jeden darmowy
    model ocenia pary w oknie agentów. Brak modelu = pary czekają; diagnoza nigdy na to nie czeka."""
    import os
    if os.environ.get('ZMIANA_ZDANIA_ENABLED', 'true').strip().lower() == 'false':
        return {'status': 'disabled'}
    from news import dyrygent, zmiana_zdania
    with dyrygent.tier('treść'):
        return zmiana_zdania.run()


@shared_task(soft_time_limit=600, time_limit=660)
def odbior_spinu_task():
    """Co godzinę: Jak spin zadziałał - dobę po wpisie z mocnym spinem liczniki i próbka odpowiedzi z oficjalnego API X
    (płatne odczyty, domyślnie wyłączone: X_REPLIES_ENABLED), ocena jednym darmowym modelem Konsylium. Tylko liczby zbiorcze."""
    from news import dyrygent, odbior_spinu
    with dyrygent.tier('treść'):
        return odbior_spinu.run()


@shared_task
def raport_petli_task():
    """Codziennie 7:05: Raport pętli mailem (audyt pętli 5.10). Bez AI; jeden mail na dzień."""
    import os
    if os.environ.get('LOOP_REPORT_ENABLED', 'true').strip().lower() == 'false':
        return {'status': 'disabled'}
    from news import raport_petli
    return raport_petli.send()


@shared_task
def opiekunowie_task():
    """Co godzinę: opiekunowie pętli (alarmy, naprawy, usprawnienia po kolei, bezpieczeństwo raz w tygodniu na pętlę)."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import opiekunowie
    from news import dyrygent
    with dyrygent.tier('niezawodność'):
        done = opiekunowie.step()
    return role_status(done, counts=True)


@shared_task
def automatyk_task():
    """Raz dziennie: przegląd wszystkich pętli agentów obu portali i usprawnienia (Automatyk, właściciel 5.10)."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import automatyk
    from news.agents_common import WindowClosed
    try:
        note = automatyk.step()
    except WindowClosed as error:
        return {'status': 'waiting', 'reason': str(error)}
    learned = None
    if automatyk.learn_due():  # wolny czas: nauka raz w tygodniu, po przeglądzie
        try:
            from news import dyrygent
            with dyrygent.tier('nauka'):
                learned = automatyk.learn().pk
        except WindowClosed:
            learned = None
    return {'status': 'ok', 'note': note.pk, 'learned': learned, 'produced': 1 + (learned is not None)}


@shared_task
def pracownia_osint_task():
    """Dwa razy dziennie krok Pracowni OSINT: każda rola sama pilnuje swojego terminu (kontroler codziennie, testy co 3 dni, reszta co tydzień)."""
    import os
    if os.environ.get('AGENTS_ENABLED', '').lower() != 'true':
        return {'status': 'disabled'}
    from news import pracownia_osint, przeszlosc
    if not przeszlosc.enabled():
        return {'status': 'disabled'}
    done = pracownia_osint.step()
    return {**role_status(done), 'roles': len(done)}


def role_status(done, counts=False):
    """Wynik kroku z wieloma rolami (Pracownia, Opiekunowie): błąd, gdy któraś rola padła; „waiting”, gdy nic nie powstało,
    a któraś rola czeka na okno modeli (audyt 5.10, P5: zielony puls bez wyniku). counts=True: liczby to liczba wpisów
    (Opiekunowie); inaczej liczba to numer jednego nowego wpisu (Pracownia)."""
    failed = sum(isinstance(v, str) and v.startswith('błąd') for v in done.values())
    waiting = sum(isinstance(v, str) and v.startswith('czeka') for v in done.values())
    numbers = [v for v in done.values() if type(v) is int]
    produced = sum(numbers) if counts else len(numbers)
    return {'status': 'error' if failed else 'waiting' if waiting and not produced else 'ok', 'failed': failed,
            'waiting': waiting, 'produced': produced}


@shared_task
def przeszlosc_topics_task():
    """Raz dziennie: automatyczny wybór tematów przeszłość.today z druków Sejmu i wpisów polityków."""
    from news import przeszlosc
    if not przeszlosc.enabled():
        return {'status': 'disabled'}
    return {'status': 'ok', 'topics': [t['topic'] for t in przeszlosc.pick_topics()]}


@shared_task(name="news.tasks.przeszlosc_alert_confirmation_task", soft_time_limit=60, time_limit=90)
def przeszlosc_alert_confirmation_task(alert_id):
    """Mail z linkiem potwierdzającym alert przeszłość.today (podwójne potwierdzenie)."""
    from news.przeszlosc_alerts import send_confirmation
    return send_confirmation(alert_id)


@shared_task(soft_time_limit=1500, time_limit=1600)
def przeszlosc_alerts_task():
    """Codziennie o 7:00: jeden list na adres z nowościami w obserwowanych tematach i osobach."""
    from news import przeszlosc
    from news.przeszlosc_alerts import send_digests
    if not przeszlosc.enabled():
        return {'status': 'disabled'}
    report = send_digests()
    return {'status': 'error' if report['failed'] else 'ok', **report}


@shared_task(soft_time_limit=540, time_limit=600)
def public_record_people_task():
    """Co noc: dokumenty Sejmu (interpelacje, zapytania, wystąpienia) łączone z osobami po oficjalnym id posła."""
    from news.public_record_people import link_people
    return {'status': 'ok', **link_people()}


@shared_task
def x_value_task():
    """Raz dziennie: czytanie X według wartości konta (właściciel 6.10: taniej i legalnie)."""
    from news import x_value
    return x_value.apply()


@shared_task(soft_time_limit=1500, time_limit=1600)
def voting_deviations_task():
    """Co noc: odstępstwa posłów od większości klubu (cała kadencja i 90 dni), bez AI i bez sieci."""
    from news import przeszlosc, voting_anomalies
    if not przeszlosc.enabled():
        return {'status': 'disabled'}
    return voting_anomalies.refresh()


@shared_task(soft_time_limit=600, time_limit=660)
def coordinated_narratives_task():
    """Co 2 godziny: wspólny przekaz (prawie identyczne wpisy z co najmniej 3 kont w 6 godzin), ostatnie 48 godzin."""
    from news import coordinated
    return coordinated.refresh()


@shared_task(soft_time_limit=1500, time_limit=1600)
def coordinated_narratives_night_task():
    """Co noc: wspólny przekaz z ostatniego tygodnia (wpisy dosłane później przez zbieranie X)."""
    from news import coordinated
    return coordinated.refresh(hours=coordinated.NIGHT_LOOKBACK_HOURS)


@shared_task(soft_time_limit=540, time_limit=600)
def raport_tygodniowy_task():
    """Poniedziałek 6:40: Raport tygodniowy dla instytucji (PDF + CSV) za poprzedni tydzień. Bez AI, bez wysyłki."""
    from news import agent_registry
    if not agent_registry.enabled(agent_registry.REGISTRY['raport-tygodniowy']):
        return {'status': 'disabled'}
    from news.raport_tygodniowy import generate
    return generate()


@shared_task(soft_time_limit=120, time_limit=150)
def sales_lead_confirmation_task(lead_id):
    """Mail z linkiem potwierdzającym zgłoszenie (raporty dla instytucji, pilot przeszłość.today)."""
    from news.sales import send_confirmation
    return send_confirmation(lead_id)


@shared_task(soft_time_limit=240, time_limit=300)
def sales_leads_task():
    """Co godzinę: ponowienia maili, powiadomienia właściciela o potwierdzonych zgłoszeniach, usuwanie niepotwierdzonych."""
    from news.sales import run
    return run()

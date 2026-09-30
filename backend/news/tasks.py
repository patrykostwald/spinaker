"""Celery tasks owned by the editorial-news domain."""
from io import StringIO

from celery import shared_task
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState


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
    if not cache.add("clinic-diagnose-lock", "1", timeout=1700):
        return {"status": "locked"}
    try:
        from news.clinic import fill_x_threads, run_diagnoses
        result = run_diagnoses(limit=2)
        # Syntezy do wątków na X dla starszych diagnoz (darmowy model, po kilka na raz).
        result['x_threads'] = fill_x_threads(limit=3)
        return result
    finally:
        cache.delete("clinic-diagnose-lock")


@shared_task(name="news.tasks.clinic_screen_task", soft_time_limit=600, time_limit=660)
def clinic_screen_task():
    """Strażnik Kliniki: darmowa ocena nowych postów (Groq, zapasowo NVIDIA NIM)."""
    if not cache.add("clinic-screen-lock", "1", timeout=700):
        return {"status": "locked"}
    try:
        from news.clinic import run_screening
        return run_screening(limit=30)
    finally:
        cache.delete("clinic-screen-lock")


@shared_task(name="news.tasks.clinic_daily_messages_task", soft_time_limit=600, time_limit=660)
def clinic_daily_messages_task():
    from news.clinic import run_daily_messages
    return run_daily_messages()


@shared_task(name="news.tasks.political_poll_task", soft_time_limit=45, time_limit=60)
def political_poll_task():
    """Run at most one due, confirmed political X account.

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
def clinic_interview_task():
    """Wywiad dnia: transkrypcja (Gemini) i diagnoza Dr. Spina dla wklejonego linku. Wyłączone bez kluczy."""
    if not cache.add("clinic-interview-lock", "1", timeout=1790):
        return {"status": "locked"}
    try:
        from news.clinic_interview import run_interviews
        return run_interviews(limit=1)
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
    """Rano: najgłośniejszy wywiad z politykiem z poprzedniego dnia trafia do kolejki wywiadu dnia."""
    from news.clinic_interview import pick_yesterday
    return pick_yesterday()


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
    """Codzienna nitka kontekstowa; domyślnie wyłączona."""
    if not cache.add('dr-spin-thread-lock', '1', timeout=400):
        return {'status': 'locked'}
    try:
        from news.dr_spin_threads import build_daily_thread
        return build_daily_thread()
    finally:
        cache.delete('dr-spin-thread-lock')


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

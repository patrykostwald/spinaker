"""Audyt gotowości bety: klucze, poczta, X, agenci, zadania w tle i świeżość danych. Nie wypisuje żadnych sekretów.

  python manage.py beta_audit
"""
import os
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sprawdza gotowość bety (bez wypisywania kluczy).'

    def line(self, ok, label, detail=''):
        mark = {True: 'OK  ', False: 'BŁĄD', None: 'UWAGA'}[ok]
        self.stdout.write(f'[{mark}] {label}' + (f' — {detail}' if detail else ''))

    def handle(self, *args, **options):
        from news import clinic, krs_agent, newsletter, x_publish
        from news.clinic_models import SpinDiagnosis
        from news.models import Article
        from news.political_models import PoliticalPost, PublicFigure, PublicFigureOrganisationRelation, PublicFigureRole
        now = timezone.now()
        day = now - timedelta(hours=24)

        self.stdout.write('== Klucze i usługi')
        bearer = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
        try:
            r = requests.get('https://api.x.com/2/users/by/username/spinclinic', headers={'Authorization': f'Bearer {bearer}'}, timeout=20)
            self.line(r.status_code == 200, 'X — odczyt postów polityków', f'HTTP {r.status_code}')
        except requests.RequestException as error:
            self.line(False, 'X — odczyt postów polityków', type(error).__name__)
        if x_publish.enabled():
            url = 'https://api.x.com/2/users/me'
            try:
                r = requests.get(url, headers={'Authorization': x_publish._oauth_header('GET', url)}, timeout=20)
                who = r.json().get('data', {}).get('username') if r.status_code == 200 else ''
                self.line(r.status_code == 200 and who == 'spinclinic', 'X — publikowanie z @spinclinic', f'HTTP {r.status_code} {who}')
            except (requests.RequestException, ValueError) as error:
                self.line(False, 'X — publikowanie', type(error).__name__)
        else:
            self.line(None, 'X — publikowanie wyłączone', 'X_POST_ENABLED albo klucze X_POST_*')
        key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
        try:
            r = requests.post('https://api.anthropic.com/v1/messages', timeout=30, headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
                              json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1, 'messages': [{'role': 'user', 'content': 'ok'}]})
            self.line(r.status_code == 200, 'Anthropic (Claude)', f'HTTP {r.status_code}' + ('' if r.status_code == 200 else ' ' + r.text[:80]))
        except requests.RequestException as error:
            self.line(False, 'Anthropic (Claude)', type(error).__name__)
        for name in ('GEMINI_API_KEY', 'GROQ_API_KEY', 'NIM_API_KEY', 'YOUTUBE_API_KEY'):
            self.line(bool(os.environ.get(name, '').strip()), name.replace('_API_KEY', ''), 'klucz ustawiony' if os.environ.get(name) else 'brak klucza')
        self.line(newsletter.smtp_ready() or None, 'Poczta (SMTP) — newsletter i alarmy',
                  'skonfigurowana' if newsletter.smtp_ready() else 'brak SOURCE_MAIL_SMTP_* — maile nie wychodzą')
        alert_to = os.environ.get('X_POST_ALERT_EMAIL', '').strip() or os.environ.get('CLINIC_REVIEW_EMAIL', '').strip()
        self.line(bool(alert_to) or None, 'Adres alarmów', 'ustawiony' if alert_to else 'brak X_POST_ALERT_EMAIL / CLINIC_REVIEW_EMAIL')

        self.stdout.write('== Dane i zadania w tle')
        fetched = PoliticalPost.objects.filter(fetched_at__gte=day).count()
        self.line(fetched > 0, 'Posty polityków z ostatniej doby', str(fetched))
        rows = SpinDiagnosis.objects.filter(created_at__gte=day)
        statuses = {s: rows.filter(status=s).count() for s in ('approved', 'queued', 'flagged', 'not_applicable', 'failed')}
        self.line(statuses['failed'] < 5, 'Klinika — statusy z ostatniej doby', ', '.join(f'{k}: {v}' for k, v in statuses.items()))
        last = SpinDiagnosis.objects.filter(status='approved').aggregate(t=Max('diagnosed_at'))['t']
        self.line(bool(last and now - last < timedelta(hours=30)), 'Ostatnia opublikowana diagnoza', str(last)[:16] if last else 'brak')
        self.line(None, 'Wydatki AI dziś (limit CLINIC_DAILY_BUDGET_USD)', f'{clinic.spent_today():.2f} USD')
        checked = PoliticalPost.objects.aggregate(t=Max('availability_checked_at'))['t']
        self.line(bool(checked and now - checked < timedelta(hours=8)), 'Strażnica usuniętych wpisów — ostatnie sprawdzenie', str(checked)[:16] if checked else 'nigdy')
        posted = SpinDiagnosis.objects.filter(x_posted_at__isnull=False).aggregate(t=Max('x_posted_at'))['t']
        self.line(None, 'Ostatni wpis @spinclinic', str(posted)[:16] if posted else 'jeszcze nic')
        votes = Article.objects.filter(category='voting').aggregate(t=Max('published_date'))['t']
        self.line(bool(votes and now - votes < timedelta(days=21)) or None, 'Ostatnie głosowanie Sejmu w Bazie', str(votes)[:10] if votes else 'brak')
        self.line(PublicFigureRole.objects.filter(since__isnull=False).exists(), 'Kariera sejmowa z datami',
                  f'{PublicFigureRole.objects.filter(since__isnull=False).count()} funkcji z datami')
        done = PublicFigure.objects.filter(organisations_checked_at__isnull=False).count()
        confirmed = PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed').count()
        self.line(krs_agent.enabled() or None, 'Agent KRS', f'sprawdzone osoby: {done} z {PublicFigure.objects.count()}, potwierdzone podmioty: {confirmed}')
        stats = newsletter.stats()
        self.line(None, 'Newsletter', f"potwierdzeni {stats['confirmed']}, czekają {stats['pending']}")
        self.stdout.write('Kopia bazy: sprawdź na serwerze poleceniem  ls -lh /srv/backups')

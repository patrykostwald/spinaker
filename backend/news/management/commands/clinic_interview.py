"""Wywiad dnia z terminala: python manage.py clinic_interview <link YouTube> [--day RRRR-MM-DD] [--now]."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from news import clinic_interview


class Command(BaseCommand):
    help = 'Dodaje wywiad dnia (publiczny film z YouTube) do kolejki; --now od razu robi transkrypcję i diagnozę.'

    def add_arguments(self, parser):
        parser.add_argument('url', nargs='?', default='', help='Link do filmu; pomiń przy --auto.')
        parser.add_argument('--auto', action='store_true', help='Wybierz sam najgłośniejszy wywiad z wczoraj.')
        parser.add_argument('--day', default='', help='Dzień emisji (domyślnie wczoraj).')
        parser.add_argument('--now', action='store_true', help='Nie czekaj na harmonogram — przetwórz od razu.')
        parser.add_argument('--rediagnose', action='store_true', help='Nowa diagnoza z zapisanej transkrypcji (bez Gemini).')

    def handle(self, *args, url, day, now, auto, rediagnose, **options):
        if rediagnose:
            from news.clinic_models import ClinicInterview
            interview = ClinicInterview.objects.filter(video_id=clinic_interview.video_id(url) or '').first()
            if not interview:
                raise CommandError('Nie ma takiego wywiadu w bazie.')
            interview = clinic_interview.rediagnose(interview)
            self.stdout.write(f'Status: {interview.status}\n{interview.headline}\n{interview.summary}')
            return
        if auto:
            result = clinic_interview.pick_yesterday()
            self.stdout.write(str(result))
            if result.get('status') != 'queued':
                return
            from news.clinic_models import ClinicInterview
            url = ClinicInterview.objects.get(pk=result['id']).url
        try:
            interview = clinic_interview.queue_interview(url, date.fromisoformat(day) if day else None)
        except ValueError:
            raise CommandError('To nie jest link do filmu na YouTube (albo zła data).')
        self.stdout.write(f'W kolejce: {interview.url} · dzień {interview.day}')
        if now:
            if not clinic_interview.enabled():
                raise CommandError('Wyłączone: ustaw CLINIC_INTERVIEW_ENABLED=true, GEMINI_API_KEY, CLINIC_AI_ENABLED i ANTHROPIC_API_KEY.')
            if not clinic_interview.claim(interview):
                raise CommandError('Ten wywiad właśnie się opracowuje (automat albo inne okno) — poczekaj kilka minut.')
            interview = clinic_interview.process(interview)
            self.stdout.write(f'Status: {interview.status} {interview.error}'.strip())
            if interview.status == 'approved':
                self.stdout.write(f'{interview.title}\n{interview.headline}\n{interview.summary}')

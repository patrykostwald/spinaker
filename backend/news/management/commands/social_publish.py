"""Wpisy silnych spinów poza X (Facebook, Instagram, Bluesky, mail z filmem na TikTok i Shorts).

  python manage.py social_publish --status        # które kanały mają klucze
  python manage.py social_publish --dry-run       # teksty dla najbliższej diagnozy, bez wysyłania
  python manage.py social_publish --preview 123   # film z diagnozy 123 mailem do Ciebie (nic nie publikuje)
  python manage.py social_publish                 # jeden przebieg (to samo, co zadanie co 30 minut)
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Publikuje silne spiny na Facebooku, Instagramie i Bluesky; film na TikTok i Shorts mailem.'

    def add_arguments(self, parser):
        parser.add_argument('--status', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--preview', type=int)

    def handle(self, *args, status=False, dry_run=False, preview=None, **options):
        from news import social_publish
        if status:
            ready = social_publish.channels()
            self.stdout.write('Kanały gotowe: ' + (', '.join(ready) if ready else 'żaden (SOCIAL_POST_ENABLED=true i klucze)'))
            return
        if preview:
            from news.clinic_models import SpinDiagnosis
            diagnosis = SpinDiagnosis.objects.filter(pk=preview).select_related('post__account').first()
            if diagnosis is None:
                raise CommandError('Nie ma takiej diagnozy.')
            path = social_publish.ensure_video(diagnosis)
            text = social_publish.texts(diagnosis)
            sent = social_publish._mail(social_publish._video_email(), f'spin.clinic: podgląd filmu diagnozy {preview}',
                                        f"Podgląd — nic nie zostało opublikowane.\n\nOpis na Facebooka:\n\n{text['facebook']}"
                                        f"\n\nOpis na Instagram:\n\n{text['instagram']}\n\nBluesky:\n\n{text['bluesky']}", path)
            self.stdout.write(f"Film: {path} ({path.stat().st_size // 1024} KB) — mail {'wysłany' if sent else 'NIE wysłany (SMTP / adres)'}")
            return
        result = social_publish.run(dry_run=dry_run)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))

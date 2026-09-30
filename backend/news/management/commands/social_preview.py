"""Podgląd materiałów bez publikacji i zapisu syntezy w bazie."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Zapisuje teksty, kartę i opcjonalnie film diagnozy bez publikowania.'

    def add_arguments(self, parser):
        parser.add_argument('id', type=int)
        parser.add_argument('--out', default=None)
        parser.add_argument('--video', action='store_true')

    def handle(self, *args, **options):
        from news.clinic_models import SpinDiagnosis
        from news.social_content import prepare
        from news.social_publish import texts_from_data
        from news.x_card import fields, render
        from news.x_publish import polish
        from news.x_share import build, weight
        try:
            diagnosis = SpinDiagnosis.objects.select_related('post__account').get(pk=options['id'])
        except SpinDiagnosis.DoesNotExist as error:
            raise CommandError('Nie znaleziono diagnozy.') from error
        data = prepare(diagnosis, save=False)
        posts = [polish(text) for text in build(data, account=True)]
        captions = texts_from_data(data)
        out = Path(options['out'] or f'social-preview-{diagnosis.pk}')
        out.mkdir(parents=True, exist_ok=True)
        sections = [f'Wpis {i} ({weight(text)} znaków ważonych)\n{text}' for i, text in enumerate(posts, 1)]
        sections += [f'{label} ({len(captions[key])} znaków)\n{captions[key]}'
                     for key, label in [('facebook', 'Facebook'), ('instagram', 'Instagram'), ('bluesky', 'Bluesky')] if key in captions]
        if not posts:
            sections = ['Brak poprawnej syntezy — publikacja zostanie pominięta.']
        (out / 'wpisy.txt').write_text('\n\n'.join(sections), encoding='utf-8')
        card = fields(diagnosis)
        (out / 'karta.png').write_bytes(render(**card))
        if options['video']:
            from news.social_video import render as video
            video(data, card, str(out / 'film.mp4'))
        self.stdout.write(str(out.resolve()))

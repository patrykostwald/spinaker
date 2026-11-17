"""Zwiadowca rozwiązań od ręki.

python manage.py zwiadowca_start --plan   - linia bazowa bez sieci: co używamy wobec znanych darmowych alternatyw i luk w danych
python manage.py zwiadowca_start          - jeden przebieg obserwatorów (sieć: publiczne katalogi i kanały); pierwszy = linia bazowa
python manage.py zwiadowca_start --zwiad  - zwiad tygodnia teraz (jeden darmowy model, Inception pierwszy)"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Zwiadowca rozwiązań: plan startowy, obserwatorzy albo zwiad tygodnia.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', action='store_true', help='tylko porównanie bez sieci')
        parser.add_argument('--zwiad', action='store_true', help='zwiad tygodnia teraz (model AI)')

    def handle(self, *args, **options):
        from news import zwiadowca_rozwiazan as zwiad
        out = self.stdout.write
        if options['plan']:
            out(zwiad.plan_text())
            return
        if options['zwiad']:
            from news.agents_common import WindowClosed
            try:
                note = zwiad.scout(force=True)
            except WindowClosed as error:
                out(f'Czeka: {error}')
                return
            out(f'Ustalenie #{note.pk}: {note.title}')
            out(note.body)
            return
        result = zwiad.run_watchers()
        out(f"Pozycje: {result['items']}, nowe: {result['new']}, sygnały: {result['signals']}"
            + (' (linia bazowa: bez sygnałów)' if result['baseline'] else '') + f", zamknięte: {result['consumed']}")
        for name, error in result['errors'].items():
            out(f'  {name}: {error}')
        out('')
        out(zwiad.plan_text())

"""Porównanie: konsylium darmowych modeli obok dotychczasowej diagnozy (Claude) na tych samych postach. Niczego nie zapisuje."""
from django.core.management.base import BaseCommand

from news import clinic, clinic_ai, clinic_council
from news.clinic_models import SpinDiagnosis


class Command(BaseCommand):
    help = 'Konsylium obok dotychczasowych diagnoz tych samych postów (bez zapisu). --limit N.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=3)

    def handle(self, *args, limit, **options):
        rows = (clinic.published_diagnoses().exclude(model_name__startswith='konsylium')
                .select_related('post__account').order_by('-diagnosed_at')[:limit])
        for row in rows:
            figure = clinic.figures_by_account([row.post.account_id]).get(row.post.account_id)
            context = clinic._post_context(row.post, figure)
            lines = '\n'.join([f"Autor: {context['author']}", f"Obóz: {context['camp_label']}",
                               f"Data publikacji: {context['published_at']}", '', 'Treść posta:', '<<<', context['text'], '>>>'])
            from news.post_attachments import describe
            attachments = describe(context['text'], context.get('media') or [])
            if attachments:
                lines += '\n\nZałączniki posta (opis automatyczny):\n' + attachments
            self.stdout.write('=' * 100)
            self.stdout.write(f'{context["author"]} · {row.post.url}')
            self.stdout.write(f'DOTYCHCZAS ({row.model_name}): {row.verdict} {row.intensity}/100 — {row.headline}')
            self.stdout.write('   techniki: ' + ', '.join(t.get('name', '') for t in row.techniques))
            try:
                result = clinic_council.diagnose(context, lines)
            except clinic_ai.ClinicAIError as error:
                self.stdout.write(f'KONSYLIUM: błąd — {error.code}')
                continue
            council = result['usage']['council']
            self.stdout.write(f'KONSYLIUM ({council["agreement"]}): {result["verdict"]} {result["intensity"]}/100 — {result["headline"]}')
            self.stdout.write('   techniki: ' + ', '.join(t['name'] for t in result['techniques']))
            self.stdout.write('   głosy: ' + '; '.join(f"{m['model'].split('/')[-1]} {m['verdict']} {m['intensity']}" for m in council['members']))
            self.stdout.write(f'   recenzja: {council["review"]} · docisk Claude: {"tak" if council["escalated"] else "nie"}')
            self.stdout.write('   ' + result['summary'])

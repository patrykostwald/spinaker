"""Write a review queue for official X-link evidence without resolving accounts."""
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from news.political_models import PublicFigure, SocialHandleEvidence


class Command(BaseCommand):
    help = ('Tworzy kolejkę redakcyjną oficjalnych dowodów kont X. '
            'Nie tworzy kont, kandydatur ani zapytań do X.')

    def add_arguments(self, parser):
        parser.add_argument('--report-path', default='reports/public-figure-x-evidence-queue-current.md')

    def handle(self, *args, **options):
        evidence = list(SocialHandleEvidence.objects.select_related('roster_entry', 'candidate').order_by(
            'status', 'handle', 'pk'))
        public_figure_type = ContentType.objects.get_for_model(PublicFigure)
        figures = PublicFigure.objects.in_bulk(
            [item.subject_object_id for item in evidence
             if item.subject_content_type_id == public_figure_type.pk and item.subject_object_id])

        rows = []
        for item in evidence:
            if item.roster_entry_id:
                subject = f'{item.roster_entry.full_name} ({item.roster_entry.get_source_display()} #{item.roster_entry.external_id})'
            elif item.subject_content_type_id == public_figure_type.pk:
                figure = figures.get(item.subject_object_id)
                subject = figure.canonical_name if figure else 'Brakujący profil osoby publicznej'
            else:
                subject = 'Nieokreślony profil'
            rows.append((item, subject))

        pending = sum(item.status == 'pending_review' for item, _ in rows)
        candidates = sum(item.status == 'candidate_created' for item, _ in rows)
        rejected = sum(item.status == 'rejected' for item, _ in rows)
        lines = [
            '# Kolejka oficjalnych dowodów kont X',
            '',
            'Każdy wiersz zawiera link X znaleziony na wskazanej oficjalnej stronie. '
            'Dowód nie jest jeszcze potwierdzonym kontem ani zezwoleniem na pobieranie postów.',
            '',
            f'- Do weryfikacji redakcyjnej: **{pending}**.',
            f'- Przekazane do kandydatur: **{candidates}**.',
            f'- Odrzucone: **{rejected}**.',
            '',
            '| Osoba / roster | Konto X | Oficjalny dowód | Bezpośredni link X | Etap |',
            '| --- | --- | --- | --- | --- |',
        ]
        status_labels = dict(SocialHandleEvidence._meta.get_field('status').choices)
        for item, subject in rows:
            lines.append(
                f'| {subject} | @{item.handle} | {item.evidence_url} | {item.extracted_url} '
                f'| {status_labels[item.status]} |'
            )
        report_path = Path(options['report_path'])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'PUBLIC_FIGURE_X_EVIDENCE_QUEUE: total={len(rows)} pending_review={pending} '
            f'candidate_created={candidates} rejected={rejected}; {report_path}'
        ))

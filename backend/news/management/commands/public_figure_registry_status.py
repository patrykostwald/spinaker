"""Report the evidence-backed public-figure registry without exposing private data."""
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count

from news.political_models import (
    ParliamentaryRosterEntry,
    PublicFigure,
    PublicFigureOrganisationRelation,
    SocialHandleEvidence,
)


SOURCE_LABELS = {
    'sejm': 'Sejm RP',
    'senat': 'Senat RP',
    'ep': 'Parlament Europejski',
}


class Command(BaseCommand):
    help = ('Pokazuje stan rejestru osób publicznych: oficjalne mandaty, profile, '
            'potwierdzone relacje z podmiotami i dowody kont X. Nie pokazuje danych wrażliwych.')

    def add_arguments(self, parser):
        parser.add_argument('--report-path', default='reports/public-figure-registry-current.md')

    def handle(self, *args, **options):
        roster_counts = {
            row['source']: row['count']
            for row in ParliamentaryRosterEntry.objects.filter(active=True).values('source').annotate(
                count=Count('id'))
        }
        profile_counts = {
            (row['role_category'], row['status']): row['count']
            for row in PublicFigure.objects.filter(archived=False).values(
                'role_category', 'status').annotate(count=Count('id'))
        }
        active_profiles = sum(profile_counts.values())
        current_profiles = sum(count for (category, status), count in profile_counts.items()
                               if status == 'current')
        confirmed_relations = PublicFigureOrganisationRelation.objects.filter(
            verification_status='confirmed').count()
        pending_relations = PublicFigureOrganisationRelation.objects.filter(
            verification_status='pending_review').count()
        confirmed_x_evidence = SocialHandleEvidence.objects.filter(status='confirmed').count()

        lines = [
            '# Stan rejestru osób publicznych',
            '',
            'Raport obejmuje wyłącznie dane publiczne i potwierdzone źródła. '
            'Nie zawiera PESEL, dat urodzenia, adresów ani automatycznych dopasowań nazwisk.',
            '',
            '## Oficjalne rostery mandatów',
            '',
            '| Roster | Aktywne wpisy |',
            '| --- | ---: |',
        ]
        for source in ('sejm', 'senat', 'ep'):
            lines.append(f'| {SOURCE_LABELS[source]} | {roster_counts.get(source, 0)} |')

        lines += [
            '',
            '## Profile w portalu',
            '',
            '| Kategoria roli | Aktualne | Byłe |',
            '| --- | ---: | ---: |',
        ]
        categories = ('government', 'party', 'parliamentary', 'european', 'local', 'political')
        category_labels = dict(PublicFigure._meta.get_field('role_category').choices)
        for category in categories:
            lines.append(
                f'| {category_labels[category]} | {profile_counts.get((category, "current"), 0)} '
                f'| {profile_counts.get((category, "former"), 0)} |'
            )

        lines += [
            '',
            '## Potwierdzenia',
            '',
            f'- Profile niearchiwalne: **{active_profiles}** (aktualne: **{current_profiles}**).',
            f'- Potwierdzone relacje z podmiotami: **{confirmed_relations}**.',
            f'- Relacje oczekujące na redakcję: **{pending_relations}**.',
            f'- Potwierdzone dowody kont X: **{confirmed_x_evidence}**.',
            '',
            'Brak relacji nie oznacza braku powiązań: oznacza jedynie, że portal nie ma jeszcze '
            'potwierdzonego publicznego dowodu konkretnej relacji.',
        ]
        report = '\n'.join(lines) + '\n'
        report_path = Path(options['report_path'])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'PUBLIC_FIGURE_REGISTRY: roster={sum(roster_counts.values())} profiles={active_profiles} '
            f'confirmed_relations={confirmed_relations} confirmed_x_evidence={confirmed_x_evidence}; '
            f'{report_path}'
        ))

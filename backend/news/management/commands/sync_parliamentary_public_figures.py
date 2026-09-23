"""Materialise public profiles from exact, official parliamentary roster entries."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.political_models import ParliamentaryRosterEntry, PublicFigure


PROFILE_DETAILS = {
    'sejm': ('parliamentary', 'Poseł na Sejm RP', 'Sejm Rzeczypospolitej Polskiej'),
    'senat': ('parliamentary', 'Senator Rzeczypospolitej Polskiej', 'Senat Rzeczypospolitej Polskiej'),
    'ep': ('european', 'Poseł do Parlamentu Europejskiego', 'Parlament Europejski'),
}


class Command(BaseCommand):
    help = ('Tworzy profile osób publicznych wyłącznie z dokładnych wpisów oficjalnego rosteru. '
            'Nie dopasowuje nazwisk, nie tworzy kont X ani nie pobiera danych z rejestrów.')

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, choices=PROFILE_DETAILS)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source = options['source']
        role_category, role_title, organisation = PROFILE_DETAILS[source]
        roster = list(ParliamentaryRosterEntry.objects.filter(source=source, active=True).order_by('external_id'))
        if not roster:
            raise CommandError('Brak aktywnych wpisów oficjalnego rosteru; najpierw uruchom synchronizację rosteru.')
        keys = {f'parliamentary:{source}:{entry.external_id}' for entry in roster}
        existing = {figure.import_key: figure for figure in PublicFigure.objects.filter(
            import_key__startswith=f'parliamentary:{source}:')}
        created = sum(key not in existing for key in keys)
        updated = len(roster) - created
        former = PublicFigure.objects.filter(import_key__startswith=f'parliamentary:{source}:',
            archived=False, status='current').exclude(import_key__in=keys).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd {source}: aktywnych wpisów {len(roster)}; nowe profile {created}; '
                f'do aktualizacji {updated}; do oznaczenia jako byli {former}. Bez zapisu i bez działań w X.'
            ))
            return
        now = timezone.now()
        with transaction.atomic():
            for entry in roster:
                PublicFigure.objects.update_or_create(
                    import_key=f'parliamentary:{source}:{entry.external_id}',
                    defaults={
                        'canonical_name': entry.full_name,
                        'role_category': role_category,
                        'role_title': role_title,
                        'organisation': organisation,
                        'status': 'current',
                        'official_profile_url': entry.profile_url,
                        'evidence_url': entry.source_url,
                        'evidence_note': f'Oficjalny roster: {entry.get_source_display()}.',
                        'source_checked_at': now,
                        'parliamentary_roster_entry': entry,
                        'archived': False,
                    },
                )
            PublicFigure.objects.filter(import_key__startswith=f'parliamentary:{source}:',
                archived=False, status='current').exclude(import_key__in=keys).update(
                    status='former', source_checked_at=now)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(roster)} profili {source}; nowe {created}; zaktualizowane {updated}; '
            f'oznaczone jako byli {former}. Nie utworzono kont X ani kandydatur.'
        ))

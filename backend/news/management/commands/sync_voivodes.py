"""Synchronize current voivodes from the official KPRM roster."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from news.political_models import PublicFigure, PublicFigureRole, PublicOffice
from news.voivode_roster import get_rows


def holder_import_key(region, name):
    """Key the sourced person/term separately from the durable office.

    The regional office is stable, while a new holder must leave the prior
    public profile and role history intact.  This is an import identity, not
    an assertion that similarly named profiles from other rosters are equal.
    """
    return f'government:voivode:{region}:holder:{slugify(name)}'


class Command(BaseCommand):
    help = ('Synchronizuje wojewodów z aktualnej oficjalnej listy KPRM. '
            'Nie dopasowuje nazwisk, nie tworzy kont X i nie pobiera danych rejestrowych.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        rows = list(get_rows())
        keys = {holder_import_key(row.region, row.canonical_name) for row in rows}
        existing = set(PublicFigure.objects.filter(import_key__in=keys).values_list('import_key', flat=True))
        created = len(keys - existing)
        updated = len(keys & existing)
        former = PublicFigure.objects.filter(import_key__startswith='government:voivode:',
            archived=False, status='current').exclude(import_key__in=keys).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd wojewodów: {len(rows)} wpisów; nowe {created}; do aktualizacji {updated}; '
                f'do oznaczenia jako byli {former}. Bez zapisu i bez działań w X.'
            ))
            return
        now = timezone.now()
        with transaction.atomic():
            for row in rows:
                figure, _ = PublicFigure.objects.update_or_create(
                    import_key=holder_import_key(row.region, row.canonical_name),
                    defaults={
                        'canonical_name': row.canonical_name,
                        'role_category': 'government',
                        'role_title': row.role_title,
                        'organisation': row.organisation,
                        'status': 'current',
                        'official_profile_url': '',
                        'evidence_url': row.source_url,
                        'evidence_note': 'Aktualna lista wojewodów wskazana przez KPRM.',
                        'source_checked_at': now,
                        'parliamentary_roster_entry': None,
                        'archived': False,
                    },
                )
                public_office, _ = PublicOffice.objects.update_or_create(
                    import_key=f'public-office:voivode:{row.region}',
                    defaults={
                        'title': row.role_title,
                        'role_category': 'government',
                        'organisation': row.organisation,
                        'official_roster_url': row.source_url,
                        'evidence_note': 'Aktualna lista wojewodów wskazana przez KPRM.',
                        'current_holder': figure,
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
                # A change of holder closes the previous sourced role while the
                # durable office remains the same registry record.
                PublicFigureRole.objects.filter(public_office=public_office,
                    status='current', archived=False).exclude(public_figure=figure).update(
                        status='former', source_checked_at=now)
                PublicFigureRole.objects.update_or_create(
                    import_key=f'public-office:voivode:{row.region}:holder:{figure.import_key}',
                    defaults={
                        'public_figure': figure,
                        'public_office': public_office,
                        'role_category': 'government',
                        'role_title': row.role_title,
                        'organisation': row.organisation,
                        'status': 'current',
                        'official_profile_url': '',
                        'evidence_url': row.source_url,
                        'evidence_note': 'Aktualna lista wojewodów wskazana przez KPRM.',
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
            PublicFigure.objects.filter(import_key__startswith='government:voivode:',
                archived=False, status='current').exclude(import_key__in=keys).update(
                    status='former', source_checked_at=now)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(rows)} wojewodów; nowe {created}; zaktualizowane {updated}; '
            f'oznaczone jako byli {former}. Nie utworzono kont X ani kandydatur.'
        ))

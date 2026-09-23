"""Merge only profiles sharing one exact official roster entry."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from news.political_models import PublicFigure, PublicFigureRole


def canonical_profile(profiles):
    return next((profile for profile in profiles if profile.import_key.startswith('parliamentary:')), profiles[0])


class Command(BaseCommand):
    help = ('Łączy wyłącznie profile wskazujące ten sam dokładny wpis oficjalnego rosteru. '
            'Pozostawia jedną osobę i zachowuje role jako osobne, udokumentowane rekordy.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        duplicated_entry_ids = PublicFigure.objects.filter(archived=False,
            parliamentary_roster_entry__isnull=False).values('parliamentary_roster_entry_id').annotate(
                total=Count('id')).filter(total__gt=1).values_list('parliamentary_roster_entry_id', flat=True)
        groups = []
        for entry_id in duplicated_entry_ids:
            profiles = list(PublicFigure.objects.filter(archived=False,
                parliamentary_roster_entry_id=entry_id).order_by('pk'))
            groups.append((canonical_profile(profiles), profiles))
        duplicates = sum(len(profiles) - 1 for _, profiles in groups)
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd: grup duplikatów {len(groups)}; profile do archiwizacji {duplicates}. Bez zapisu.'
            ))
            return
        roles_created = 0
        with transaction.atomic():
            for canonical, profiles in groups:
                for profile in profiles:
                    _, created = PublicFigureRole.objects.update_or_create(
                        import_key=f'profile-role:{profile.import_key}',
                        defaults={
                            'public_figure': canonical,
                            'role_category': profile.role_category,
                            'role_title': profile.role_title,
                            'organisation': profile.organisation,
                            'status': profile.status,
                            'official_profile_url': profile.official_profile_url,
                            'evidence_url': profile.evidence_url,
                            'evidence_note': profile.evidence_note,
                            'source_checked_at': profile.source_checked_at,
                            'archived': False,
                        },
                    )
                    roles_created += int(created)
                    if profile.pk != canonical.pk:
                        profile.archived = True
                        profile.save(update_fields=['archived', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(
            f'Połączono grup {len(groups)}; zarchiwizowano duplikatów {duplicates}; '
            f'zapisano ról {roles_created}. Nie wykonano dopasowania po nazwisku.'
        ))

"""Synchronise a small, explicitly evidenced set of highest state offices.

The parliamentary roles below point to a *known official Senate roster id*.
They deliberately do not resolve people by their name.  New institutional
rosters belong in their own adapters once a stable official list is available.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureRole


PRESIDENT_EVIDENCE_URL = 'https://k.prezydent.pl/prezydent'
SENATE_PRESIDIUM_EVIDENCE_URL = 'https://www.senat.gov.pl/o-senacie/organy/prezydium-senatu/'

# (official Senate roster id, role suffix, visible title).  The ids come from
# the current Senate's official profile URLs and are reviewed with the roster,
# rather than being derived from a spelling of a name.
SENATE_PRESIDIUM = (
    ('1063', 'marshal', 'Marszałek Senatu'),
    ('1051', 'deputy-marshal-biejat', 'Wicemarszałkini Senatu'),
    ('1085', 'deputy-marshal-grupinski', 'Wicemarszałek Senatu'),
    ('1016', 'deputy-marshal-kaminski', 'Wicemarszałek Senatu'),
    ('1072', 'deputy-marshal-zywno', 'Wicemarszałek Senatu'),
)


class Command(BaseCommand):
    help = ('Synchronizuje Prezydenta RP i Prezydium Senatu z bezpośrednimi, oficjalnymi dowodami. '
            'Nie dopasowuje nazwisk, nie tworzy kont X ani nie pobiera danych rejestrowych.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        senate_profile_keys = [f'parliamentary:senat:{external_id}' for external_id, *_ in SENATE_PRESIDIUM]
        figures = {
            item.import_key: item
            for item in PublicFigure.objects.filter(import_key__in=senate_profile_keys, archived=False)
        }
        missing = sorted(set(senate_profile_keys) - set(figures))
        if missing:
            raise CommandError(
                'Brakuje profilu z dokładnego oficjalnego rosteru Senatu: '
                f"{', '.join(missing)}. Najpierw synchronizuj roster i profile Senatu."
            )

        president_key = 'state-office:president:current'
        role_keys = {f'state-office:senate-presidium:{suffix}' for _, suffix, _ in SENATE_PRESIDIUM}
        created_president = not PublicFigure.objects.filter(import_key=president_key).exists()
        existing_roles = set(PublicFigureRole.objects.filter(import_key__in=role_keys).values_list('import_key', flat=True))
        created_roles = len(role_keys - existing_roles)
        former_roles = PublicFigureRole.objects.filter(
            import_key__startswith='state-office:senate-presidium:', archived=False, status='current'
        ).exclude(import_key__in=role_keys).count()

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd najwyższych funkcji: Prezydent RP nowe {int(created_president)}; '
                f'role Prezydium Senatu nowe {created_roles}, do aktualizacji {len(role_keys) - created_roles}, '
                f'do oznaczenia jako byłe {former_roles}. Bez zapisu i bez działań w X.'
            ))
            return

        now = timezone.now()
        with transaction.atomic():
            PublicFigure.objects.update_or_create(
                import_key=president_key,
                defaults={
                    'canonical_name': 'Karol Nawrocki',
                    'role_category': 'political',
                    'role_title': 'Prezydent Rzeczypospolitej Polskiej',
                    'organisation': 'Kancelaria Prezydenta Rzeczypospolitej Polskiej',
                    'status': 'current',
                    'official_profile_url': PRESIDENT_EVIDENCE_URL,
                    'evidence_url': PRESIDENT_EVIDENCE_URL,
                    'evidence_note': 'Oficjalny profil Prezydenta Rzeczypospolitej Polskiej.',
                    'source_checked_at': now,
                    'parliamentary_roster_entry': None,
                    'archived': False,
                },
            )
            for external_id, suffix, title in SENATE_PRESIDIUM:
                PublicFigureRole.objects.update_or_create(
                    import_key=f'state-office:senate-presidium:{suffix}',
                    defaults={
                        'public_figure': figures[f'parliamentary:senat:{external_id}'],
                        'role_category': 'parliamentary',
                        'role_title': title,
                        'organisation': 'Senat Rzeczypospolitej Polskiej',
                        'status': 'current',
                        'official_profile_url': SENATE_PRESIDIUM_EVIDENCE_URL,
                        'evidence_url': SENATE_PRESIDIUM_EVIDENCE_URL,
                        'evidence_note': 'Aktualne Prezydium Senatu wskazane przez Senat RP.',
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
            PublicFigureRole.objects.filter(
                import_key__startswith='state-office:senate-presidium:', archived=False, status='current'
            ).exclude(import_key__in=role_keys).update(status='former', source_checked_at=now)

        self.stdout.write(self.style.SUCCESS(
            f'Zsynchronizowano Prezydenta RP oraz {len(SENATE_PRESIDIUM)} ról Prezydium Senatu; '
            f'nowy profil Prezydenta {int(created_president)}, nowe role {created_roles}, '
            f'oznaczone jako byłe role {former_roles}. Nie utworzono kont X ani kandydatur.'
        ))

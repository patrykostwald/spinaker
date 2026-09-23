"""Synchronise a small, explicitly evidenced set of highest state offices.

The parliamentary roles below point to a *known official Senate roster id*.
They deliberately do not resolve people by their name.  New institutional
rosters belong in their own adapters once a stable official list is available.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureRole


PRESIDENT_EVIDENCE_URL = 'https://k.prezydent.pl/prezydent'
SENATE_PRESIDIUM_EVIDENCE_URL = 'https://www.senat.gov.pl/o-senacie/organy/prezydium-senatu/'
SEJM_PRESIDIUM_EVIDENCE_URL = 'https://www.sejm.gov.pl/sejm10.nsf/page.xsp/prezydium_sejmu'

# (official Senate roster id, role suffix, visible title).  The ids come from
# the current Senate's official profile URLs and are reviewed with the roster,
# rather than being derived from a spelling of a name.
SENATE_PRESIDIUM = (
    ('1063', 'marshal', 'Marszałek Senatu'),
    ('1065', 'deputy-marshal-biejat', 'Wicemarszałkini Senatu'),
    ('1050', 'deputy-marshal-grupinski', 'Wicemarszałek Senatu'),
    ('984', 'deputy-marshal-kaminski', 'Wicemarszałek Senatu'),
    ('1072', 'deputy-marshal-zywno', 'Wicemarszałek Senatu'),
)

# (official Sejm API roster id, role suffix, visible title).  The source page
# below is the current official Presidium page; the identifiers are then bound
# to the exact Sejm roster keys, never to a runtime name match.
SEJM_PRESIDIUM = (
    ('58', 'marshal', 'Marszałek Sejmu'),
    ('33', 'deputy-marshal-bosak', 'Wicemarszałek Sejmu'),
    ('133', 'deputy-marshal-holownia', 'Wicemarszałek Sejmu'),
    ('134', 'deputy-marshal-horala', 'Wicemarszałek Sejmu'),
    ('258', 'deputy-marshal-niedziela', 'Wicemarszałkini Sejmu'),
    ('421', 'deputy-marshal-wielichowska', 'Wicemarszałkini Sejmu'),
    ('449', 'deputy-marshal-zgorzelski', 'Wicemarszałek Sejmu'),
)

# These are separate institutional offices, each backed by an official profile.
# The import key includes both the office and person so a future holder can be
# added while the previous public profile is retained as former.
CENTRAL_OFFICES = (
    (
        'rpd', 'monika-horna-cieslak', 'Monika Horna-Cieślak',
        'Rzeczniczka Praw Dziecka', 'Biuro Rzecznika Praw Dziecka',
        'https://brpd.gov.pl/o-rzeczniczce/',
    ),
    (
        'uodo', 'miroslaw-wroblewski', 'Mirosław Wróblewski',
        'Prezes Urzędu Ochrony Danych Osobowych', 'Urząd Ochrony Danych Osobowych',
        'https://uodo.gov.pl/pl/544/996',
    ),
)


class Command(BaseCommand):
    help = ('Synchronizuje Prezydenta RP, wybrane urzędy centralne oraz Prezydia Sejmu i Senatu z bezpośrednimi, oficjalnymi dowodami. '
            'Nie dopasowuje nazwisk, nie tworzy kont X ani nie pobiera danych rejestrowych.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        senate_profile_keys = [f'parliamentary:senat:{external_id}' for external_id, *_ in SENATE_PRESIDIUM]
        sejm_profile_keys = [f'parliamentary:sejm:{external_id}' for external_id, *_ in SEJM_PRESIDIUM]
        figures = {
            item.import_key: item
            for item in PublicFigure.objects.filter(import_key__in=[*senate_profile_keys, *sejm_profile_keys], archived=False)
        }
        missing = sorted(set([*senate_profile_keys, *sejm_profile_keys]) - set(figures))
        if missing:
            raise CommandError(
                'Brakuje profilu z dokładnego oficjalnego rosteru parlamentarnego: '
                f"{', '.join(missing)}. Najpierw synchronizuj odpowiedni roster i profile."
            )

        president_key = 'state-office:president:current'
        central_office_keys = {f'state-office:{office}:{person}' for office, person, *_ in CENTRAL_OFFICES}
        senate_role_keys = {f'state-office:senate-presidium:{suffix}' for _, suffix, _ in SENATE_PRESIDIUM}
        sejm_role_keys = {f'state-office:sejm-presidium:{suffix}' for _, suffix, _ in SEJM_PRESIDIUM}
        role_keys = senate_role_keys | sejm_role_keys
        created_president = not PublicFigure.objects.filter(import_key=president_key).exists()
        existing_central_offices = set(PublicFigure.objects.filter(import_key__in=central_office_keys).values_list('import_key', flat=True))
        created_central_offices = len(central_office_keys - existing_central_offices)
        existing_roles = set(PublicFigureRole.objects.filter(import_key__in=role_keys).values_list('import_key', flat=True))
        created_roles = len(role_keys - existing_roles)
        presidium_roles = PublicFigureRole.objects.filter(
            Q(import_key__startswith='state-office:senate-presidium:')
            | Q(import_key__startswith='state-office:sejm-presidium:'),
            archived=False, status='current',
        )
        former_roles = presidium_roles.exclude(import_key__in=role_keys).count()

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd najwyższych funkcji: Prezydent RP nowe {int(created_president)}; urzędy centralne nowe {created_central_offices}; '
                f'role Prezydiów Sejmu i Senatu nowe {created_roles}, do aktualizacji {len(role_keys) - created_roles}, '
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
            for office, person, name, title, organisation, evidence_url in CENTRAL_OFFICES:
                PublicFigure.objects.update_or_create(
                    import_key=f'state-office:{office}:{person}',
                    defaults={
                        'canonical_name': name,
                        'role_category': 'political',
                        'role_title': title,
                        'organisation': organisation,
                        'status': 'current',
                        'official_profile_url': evidence_url,
                        'evidence_url': evidence_url,
                        'evidence_note': f'Oficjalny profil osoby pełniącej urząd: {title}.',
                        'source_checked_at': now,
                        'parliamentary_roster_entry': None,
                        'archived': False,
                    },
                )
                PublicFigure.objects.filter(
                    import_key__startswith=f'state-office:{office}:', status='current', archived=False,
                ).exclude(import_key=f'state-office:{office}:{person}').update(
                    status='former', source_checked_at=now,
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
            for external_id, suffix, title in SEJM_PRESIDIUM:
                PublicFigureRole.objects.update_or_create(
                    import_key=f'state-office:sejm-presidium:{suffix}',
                    defaults={
                        'public_figure': figures[f'parliamentary:sejm:{external_id}'],
                        'role_category': 'parliamentary',
                        'role_title': title,
                        'organisation': 'Sejm Rzeczypospolitej Polskiej',
                        'status': 'current',
                        'official_profile_url': SEJM_PRESIDIUM_EVIDENCE_URL,
                        'evidence_url': SEJM_PRESIDIUM_EVIDENCE_URL,
                        'evidence_note': 'Aktualne Prezydium Sejmu wskazane przez Sejm RP.',
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
            presidium_roles.exclude(import_key__in=role_keys).update(status='former', source_checked_at=now)

        self.stdout.write(self.style.SUCCESS(
            f'Zsynchronizowano Prezydenta RP oraz {len(SEJM_PRESIDIUM)} ról Prezydium Sejmu i '
            f'{len(SENATE_PRESIDIUM)} ról Prezydium Senatu; '
            f'nowy profil Prezydenta {int(created_president)}, nowe profile urzędów centralnych {created_central_offices}, nowe role {created_roles}, '
            f'oznaczone jako byłe role {former_roles}. Nie utworzono kont X ani kandydatur.'
        ))

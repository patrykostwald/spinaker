"""Seed the current KPRP leadership from its single official roster page."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureRole, PublicOffice


EVIDENCE_URL = 'https://www.prezydent.pl/kancelaria/kierownictwo-kancelarii'
KPRP_LEADERSHIP = (
    ('chief-of-chancellery', 'Zbigniew Bogucki', 'Szef Kancelarii Prezydenta Rzeczypospolitej Polskiej'),
    ('deputy-chief', 'Adam Andruszkiewicz', 'Sekretarz Stanu – Zastępca Szefa Kancelarii Prezydenta RP'),
    ('chief-of-cabinet', 'Paweł Szefernaker', 'Sekretarz Stanu – Szef Gabinetu Prezydenta RP'),
    ('deputy-chief-of-cabinet', 'Jarosław Dębowski', 'Sekretarz Stanu – Zastępca Szefa Gabinetu Prezydenta RP'),
    ('head-bbn', 'Bartosz Grodecki', 'Sekretarz Stanu – Szef Biura Bezpieczeństwa Narodowego'),
    ('head-international-policy', 'Marcin Przydacz', 'Sekretarz Stanu – Szef Biura Polityki Międzynarodowej'),
    ('state-secretary-kolarski', 'Wojciech Kolarski', 'Sekretarz Stanu'),
    ('state-secretary-kotecki', 'Mateusz Kotecki', 'Sekretarz Stanu'),
    ('press-secretary', 'Rafał Leśkiewicz', 'Sekretarz Stanu – Rzecznik Prasowy Prezydenta RP'),
    ('undersecretary-jedrzak', 'Agnieszka Jędrzak', 'Podsekretarz Stanu'),
    ('undersecretary-rabenda', 'Karol Rabenda', 'Podsekretarz Stanu'),
    ('director-general', 'Magdalena Głowa', 'Dyrektor Generalny Kancelarii Prezydenta RP'),
)


class Command(BaseCommand):
    help = ('Synchronizuje kierownictwo KPRP z jednego oficjalnego wykazu. '
            'Nie dopasowuje nazwisk, nie tworzy kont X ani nie pobiera danych rejestrowych.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        prefix = 'kprp-leadership:'
        holder_keys = {f'{prefix}{key}:holder:{slugify(name)}' for key, name, _ in KPRP_LEADERSHIP}
        existing = set(PublicFigure.objects.filter(import_key__in=holder_keys).values_list('import_key', flat=True))
        created, updated = len(holder_keys - existing), len(holder_keys & existing)
        former = PublicFigure.objects.filter(import_key__startswith=prefix, archived=False, status='current').exclude(import_key__in=holder_keys).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd KPRP: {len(KPRP_LEADERSHIP)} wpisów; nowe {created}; do aktualizacji {updated}; '
                f'do oznaczenia jako byli {former}. Bez zapisu i bez działań w X.'
            ))
            return
        now = timezone.now()
        with transaction.atomic():
            for key, name, title in KPRP_LEADERSHIP:
                holder_key = f'{prefix}{key}:holder:{slugify(name)}'
                figure, _ = PublicFigure.objects.update_or_create(
                    import_key=holder_key,
                    defaults={
                        'canonical_name': name,
                        'role_category': 'government',
                        'role_title': title,
                        'organisation': 'Kancelaria Prezydenta Rzeczypospolitej Polskiej',
                        'status': 'current',
                        'official_profile_url': EVIDENCE_URL,
                        'evidence_url': EVIDENCE_URL,
                        'evidence_note': 'Aktualne kierownictwo KPRP wskazane na oficjalnej stronie Kancelarii.',
                        'source_checked_at': now,
                        'parliamentary_roster_entry': None,
                        'archived': False,
                    },
                )
                office, _ = PublicOffice.objects.update_or_create(
                    import_key=f'public-office:kprp:{key}',
                    defaults={
                        'title': title,
                        'role_category': 'government',
                        'organisation': 'Kancelaria Prezydenta Rzeczypospolitej Polskiej',
                        'official_roster_url': EVIDENCE_URL,
                        'evidence_note': 'Funkcja kierownicza KPRP wskazana na oficjalnej stronie Kancelarii.',
                        'current_holder': figure,
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
                PublicFigureRole.objects.update_or_create(
                    import_key=f'{prefix}{key}:role:{slugify(name)}',
                    defaults={
                        'public_figure': figure,
                        'public_office': office,
                        'role_category': 'government',
                        'role_title': title,
                        'organisation': 'Kancelaria Prezydenta Rzeczypospolitej Polskiej',
                        'status': 'current',
                        'official_profile_url': EVIDENCE_URL,
                        'evidence_url': EVIDENCE_URL,
                        'evidence_note': 'Aktualne kierownictwo KPRP wskazane na oficjalnej stronie Kancelarii.',
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
                PublicFigureRole.objects.filter(
                    public_office=office, status='current', archived=False,
                ).exclude(public_figure=figure).update(status='former', source_checked_at=now)
            PublicFigure.objects.filter(import_key__startswith=prefix, archived=False, status='current').exclude(import_key__in=holder_keys).update(
                status='former', source_checked_at=now)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(KPRP_LEADERSHIP)} osób z kierownictwa KPRP; nowe {created}; '
            f'zaktualizowane {updated}; oznaczone jako byli {former}. Nie utworzono kont X ani kandydatur.'
        ))

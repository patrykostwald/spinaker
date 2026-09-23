"""Seed the current voivodes from the MSWiA's single official roster page."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureRole, PublicOffice


EVIDENCE_URL = 'https://www.gov.pl/web/mswia/urzedy-wojewodzkie'
VOIVODES = (
    ('dolnoslaskie', 'Anna Żabska', 'Wojewoda Dolnośląski', 'Dolnośląski Urząd Wojewódzki we Wrocławiu'),
    ('kujawsko-pomorskie', 'Michał Sztybel', 'Wojewoda Kujawsko-Pomorski', 'Kujawsko-Pomorski Urząd Wojewódzki w Bydgoszczy'),
    ('lubelskie', 'Krzysztof Komorski', 'Wojewoda Lubelski', 'Lubelski Urząd Wojewódzki w Lublinie'),
    ('lubuskie', 'Marek Cebula', 'Wojewoda Lubuski', 'Lubuski Urząd Wojewódzki w Gorzowie Wielkopolskim'),
    ('lodzkie', 'Dorota Ryl', 'Wojewoda Łódzki', 'Łódzki Urząd Wojewódzki w Łodzi'),
    ('malopolskie', 'Krzysztof Jan Klęczar', 'Wojewoda Małopolski', 'Małopolski Urząd Wojewódzki w Krakowie'),
    ('mazowieckie', 'Mariusz Frankowski', 'Wojewoda Mazowiecki', 'Mazowiecki Urząd Wojewódzki w Warszawie'),
    ('opolskie', 'Monika Jurek', 'Wojewoda Opolski', 'Opolski Urząd Wojewódzki w Opolu'),
    ('podkarpackie', 'Teresa Kubas-Hul', 'Wojewoda Podkarpacki', 'Podkarpacki Urząd Wojewódzki w Rzeszowie'),
    ('podlaskie', 'Jacek Brzozowski', 'Wojewoda Podlaski', 'Podlaski Urząd Wojewódzki w Białymstoku'),
    ('pomorskie', 'Beata Rutkiewicz', 'Wojewoda Pomorski', 'Pomorski Urząd Wojewódzki w Gdańsku'),
    ('slaskie', 'Marek Wójcik', 'Wojewoda Śląski', 'Śląski Urząd Wojewódzki w Katowicach'),
    ('swietokrzyskie', 'Józef Bryk', 'Wojewoda Świętokrzyski', 'Świętokrzyski Urząd Wojewódzki w Kielcach'),
    ('warminsko-mazurskie', 'Radosław Król', 'Wojewoda Warmińsko-Mazurski', 'Warmińsko-Mazurski Urząd Wojewódzki w Olsztynie'),
    ('wielkopolskie', 'Agata Sobczyk', 'Wojewoda Wielkopolski', 'Wielkopolski Urząd Wojewódzki w Poznaniu'),
    ('zachodniopomorskie', 'Adam Rudawski', 'Wojewoda Zachodniopomorski', 'Zachodniopomorski Urząd Wojewódzki w Szczecinie'),
)


class Command(BaseCommand):
    help = ('Synchronizuje listę wojewodów z jednego oficjalnego rosteru MSWiA. '
            'Nie dopasowuje nazwisk, nie tworzy kont X i nie pobiera danych rejestrowych.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        keys = {f'government:voivode:{region}' for region, *_ in VOIVODES}
        existing = set(PublicFigure.objects.filter(import_key__in=keys).values_list('import_key', flat=True))
        created = len(keys - existing)
        updated = len(keys & existing)
        former = PublicFigure.objects.filter(import_key__startswith='government:voivode:',
            archived=False, status='current').exclude(import_key__in=keys).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd wojewodów: {len(VOIVODES)} wpisów; nowe {created}; do aktualizacji {updated}; '
                f'do oznaczenia jako byli {former}. Bez zapisu i bez działań w X.'
            ))
            return
        now = timezone.now()
        with transaction.atomic():
            for region, name, title, office in VOIVODES:
                figure, _ = PublicFigure.objects.update_or_create(
                    import_key=f'government:voivode:{region}',
                    defaults={
                        'canonical_name': name,
                        'role_category': 'government',
                        'role_title': title,
                        'organisation': office,
                        'status': 'current',
                        'official_profile_url': '',
                        'evidence_url': EVIDENCE_URL,
                        'evidence_note': 'Oficjalna lista urzędów wojewódzkich MSWiA.',
                        'source_checked_at': now,
                        'parliamentary_roster_entry': None,
                        'archived': False,
                    },
                )
                public_office, _ = PublicOffice.objects.update_or_create(
                    import_key=f'public-office:voivode:{region}',
                    defaults={
                        'title': title,
                        'role_category': 'government',
                        'organisation': office,
                        'official_roster_url': EVIDENCE_URL,
                        'evidence_note': 'Oficjalna lista urzędów wojewódzkich MSWiA.',
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
                    import_key=f'public-office:voivode:{region}:holder:{figure.import_key}',
                    defaults={
                        'public_figure': figure,
                        'public_office': public_office,
                        'role_category': 'government',
                        'role_title': title,
                        'organisation': office,
                        'status': 'current',
                        'official_profile_url': '',
                        'evidence_url': EVIDENCE_URL,
                        'evidence_note': 'Oficjalna lista urzędów wojewódzkich MSWiA.',
                        'source_checked_at': now,
                        'archived': False,
                    },
                )
            PublicFigure.objects.filter(import_key__startswith='government:voivode:',
                archived=False, status='current').exclude(import_key__in=keys).update(
                    status='former', source_checked_at=now)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(VOIVODES)} wojewodów; nowe {created}; zaktualizowane {updated}; '
            f'oznaczone jako byli {former}. Nie utworzono kont X ani kandydatur.'
        ))

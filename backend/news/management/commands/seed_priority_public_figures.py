"""Seed a small, evidence-only priority list for the public-figure register."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.political_models import ParliamentaryRosterEntry, PublicFigure


ROWS = (
    {
        'import_key': 'editorial-priority:mateusz-morawiecki',
        'canonical_name': 'Mateusz Morawiecki',
        'role_category': 'parliamentary',
        'role_title': 'Poseł na Sejm RP; przewodniczący klubu/koła',
        'organisation': 'Klub Parlamentarny Rozwój Plus',
        'official_profile_url': 'https://orka.sejm.gov.pl/Home.nsf/posel.xsp?SessionID=DKFQWBIOQO&id=246&type=P',
        'evidence_url': 'https://orka.sejm.gov.pl/Home.nsf/posel.xsp?SessionID=DKFQWBIOQO&id=246&type=P',
        'evidence_note': 'Aktualny profil poselski Sejmu RP wskazuje mandat i funkcję w klubie/kole.',
        'roster_source': 'sejm',
        'roster_name': 'Mateusz Morawiecki',
    },
    {
        'canonical_name': 'Paulina Hennig-Kloska',
        'link_existing_only': True,
        'roster_source': 'sejm',
        'roster_name': 'Paulina Hennig-Kloska',
    },
    {
        'import_key': 'editorial-priority:grzegorz-braun',
        'canonical_name': 'Grzegorz Braun',
        'role_category': 'european',
        'role_title': 'Poseł do Parlamentu Europejskiego',
        'organisation': 'Konfederacja Korony Polskiej',
        'official_profile_url': 'https://www.europarl.europa.eu/meps/pl/257067/GRZEGORZ_BRAUN/home',
        'evidence_url': 'https://www.europarl.europa.eu/meps/pl/257067/GRZEGORZ_BRAUN/home',
        'evidence_note': 'Oficjalny profil Parlamentu Europejskiego.',
        'roster_source': 'ep',
        'roster_name': 'Grzegorz Braun',
    },
    {
        'import_key': 'editorial-priority:janusz-korwin-mikke',
        'canonical_name': 'Janusz Korwin-Mikke',
        'role_category': 'political',
        'role_title': 'Prezes Partii KORWiN',
        'organisation': 'Partia KORWiN',
        'official_profile_url': 'https://korwin.com.pl/korwin/',
        'evidence_url': 'https://korwin.com.pl/wladze/',
        'evidence_note': 'Oficjalna strona władz Partii KORWiN.',
    },
    {
        'import_key': 'editorial-priority:jaroslaw-kaczynski',
        'canonical_name': 'Jarosław Kaczyński',
        'role_category': 'party',
        'role_title': 'Prezes partii',
        'organisation': 'Prawo i Sprawiedliwość',
        'official_profile_url': 'https://pis.org.pl/partia/wladze-ludzie/',
        'evidence_url': 'https://pis.org.pl/partia/wladze-ludzie/',
        'evidence_note': 'Oficjalna strona władz Prawa i Sprawiedliwości.',
    },
)


class Command(BaseCommand):
    help = 'Dodaje krótką, udokumentowaną listę priorytetowych osób publicznych; nie tworzy kont X ani kandydatur.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        import_keys = [row['import_key'] for row in ROWS if row.get('import_key')]
        existing_keys = set(PublicFigure.objects.filter(import_key__in=import_keys).values_list('import_key', flat=True))
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd listy priorytetowej: {len(ROWS)} wpisów; nowe {len(import_keys) - len(existing_keys)}; '
                f'do aktualizacji {len(existing_keys)}. Bez zapisu i bez działań w X.'
            ))
            return

        created = updated = linked = 0
        with transaction.atomic():
            for row in ROWS:
                if row.get('link_existing_only'):
                    figure = PublicFigure.objects.filter(canonical_name__iexact=row['canonical_name'], archived=False).first()
                    if not figure:
                        self.stdout.write(self.style.WARNING(
                            f'Pominięto połączenie z rosterem: nie ma aktywnego wpisu osoby {row["canonical_name"]}.'
                        ))
                        continue
                    was_created = False
                else:
                    values = {key: value for key, value in row.items() if key not in {
                        'roster_source', 'roster_name', 'link_existing_only'
                    }}
                    values.update(status='current', source_checked_at=now, archived=False)
                    figure, was_created = PublicFigure.objects.update_or_create(import_key=row['import_key'], defaults=values)
                created += int(was_created)
                updated += int(not was_created)
                if row.get('roster_source'):
                    roster = ParliamentaryRosterEntry.objects.filter(
                        source=row['roster_source'], active=True, full_name__iexact=row['roster_name'],
                    ).first()
                    if roster and figure.parliamentary_roster_entry_id != roster.pk:
                        figure.parliamentary_roster_entry = roster
                        figure.save(update_fields=['parliamentary_roster_entry', 'updated_at'])
                        linked += 1
        self.stdout.write(self.style.SUCCESS(
            f'Dodano {created} osób, zaktualizowano {updated}, ręcznie potwierdzono {linked} połączeń z rosterem. '
            'Nie utworzono kont X ani kandydatur.'
        ))

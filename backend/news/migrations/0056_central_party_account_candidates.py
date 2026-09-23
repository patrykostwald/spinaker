"""Seed editorial leads for central Polish party accounts.

This migration deliberately creates *candidates* only.  It never resolves a
handle with X, creates a PoliticalAccount, confirms an identity, or enables
polling.  A staff editor must review and resolve each lead explicitly.
"""
from django.db import migrations


CENTRAL_PARTY_CANDIDATES = (
    {
        'handle': 'Platforma_org',
        'display_name': 'Platforma Obywatelska',
        'classification': 'opposition',
        'proposed_camp': 'opposition',
        'confirmation_url': 'https://platforma.org/aktualnosci/wiec-donalda-tuska',
        'confirmation_note': 'Materiał opublikowany w oficjalnym serwisie Platformy Obywatelskiej.',
    },
    {
        'handle': 'pisorgpl',
        'display_name': 'Prawo i Sprawiedliwość',
        'classification': 'opposition',
        'proposed_camp': 'opposition',
        'confirmation_url': 'https://bip.pis.org.pl/',
        'confirmation_note': 'Oficjalny Biuletyn Informacji Publicznej Prawa i Sprawiedliwości.',
    },
    {
        'handle': 'nowePSL',
        'display_name': 'Polskie Stronnictwo Ludowe',
        'classification': 'government',
        'proposed_camp': 'government',
        'confirmation_url': 'https://x.com/nowePSL/with_replies',
        'confirmation_note': 'Kandydatura wymaga dodatkowego potwierdzenia w oficjalnym serwisie PSL przed rozstrzygnięciem w X.',
    },
    {
        'handle': 'PL_2050',
        'display_name': 'Polska 2050',
        'classification': 'government',
        'proposed_camp': 'government',
        'confirmation_url': 'https://stowarzyszenie2050.pl/wp-content/uploads/2021/09/Zagranica_Final.pdf',
        'confirmation_note': 'Materiał opublikowany przez Stowarzyszenie Polska 2050; sprawdź aktualne wskazanie konta przed rozstrzygnięciem.',
    },
    {
        'handle': '__Lewica',
        'display_name': 'Lewica',
        'classification': 'government',
        'proposed_camp': 'government',
        'confirmation_url': 'https://bip.lewica.org.pl/',
        'confirmation_note': 'Oficjalny Biuletyn Informacji Publicznej Lewicy.',
    },
    {
        'handle': 'KoronyPolskiej',
        'display_name': 'Konfederacja Korony Polskiej',
        'classification': 'opposition',
        'proposed_camp': 'opposition',
        'confirmation_url': 'https://konfederacjakoronypolskiej.pl/wp-content/uploads/2026/03/Statut-KKP-2025-rok.pdf',
        'confirmation_note': 'Statut opublikowany przez Konfederację Korony Polskiej; sprawdź aktualne wskazanie konta przed rozstrzygnięciem.',
    },
)


def seed_central_party_candidates(apps, schema_editor):
    Candidate = apps.get_model('news', 'PoliticalAccountCandidate')
    for values in CENTRAL_PARTY_CANDIDATES:
        # Preserve any prior editorial changes or resolution rather than
        # replacing a candidate merely because a migration is re-run.
        Candidate.objects.get_or_create(handle=values['handle'], defaults=values)


class Migration(migrations.Migration):
    dependencies = [('news', '0055_parliamentary_roster_entry')]

    operations = [migrations.RunPython(seed_central_party_candidates, migrations.RunPython.noop)]

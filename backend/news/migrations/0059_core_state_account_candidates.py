"""Stage core state accounts with official provenance for editorial review.

This migration deliberately creates candidates only.  A staff editor must
resolve each lead before an account can be polled; resolution never enables
polling.  The links below explicitly identify the corresponding account on an
official public page.
"""
from django.db import migrations


CORE_STATE_CANDIDATES = (
    {
        "handle": "PremierRP",
        "display_name": "Kancelaria Prezesa Rady Ministrów",
        "classification": "public",
        "proposed_camp": "public",
        "confirmation_url": "https://www.gov.pl/attachment/a00b5794-e36f-429f-af98-1c0ecdce192e",
        "confirmation_note": "Oficjalny materiał KPRM wskazuje konto PremierRP.",
    },
    {
        "handle": "prezydentpl",
        "display_name": "Kancelaria Prezydenta RP",
        "classification": "public",
        "proposed_camp": "public",
        "confirmation_url": "https://www.prezydent.pl/kancelaria/aktywnosc-ministrow/posiedzenie-rady-ds-energii-i-zasobow-naturalnych%2C116164",
        "confirmation_note": "Oficjalny serwis Prezydenta RP cytuje konto Kancelarii Prezydenta RP @prezydentpl.",
    },
    {
        "handle": "NawrockiKn",
        "display_name": "Karol Nawrocki",
        "classification": "public",
        "proposed_camp": "public",
        "confirmation_url": "https://www.prezydent.pl/aktualnosci/wizyty-krajowe/wielun-obchody-86-rocznicy-wybuchu-ii-wojny-swiatowej%2C106146",
        "confirmation_note": "Oficjalny serwis Prezydenta RP wskazuje konto Prezydenta @NawrockiKn.",
    },
)


def seed_core_state_candidates(apps, schema_editor):
    Candidate = apps.get_model("news", "PoliticalAccountCandidate")
    for values in CORE_STATE_CANDIDATES:
        Candidate.objects.get_or_create(handle=values["handle"], defaults=values)


class Migration(migrations.Migration):
    dependencies = [("news", "0058_public_figure")]

    operations = [migrations.RunPython(seed_core_state_candidates, migrations.RunPython.noop)]

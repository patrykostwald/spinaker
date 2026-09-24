"""Stage a small, review-only first batch of senior cabinet accounts.

The KPRM page proves current offices.  It does not replace the editor's final
identity check of the X profile before resolving a candidate.
"""
from django.db import migrations


SENIOR_CABINET_CANDIDATES = (
    {
        "handle": "sikorskiradek",
        "display_name": "Radosław Sikorski",
        "classification": "government",
        "proposed_camp": "government",
        "confirmation_url": "https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2",
        "confirmation_note": "Aktualny wiceprezes Rady Ministrów i minister spraw zagranicznych w wykazie KPRM. Przed rozstrzygnięciem sprawdź nazwę na profilu X.",
    },
    {
        "handle": "KosiniakKamysz",
        "display_name": "Władysław Kosiniak-Kamysz",
        "classification": "government",
        "proposed_camp": "government",
        "confirmation_url": "https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2",
        "confirmation_note": "Aktualny wiceprezes Rady Ministrów i minister obrony narodowej w wykazie KPRM. Przed rozstrzygnięciem sprawdź nazwę na profilu X.",
    },
    {
        "handle": "KGawkowski",
        "display_name": "Krzysztof Gawkowski",
        "classification": "government",
        "proposed_camp": "government",
        "confirmation_url": "https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2",
        "confirmation_note": "Aktualny wiceprezes Rady Ministrów i minister cyfryzacji w wykazie KPRM. Przed rozstrzygnięciem sprawdź nazwę na profilu X.",
    },
)


def seed_senior_cabinet_candidates(apps, schema_editor):
    Candidate = apps.get_model("news", "PoliticalAccountCandidate")
    for values in SENIOR_CABINET_CANDIDATES:
        Candidate.objects.get_or_create(handle=values["handle"], defaults=values)


class Migration(migrations.Migration):
    dependencies = [("news", "0060_align_social_evidence_metadata")]

    operations = [migrations.RunPython(seed_senior_cabinet_candidates, migrations.RunPython.noop)]

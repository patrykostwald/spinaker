from django.db import migrations


PUBLIC_CONFIRMATIONS = {
    # Official Sejm contact page; it is retained as a public provenance link for this lead.
    'KancelariaSejmu': ('https://www.sejm.gov.pl/Sejm10.nsf/page.xsp/kontakt', 'Oficjalna strona kontaktowa Kancelarii Sejmu.'),
    'PolskiSenat': ('https://www.senat.gov.pl/gfx/senat/userfiles/_public/k11/dokumenty/diariusz/034.pdf', 'Materiał opublikowany przez Senat RP.'),
    'MSZ_RP': ('https://www.gov.pl/web/dyplomacja/media-spolecznosciowe-i-zdjecia', 'Oficjalna strona MSZ o mediach społecznościowych.'),
    'MON_GOV_PL': ('https://www.gov.pl/attachment/bea382c8-fec1-41b7-a9f2-7e9b12af766f', 'Materiał opublikowany w serwisie gov.pl przez MON.'),
    'MSWiA_GOV_PL': ('https://www.gov.pl/attachment/057da8d9-f326-48d6-aad7-f6f61b846f07', 'Materiał opublikowany w serwisie gov.pl przez MSWiA.'),
    'RCB_RP': ('https://www.gov.pl/web/mswia/ministerstwo-spraw-wewnetrznych-i-administracji-wlacza-sie-w-walke-z-dezinformacja', 'Oficjalny materiał gov.pl dotyczący RCB.'),
    'MZ_GOV_PL': ('https://www.gov.pl/attachment/972783f3-fc68-43bf-b749-7757034254b6', 'Materiał opublikowany w serwisie gov.pl przez Ministerstwo Zdrowia.'),
    'MRiRW_GOV_PL': ('https://www.gov.pl/attachment/ada8a743-a183-4b62-a7eb-0248b8f63fe9', 'Materiał opublikowany w serwisie gov.pl przez MRiRW.'),
    'ME_GOV_PL': ('https://www.gov.pl/web/energia/dla-mediow', 'Oficjalna strona Ministerstwa Energii dla mediów.'),
}


def add_confirmation_sources(apps, schema_editor):
    Candidate = apps.get_model('news', 'PoliticalAccountCandidate')
    for handle, (url, note) in PUBLIC_CONFIRMATIONS.items():
        Candidate.objects.filter(handle=handle, classification='public').update(
            confirmation_url=url, confirmation_note=note, proposed_camp='public')


class Migration(migrations.Migration):
    dependencies = [('news', '0053_political_public_accounts')]

    operations = [migrations.RunPython(add_confirmation_sources, migrations.RunPython.noop)]

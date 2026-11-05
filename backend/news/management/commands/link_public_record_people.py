import json

from django.core.management.base import BaseCommand

from news.public_record_people import link_people


class Command(BaseCommand):
    help = 'Dopina dokumenty Sejmu (interpelacje, zapytania, wystąpienia) do osób po oficjalnym id posła. Bez sieci, idempotentne.'

    def handle(self, *args, **options):
        result = link_people()
        self.stdout.write(json.dumps(result, ensure_ascii=False))
        why = result['why_unlinked']
        self.stdout.write(f"unlinked = wiersze nadal bez osoby (stan, nie odpięte teraz). Pary bez osoby: "
                          f"{why['not_in_roster']} spoza listy mandatów (np. wygasły mandat), "
                          f"{why['roster_without_profile']} z mandatem bez profilu, {why['ambiguous']} niejednoznacznych.")

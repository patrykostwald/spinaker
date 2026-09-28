from collections import Counter

from django.core.management.base import BaseCommand

from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.techniques import CANONICAL_TECHNIQUES, categorize_techniques


class Command(BaseCommand):
    help = 'Uzupełnia kategorie technik regułami słownika, bez wywołań AI.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        counts, other = Counter(), Counter()
        changed = 0

        def categorize(items):
            result = categorize_techniques(items)
            for item in result:
                if isinstance(item, dict):
                    counts[item['category']] += 1
                    if item['category'] == 'Inne':
                        other[str(item.get('name', ''))] += 1
            return result

        for model, fields in (
            (SpinDiagnosis, (('techniques', None),)),
            (ClinicInterview, (('guest_analysis', 'techniques'), ('host_analysis', 'notes'))),
        ):
            for row in model.objects.only('pk', *(field for field, _ in fields)).order_by('pk').iterator():
                updates = {}
                for field, key in fields:
                    original = getattr(row, field)
                    if key is None:
                        value = categorize(original) if isinstance(original, list) else original
                    elif isinstance(original, dict) and isinstance(original.get(key), list):
                        value = {**original, key: categorize(original[key])}
                    else:
                        continue
                    if value != original:
                        updates[field] = value
                if updates:
                    changed += 1
                    if not options['dry_run']:
                        # Warunek chroni przed nadpisaniem równoległej zmiany diagnozy.
                        model.objects.filter(pk=row.pk, **{field: getattr(row, field) for field in updates}).update(**updates)

        self.stdout.write(f"{'DRY RUN — bez zapisu' if options['dry_run'] else 'Zapis'}: {changed} diagnoz")
        self.stdout.write('Rozkład kategorii (liczba technik):')
        for category in CANONICAL_TECHNIQUES:
            self.stdout.write(f'{category}: {counts[category]}')
        self.stdout.write('Nazwy w kategorii Inne:')
        for name, count in sorted(other.items()):
            self.stdout.write(f'{name!r}: {count}')

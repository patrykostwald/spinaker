"""Lista wszystkich kont X, które śledzimy (politycy i partie + konta źródeł) — CSV do obserwowania z @spinclinic.

  python manage.py x_accounts_export > konta_x.csv
"""
import csv
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Eksport kont X (polityczne + źródła) do CSV na standardowe wyjście.'

    def handle(self, *args, **options):
        from news.models import Source
        from news.political_models import PoliticalAccount
        writer = csv.writer(sys.stdout)
        writer.writerow(['handle', 'link', 'nazwa', 'rodzaj', 'obóz / typ', 'aktywne'])
        seen = set()
        for account in PoliticalAccount.objects.order_by('camp', 'display_name'):
            seen.add(account.handle.lower())
            writer.writerow([f'@{account.handle}', f'https://x.com/{account.handle}', account.display_name,
                             'polityk/partia', account.get_camp_display(), 'tak' if account.enabled else 'nie'])
        for source in Source.objects.exclude(x_handle='').order_by('name'):
            if source.x_handle.lower() in seen:
                continue
            seen.add(source.x_handle.lower())
            writer.writerow([f'@{source.x_handle}', f'https://x.com/{source.x_handle}', source.name,
                             'źródło', source.get_source_type_display(), 'tak' if source.is_active else 'nie'])
        self.stderr.write(f'Kont: {len(seen)}')

"""Ile osób zapisało się na powiadomienie o starcie (potwierdzeni, czekający, wypisani)."""
from django.core.management.base import BaseCommand

from news.newsletter import stats


class Command(BaseCommand):
    help = 'Liczba zapisów na newsletter.'

    def handle(self, *args, **options):
        data = stats()
        self.stdout.write(f"potwierdzeni: {data['confirmed']} · czekają na potwierdzenie: {data['pending']} · "
                          f"wypisani: {data['unsubscribed']} · nowi potwierdzeni (7 dni): {data['confirmed_last_7_days']}")
        for row in data['daily']:
            self.stdout.write(f"  {row['day']}: +{row['confirmed']}")
        if not data['smtp_ready']:
            self.stdout.write('UWAGA: SMTP nie jest skonfigurowany — maile potwierdzające nie wychodzą.')

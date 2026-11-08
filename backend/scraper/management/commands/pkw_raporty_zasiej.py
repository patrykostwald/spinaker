"""Zasiewa kolejkę zbieracza PKW zadaniami odczytu PDF-ów już znanych dokumentów (jednorazowo po wdrożeniu odczytu uchwał, 6.11.2026).

Dodaje tylko zadania `pkw_pdf` (idempotentnie, ta sama tożsamość = jedno zadanie); samo pobieranie robi zbieracz PKW z jego limitami
i kartą dostępu (domyślnie 40 żądań na dobę: `PUBLIC_RECORDS_PKW_DAILY_CAP` zwiększa limit w granicach karty)."""
from django.core.management.base import BaseCommand

from news.public_records_models import PublicCollectionState, PublicRecord
from scraper.public_records import enqueue


class Command(BaseCommand):
    help = 'Dodaje zadania odczytu PDF-ów do kolejki zbieracza PKW (bez pobierania).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='bez tej flagi tylko liczy')
        parser.add_argument('--ponownie', action='store_true',
                            help='Ponów odczyt uchwał już odczytanych, ale bez żadnej kwoty (po poprawce wzorców parsera).')

    def handle(self, *args, apply=False, ponownie=False, **options):
        if ponownie:
            return self.requeue(apply)
        urls = [u for u in PublicRecord.objects.filter(source='pkw', kind='financial_document').values_list('source_url', flat=True)
                if u.lower().endswith('.pdf') and '/uploaded_files/' in u]
        done = set(PublicRecord.objects.filter(source='pkw', kind='financial_report').values_list('source_url', flat=True))
        todo = [u for u in urls if u not in done]
        self.stdout.write(f'PDF-ów w spisie: {len(urls)}, już odczytanych: {len(urls) - len(todo)}, do odczytu: {len(todo)}')
        if not apply:
            self.stdout.write('PLAN: bez --apply nie dodaję zadań.')
            return
        state, _ = PublicCollectionState.objects.get_or_create(source='pkw')
        for url in todo:
            enqueue(state, url, 'pkw_pdf')
        self.stdout.write(self.style.SUCCESS(f'DODANO zadania: {len(todo)}'))

    def requeue(self, apply):
        """Uchwały odczytane, ale bez kwot: wznawia ich zadania (po poprawce wzorców), bez zmiany innych rekordów."""
        from hashlib import sha256
        from news.public_records_models import PublicCollectionJob
        urls = [u for u, d in PublicRecord.objects.filter(source='pkw', kind='financial_report').values_list('source_url', 'data')
                if d.get('readable') and not d.get('amounts')]
        self.stdout.write(f'Odczytanych uchwał bez kwot do ponowienia: {len(urls)}')
        if not apply:
            self.stdout.write('PLAN: bez --apply niczego nie zmieniam.')
            return
        state, _ = PublicCollectionState.objects.get_or_create(source='pkw')
        for url in urls:
            identity = sha256(('pkw_pdf\n' + url).encode()).hexdigest()
            if not PublicCollectionJob.objects.filter(state=state, identity=identity).update(done=False, failures=0, retry_at=None, last_error=''):
                enqueue(state, url, 'pkw_pdf')
        self.stdout.write(self.style.SUCCESS(f'WZNOWIONO zadania: {len(urls)}'))

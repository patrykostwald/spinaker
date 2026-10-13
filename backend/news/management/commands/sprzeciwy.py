"""Sprzeciwy (art. 21 RODO) wobec profili przeszłość.today - kolejka personelu (news/privacy_notice.py).

python manage.py sprzeciwy lista [--status potwierdzony]
python manage.py sprzeciwy rozpatrz <id> --decyzja uwzgledniony|odrzucony --uwaga "uzasadnienie" --kto <login>
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sprzeciwy wobec przetwarzania danych w profilach (kolejka personelu, bez automatycznego usuwania).'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        listing = sub.add_parser('lista')
        listing.add_argument('--status', default='')
        decide = sub.add_parser('rozpatrz')
        decide.add_argument('id', type=int)
        decide.add_argument('--decyzja', required=True, choices=['uwzgledniony', 'odrzucony'])
        decide.add_argument('--uwaga', required=True)
        decide.add_argument('--kto', required=True)
        clean = sub.add_parser('czysc', help='Retencja: usuń adres i token po okresie od decyzji (POSITION_PAIR_CONTACT_RETENTION_DAYS).')
        clean.add_argument('--dni', type=int, default=None)

    def handle(self, *args, **opts):
        from news import privacy_notice
        from news.clinic_models import DataObjection
        if opts['action'] == 'lista':
            rows = DataObjection.objects.select_related('figure')
            if opts['status']:
                rows = rows.filter(status=opts['status'])
            for r in rows.order_by('created_at'):
                self.stdout.write(f'{r.pk}\t{r.created_at:%Y-%m-%d}\t{r.status}\t{r.relation}\t{r.figure.canonical_name if r.figure else "(brak profilu: " + r.ident + ")"}\t{r.reason[:80]}')
            return
        if opts['action'] == 'czysc':
            from news.position_pairs import clean_contacts
            self.stdout.write(f'wyczyszczono: {clean_contacts(opts["dni"])}')
            return
        user = get_user_model().objects.filter(username=opts['kto'], is_staff=True).first()
        if user is None:
            raise CommandError('Decyzję podejmuje członek personelu (is_staff).')
        row = DataObjection.objects.filter(pk=opts['id']).first()
        if row is None:
            raise CommandError('Nie ma takiego sprzeciwu.')
        try:
            privacy_notice.decide(row, user, opts['decyzja'], opts['uwaga'])
        except ValueError as error:
            raise CommandError(f'Błąd: {error}') from None
        self.stdout.write(f'{row.pk}: {row.status}')

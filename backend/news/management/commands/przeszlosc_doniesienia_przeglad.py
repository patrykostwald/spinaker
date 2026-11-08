"""Przegląd kolejki doniesień medialnych z terminala (bez panelu administracyjnego).

  python manage.py przeszlosc_doniesienia_przeglad                    # lista oczekujących (numer, osoba, podmiot, KRS, link, cytat)
  python manage.py przeszlosc_doniesienia_przeglad --odrzuc 227 225   # odrzuca wskazane numery
  python manage.py przeszlosc_doniesienia_przeglad --publikuj 226     # publikuje wskazane numery (PO sprawdzeniu linku przez człowieka)
  python manage.py przeszlosc_doniesienia_przeglad --uzupelnij-daty   # dopisuje brakujące daty artykułów z metadanych stron (robots.txt/TDM respektowane)
Publikacja i odrzucenie są zapisane z użytkownikiem zespołu (domyślnie pierwszy aktywny superużytkownik, albo --uzytkownik nazwa).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.political_models import PublicFigureMediaMention


class Command(BaseCommand):
    help = 'Lista, odrzucanie i publikacja doniesień medialnych z kolejki przeglądu.'

    def add_arguments(self, parser):
        parser.add_argument('--odrzuc', type=int, nargs='*', default=[])
        parser.add_argument('--publikuj', type=int, nargs='*', default=[])
        parser.add_argument('--uzytkownik')
        parser.add_argument('--uzupelnij-daty', action='store_true')
        parser.add_argument('--wszystkie', action='store_true', help='Na liście także opublikowane i odrzucone (ostatnie 50).')

    def _staff(self, name):
        users = get_user_model().objects.filter(is_active=True, is_staff=True)
        user = users.filter(username=name).first() if name else users.filter(is_superuser=True).order_by('pk').first()
        if user is None:
            raise CommandError('Nie znaleziono aktywnego użytkownika zespołu (podaj --uzytkownik).')
        return user

    def handle(self, *args, **o):
        if o['uzupelnij_daty']:
            from news.doniesienia_badacz import page_date
            filled = 0
            for m in PublicFigureMediaMention.objects.filter(published_on__isnull=True).exclude(status='rejected'):
                found = page_date(m.source_url)
                if found:
                    PublicFigureMediaMention.objects.filter(pk=m.pk).update(published_on=found)
                    filled += 1
                    self.stdout.write(f'#{m.pk}: data {found.isoformat()}')
            self.stdout.write(f'Uzupełniono dat: {filled}')
            return
        if o['odrzuc'] or o['publikuj']:
            staff = self._staff(o['uzytkownik'])
            queue = PublicFigureMediaMention.objects.select_related('public_figure', 'organisation')
            for pk in o['odrzuc']:
                m = queue.filter(pk=pk).first()
                if m is None:
                    self.stdout.write(f'#{pk}: nie ma takiej pozycji')
                    continue
                m.status, m.reviewed_by, m.reviewed_at = 'rejected', staff, timezone.now()
                m.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
                self.stdout.write(f'#{pk}: ODRZUCONO ({m.public_figure.canonical_name} / {m.display_name})')
            for pk in o['publikuj']:
                m = queue.filter(pk=pk).first()
                if m is None:
                    self.stdout.write(f'#{pk}: nie ma takiej pozycji')
                    continue
                try:
                    m.publish(staff)
                except ValidationError as error:
                    self.stdout.write(f'#{pk}: NIE opublikowano: {"; ".join(error.messages)}')
                    continue
                self.stdout.write(f'#{pk}: OPUBLIKOWANO ({m.public_figure.canonical_name} / {m.display_name})')
            return
        rows = PublicFigureMediaMention.objects.select_related('public_figure', 'organisation').order_by('-pk')
        rows = rows[:50] if o['wszystkie'] else rows.filter(status='pending_review')[:50]
        for m in rows:
            ident = ('KRS ' + m.organisation.krs_number) if m.organisation_id else ('bez KRS: ' + (m.entity_identifier or 'brak identyfikatora'))
            self.stdout.write(f'#{m.pk} [{m.status}] {m.public_figure.canonical_name} | {m.display_name} ({ident}) | '
                              f'{m.get_category_display()}{" | niepotwierdzone" if m.match_basis == "name_only" else ""} | {m.source_outlet} {m.published_on or ""}\n'
                              f'    {m.source_url}\n    „{m.quote[:250]}”')

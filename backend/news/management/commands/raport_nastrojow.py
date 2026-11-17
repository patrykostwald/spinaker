"""Raport nastrojów: udział pozytywnych i negatywnych opinii o temacie z legalnych źródeł (X, YouTube, Wykop, RSS, tytuły mediów)."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from news import nastroje


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CommandError(f'Zła data: {value} (RRRR-MM-DD)')


class Command(BaseCommand):
    help = ('Jednorazowy raport nastrojów o temacie: X (oficjalne API, 7 dni), YouTube (komentarze), Wykop (po kluczu), RSS forów '
            'i blogów, tytuły z bazy; HTML i CSV w katalogu raportów. Nic nie zapisuje do tabel.')

    def add_arguments(self, parser):
        parser.add_argument('--fraza', action='append', default=[], help='Fraza do wyszukania (można podać kilka).')
        parser.add_argument('--dni', type=int, default=7, help='Okno X w dniach, gdy brak --od (najwyżej 7).')
        parser.add_argument('--od', default='', help='Początek zakresu RRRR-MM-DD (czas polski; X sięga 7 dni wstecz).')
        parser.add_argument('--do', default='', help='Koniec zakresu RRRR-MM-DD włącznie (domyślnie dziś).')
        parser.add_argument('--limit', type=int, default=500, help='Najwyżej tyle wpisów z X.')
        parser.add_argument('--limit-yt', type=int, default=1500, help='Najwyżej tyle komentarzy z YouTube.')
        parser.add_argument('--tytul', default='', help='Tytuł raportu.')
        parser.add_argument('--temat', default='', help='Opis tematu dla modelu (domyślnie frazy).')
        parser.add_argument('--wyslij', action='store_true', help='Wyślij skrót mailem na adres administratora.')
        parser.add_argument('--zachowaj', action='store_true', help='Debugowanie: zapisz surowe dane (JSON) obok raportu; domyślnie są kasowane.')
        parser.add_argument('--plan', action='store_true', help='Tylko szacunek: liczniki X i lista filmów, bez odczytu wpisów i bez modelu.')
        parser.add_argument('--z-pliku', default='', help='Oceń teksty z pliku (CSV poprzedniego raportu, JSONL albo JSON pamięci podręcznej) zamiast pobierać.')
        parser.add_argument('--swiezo', action='store_true', help='Pomiń pamięć podręczną (24 h) i pobierz teksty na nowo (płatne odczyty X).')

    def handle(self, *args, **opts):
        od = _date(opts['od']) if opts['od'] else None
        do = _date(opts['do']) if opts['do'] else None
        limit, yt_limit = max(10, min(5000, opts['limit'])), max(0, min(10000, opts['limit_yt']))
        try:
            if opts['plan']:
                return self._plan(nastroje.plan(opts['fraza'], days=opts['dni'], limit=limit, yt_limit=yt_limit, od=od, do=do))
            result = nastroje.run(opts['fraza'], days=opts['dni'], limit=limit, yt_limit=yt_limit, title=opts['tytul'], topic=opts['temat'],
                                  od=od, do=do, keep_raw=opts['zachowaj'], source_file=opts['z_pliku'], refresh=opts['swiezo'])
        except nastroje.NastrojeError as error:
            raise CommandError(f'{error.code}: {error.detail}')
        self.stdout.write(nastroje.summary_text(result))
        if opts['wyslij']:
            self.stdout.write('Mail: ' + ('wysłany' if nastroje.send(result) else 'nie wysłany (brak adresu albo SMTP)'))

    def _plan(self, plan):
        est, counts = plan['estimate'], plan['counts']
        tak = lambda v: 'tak' if v else 'nie'  # noqa: E731
        self.stdout.write(f"Zakres: {plan['start'].astimezone(nastroje.PL):%d.%m.%Y} do {plan['end'].astimezone(nastroje.PL):%d.%m.%Y}")
        self.stdout.write(f"Zapytanie X: {plan['query']}")
        if counts['error']:
            self.stdout.write(f"Liczniki X: {counts['error']}")
        else:
            self.stdout.write(f"Wpisów na X w zakresie: {counts['total']} (" + ', '.join(f'{d[5:]}: {n}' for d, n in sorted(counts['days'].items())) + ')')
        if plan['videos']['error']:
            self.stdout.write(f"YouTube: {plan['videos']['error']}")
        else:
            self.stdout.write(f"YouTube: {len(plan['videos']['videos'])} filmów z frazami; najpopularniejsze:")
            for v in plan['videos']['videos'][:nastroje.YT_VIDEOS]:
                self.stdout.write(f"  {v['views']:>9} wyśw. {v['comments']:>6} kom.  {v['channel'][:30]}: {v['title'][:70]}")
        self.stdout.write(f"Tytułów z mediów w bazie: {plan['media']}; Wykop: {tak(plan['wykop'])}; kanałów RSS: {plan['rss_feeds']}")
        self.stdout.write(f"Szacunek: do {est['x_reads']} odczytów X (~{est['x_usd']} USD), do {est['yt_comments']} komentarzy YouTube "
                          f"(~{est['yt_units']} jednostek, zostało {plan['yt_units_left']}), {est['mercury_calls']} wywołań Mercury "
                          f"(~{est['mercury_tokens']} tokenów)")
        self.stdout.write(f"X skonfigurowane: {tak(plan['x_configured'])}; dzienny limit odczytów X (X_REPLIES_DAILY_CAP): {plan['daily_cap']}; "
                          f"Mercury gotowy: {tak(plan['mercury_ready'])}; darmowe modele Konsylium w zapasie: "
                          f"{', '.join(plan['council_models']) or 'brak'}; teksty w pamięci podręcznej: {tak(plan['cached'])}")

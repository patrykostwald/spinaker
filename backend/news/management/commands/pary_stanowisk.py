"""„Wcześniej i teraz” (v3): kandydaci, decyzje człowieka, wycofania i bilans miary.

python manage.py pary_stanowisk generuj --z-pętli [--limit 50]
python manage.py pary_stanowisk generuj --osoba 123 --temat "podatek od nieruchomości"
python manage.py pary_stanowisk dodaj --osoba 123 --temat "..." --a post:1 --b ballot:2 [--cytat-a "..."] [--cytat-b "..."] [--kontekst "..."] --kto <login>
python manage.py pary_stanowisk lista [--status suggested]
python manage.py pary_stanowisk pokaz <id>
python manage.py pary_stanowisk zatwierdz <id> --kto <login> [--uwaga "..."]
python manage.py pary_stanowisk odrzuc <id> --kto <login> --uwaga "..."
python manage.py pary_stanowisk wycofaj <id> --kto <login> --uwaga "publiczny powód"
python manage.py pary_stanowisk bilans     (wewnętrzna kontrola tej samej miary: liczby wg obozu kont, niepubliczne)
"""
import json
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


DECIDE = 'news.can_decide_positionpair'


class Command(BaseCommand):
    help = '„Wcześniej i teraz”: kandydaci par stanowisk (AI albo człowiek) i decyzje człowieka.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        gen = sub.add_parser('generuj')
        gen.add_argument('--z-petli', action='store_true', help='Kandydaci z pętli Zmiana zdania (bez nowych wywołań modeli).')
        gen.add_argument('--osoba')
        gen.add_argument('--temat')
        gen.add_argument('--limit', type=int, default=50)
        add = sub.add_parser('dodaj')
        for name in ('--osoba', '--temat', '--a', '--b', '--kto'):
            add.add_argument(name, required=True)
        for name in ('--cytat-a', '--cytat-b', '--kontekst'):
            add.add_argument(name, default='')
        listing = sub.add_parser('lista')
        listing.add_argument('--status', default='suggested')
        sub.add_parser('bilans')
        show = sub.add_parser('pokaz')
        show.add_argument('id', type=int)
        for name in ('zatwierdz', 'odrzuc', 'wycofaj', 'rozpatrz'):
            p = sub.add_parser(name)
            p.add_argument('id', type=int)
            p.add_argument('--kto', required=True)
            p.add_argument('--uwaga', default='')
            if name == 'zatwierdz':
                p.add_argument('--potwierdzam-przedmiot', action='store_true',
                               help='Przedmiot głosowania (wniosek o odrzucenie, poprawka, inne) sprawdzony w druku i opisany w kontekście.')
                p.add_argument('--kontekst', default=None, help='Kontekst od człowieka (zastępuje kontekst AI).')
                p.add_argument('--temat', default=None)
        sub.add_parser('zgloszenia')
        old = sub.add_parser('stare', help='Przegląd par ze starego bloku „Zmiana zdania” (PositionCheck), niepublicznych od 13.10.')
        old.add_argument('--przenies', action='store_true', help='Przenieś je do kolejki „Wcześniej i teraz” jako kandydatów.')
        old.add_argument('--limit', type=int, default=200)
        clean = sub.add_parser('czysc-kontakty', help='Retencja: usuń adresy zgłaszających po rozstrzygnięciu.')
        clean.add_argument('--dni', type=int, default=None)
        ver = sub.add_parser('zweryfikuj', help='Potwierdź konto jako osobę z rejestru albo jej przedstawiciela.')
        for name in ('--login', '--osoba', '--dowod', '--kto'):
            ver.add_argument(name, required=True)
        ver.add_argument('--rola', choices=['osoba', 'przedstawiciel'], default='przedstawiciel')
        sub.add_parser('odpowiedzi', help='Odpowiedzi osób czekające na decyzję.')
        for name in ('odpowiedz-opublikuj', 'odpowiedz-odrzuc'):
            p = sub.add_parser(name)
            p.add_argument('id', type=int)
            p.add_argument('--kto', required=True)
            p.add_argument('--uwaga', default='')

    def _staff(self, login, decide=False):
        user = get_user_model().objects.filter(username=login, is_staff=True).first()
        if user is None:
            raise CommandError('Decyzję podejmuje członek personelu (is_staff); nie ma takiego loginu.')
        if decide and not user.has_perm(DECIDE):
            raise CommandError(f'To konto nie ma uprawnienia {DECIDE}.')
        return user

    def _figure(self, ident):
        from news.przeszlosc_osoba import resolve
        figure = resolve(ident)
        if figure is None:
            raise CommandError('Nie ma takiej osoby publicznej w rejestrze.')
        return figure

    def handle(self, *args, **opts):
        from news import position_pairs as pp
        from news.clinic_models import PositionPair
        action = opts['action']
        if action == 'generuj':
            if opts['z_petli']:
                result = pp.from_checks(limit=opts['limit'])
            elif opts['osoba'] and opts['temat']:
                result = pp.from_topic(self._figure(opts['osoba']), opts['temat'])
            else:
                raise CommandError('Podaj --z-petli albo --osoba i --temat.')
            self.stdout.write(json.dumps(result, ensure_ascii=False))
            return
        if action == 'dodaj':
            try:
                pair = pp.suggest(self._figure(opts['osoba']), opts['temat'], opts['a'], opts['b'], opts['cytat_a'],
                                  opts['cytat_b'], opts['kontekst'], user=self._staff(opts['kto']))
            except pp.PairError as error:
                raise CommandError(f'Para odrzucona przez walidator: {error}') from None
            self.stdout.write(f'{pair.pk}: {pair.status}')
            return
        if action == 'lista':
            for pair in PositionPair.objects.filter(status=opts['status']).select_related('figure').order_by('-created_at'):
                self.stdout.write(f'{pair.pk}\t{pair.figure.canonical_name}\t{pair.topic}\t{pair.a_date} -> {pair.b_date}\t'
                                  f'{"AI" if pair.ai_suggested else "człowiek"}\t{pair.reports.filter(resolved_at__isnull=True).count()} zgłoszeń')
            return
        if action == 'bilans':
            self._balance()
            return
        if action == 'stare':
            self._legacy(opts)
            return
        if action == 'odpowiedzi':
            from news.clinic_models import SubjectResponse
            for r in SubjectResponse.objects.filter(status='zgloszona').select_related('pair__figure').order_by('submitted_at'):
                self.stdout.write(f'{r.pk}\tpara {r.pair_id}\t{r.pair.figure.canonical_name}\t{r.via}\t{r.text[:100]}')
            return
        if action in ('odpowiedz-opublikuj', 'odpowiedz-odrzuc'):
            from news.clinic_models import SubjectResponse
            row = SubjectResponse.objects.filter(pk=opts['id']).first()
            if row is None:
                raise CommandError('Nie ma takiej odpowiedzi.')
            try:
                row = pp.decide_response(row, self._staff(opts['kto'], decide=True), action == 'odpowiedz-opublikuj', opts['uwaga'])
            except pp.PairError as error:
                raise CommandError(str(error)) from None
            self.stdout.write(f'{row.pk}: {row.status}')
            return
        if action == 'czysc-kontakty':
            self.stdout.write(f'wyczyszczono kontakty: {pp.clean_contacts(opts["dni"])}')
            return
        if action == 'zgloszenia':
            from news.clinic_models import PositionPairReport
            rows = (PositionPairReport.objects.filter(resolved_at__isnull=True).select_related('pair__figure')
                    .order_by('priority', 'created_at'))  # „wysoki” przed „zwykly”, potem najstarsze (SLA)
            for r in rows:
                self.stdout.write(f'{r.priority}\t{r.created_at:%Y-%m-%d %H:%M}\tpara {r.pair_id} ({r.pair.status})\t'
                                  f'{r.pair.figure.canonical_name}\t{"zweryfikowany" if r.verified else ("konto" if r.user_id else "anonim")}\t{r.reason[:80]}')
            return
        if action == 'zweryfikuj':
            from news.clinic_models import VerifiedReporter
            account = get_user_model().objects.filter(username=opts['login']).first()
            if account is None:
                raise CommandError('Nie ma takiego konta.')
            row, _ = VerifiedReporter.objects.update_or_create(
                user=account, figure=self._figure(opts['osoba']),
                defaults={'role': opts['rola'], 'evidence': opts['dowod'][:400], 'verified_by': self._staff(opts['kto'], decide=True),
                          'revoked_at': None})
            self.stdout.write(f'zweryfikowany: {account.username} -> {row.figure.canonical_name} ({row.role})')
            return
        pair = PositionPair.objects.filter(pk=opts['id']).first()
        if pair is None:
            raise CommandError('Nie ma takiej pary.')
        if action == 'pokaz':
            self.stdout.write(json.dumps({'id': pair.pk, 'status': pair.status, 'topic': pair.topic, 'a': pair.a, 'b': pair.b,
                                          'context': pair.context, 'ai_suggested': pair.ai_suggested, 'model': pair.model_name,
                                          'reports': list(pair.reports.values('created_at', 'reason', 'is_subject', 'resolved_at'))},
                                         ensure_ascii=False, indent=2, default=str))
            return
        user = self._staff(opts['kto'], decide=True)
        try:
            if action == 'zatwierdz':
                pair = pp.approve(pair, user, opts['uwaga'], confirm_subject=opts['potwierdzam_przedmiot'],
                                  context=opts['kontekst'], topic=opts['temat'])
            elif action == 'odrzuc':
                if not opts['uwaga'].strip():
                    raise CommandError('Odrzucenie wymaga uzasadnienia (--uwaga).')
                pair = pp.reject(pair, user, opts['uwaga'])
            elif action == 'rozpatrz':
                done = pp.resolve_reports(pair, user, opts['uwaga'])
                self.stdout.write(f'{pair.pk}: rozpatrzone zgłoszenia {done}, status {pair.status}')
                return
            else:
                pair = pp.withdraw(pair, user, opts['uwaga'])
        except pp.PairError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f'{pair.pk}: {pair.status}')

    def _legacy(self, opts):
        """Pary, które stary blok pokazywał automatycznie (relacja zmiana stanowiska od progu). Od recenzji Fable blok jest
        wyłączony (POSITION_CHANGES_LEGACY_ENABLED=False); przed ewentualnym włączeniem człowiek przegląda każdą pozycję,
        najlepiej przenosząc ją do kolejki „Wcześniej i teraz” (--przenies) i decydując tam z dziennikiem."""
        from news import position_pairs as pp
        from news.clinic_models import PositionCheck
        from news.zmiana_zdania import MIN_CONFIDENCE
        rows = (PositionCheck.objects.filter(relation='change', confidence__gte=MIN_CONFIDENCE)
                .select_related('diagnosis__post__account').order_by('-checked_at', '-pk')[:opts['limit']])
        for c in rows:
            self.stdout.write(f'{c.pk}\tdiagnoza {c.diagnosis_id}\t@{c.diagnosis.post.account.handle}\t{c.source_date} -> '
                              f'{c.diagnosis.post.published_at:%Y-%m-%d}\t{c.confidence}\t{c.explanation[:90]}')
        if opts['przenies']:
            self.stdout.write(json.dumps(pp.from_checks(limit=opts['limit']), ensure_ascii=False))

    def _balance(self):
        """Kontrola tej samej miary (wewnętrznie, nigdy publicznie): kandydaci i decyzje wg obozu kont osoby."""
        from news.clinic_models import PositionPair
        from news.przeszlosc_osoba import x_accounts
        camps = {}
        rows = Counter()
        for pair in PositionPair.objects.select_related('figure'):
            if pair.figure_id not in camps:
                found = {a.camp for a, _ in x_accounts(pair.figure)}
                camps[pair.figure_id] = '/'.join(sorted(found)) or 'brak konta'
            rows[(camps[pair.figure_id], pair.status)] += 1
        for (camp, status), n in sorted(rows.items()):
            self.stdout.write(f'{camp}\t{status}\t{n}')

"""Ciąg przyczyn przekazu dnia (v3): lista, generowanie, zatwierdzenie i odrzucenie przez człowieka.

python manage.py lancuch_przekazu lista [--status pending_review]
python manage.py lancuch_przekazu generuj --dzien 2026-10-12 [--oboz government] [--bez-przegladu] [--wymus]
python manage.py lancuch_przekazu pokaz <id>
python manage.py lancuch_przekazu zatwierdz <id> --kto <login> [--uwaga "..."] [--mimo-uwag]
python manage.py lancuch_przekazu odrzuc <id> --kto <login> --uwaga "..."
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Ciąg przyczyn przekazu dnia: generowanie (darmowe modele), zatwierdzanie i odrzucanie przez człowieka.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        listing = sub.add_parser('lista')
        listing.add_argument('--status', default='pending_review')
        gen = sub.add_parser('generuj')
        gen.add_argument('--dzien', required=True)
        gen.add_argument('--oboz', choices=['government', 'opposition'])
        gen.add_argument('--bez-przegladu', action='store_true')
        gen.add_argument('--wymus', action='store_true', help='Nadpisz łańcuch rozstrzygnięty przez człowieka.')
        show = sub.add_parser('pokaz')
        show.add_argument('id', type=int)
        for name in ('zatwierdz', 'odrzuc'):
            p = sub.add_parser(name)
            p.add_argument('id', type=int)
            p.add_argument('--kto', required=True, help='Login członka personelu (is_staff).')
            p.add_argument('--uwaga', default='')
            if name == 'zatwierdz':
                p.add_argument('--mimo-uwag', action='store_true', help='Zatwierdź mimo uwag przeglądu (wymaga --uwaga).')

    def handle(self, *args, **opts):
        from news import causal_chain
        from news.clinic import published_messages
        from news.clinic_models import CausalChain
        action = opts['action']
        if action == 'lista':
            for chain in CausalChain.objects.filter(status=opts['status']).select_related('message').order_by('-message__day'):
                review = (chain.gates.get('przeglad') or {}).get('status', 'brak')
                self.stdout.write(f'{chain.pk}\t{chain.message.day}\t{chain.message.camp}\t{chain.status}\tprzegląd: {review}')
            return
        if action == 'generuj':
            try:
                day = date.fromisoformat(opts['dzien'])
            except ValueError:
                raise CommandError('Dzień w formacie YYYY-MM-DD.') from None
            rows = published_messages().filter(day=day)
            if opts['oboz']:
                rows = rows.filter(camp=opts['oboz'])
            for message in rows:
                chain = causal_chain.generate(message, with_review=not opts['bez_przegladu'], force=opts['wymus'])
                self.stdout.write(f'{message.day} {message.camp}: ' + (f'{chain.pk} {chain.status}' if chain else 'pominięty'))
            return
        chain = CausalChain.objects.filter(pk=opts['id']).first()
        if chain is None:
            raise CommandError('Nie ma takiego łańcucha.')
        if action == 'pokaz':
            self.stdout.write(json.dumps({'id': chain.pk, 'status': chain.status, 'steps': chain.steps, 'gates': chain.gates,
                                          'model': chain.model_name, 'prompt_version': chain.prompt_version},
                                         ensure_ascii=False, indent=2, default=str))
            return
        user = get_user_model().objects.filter(username=opts['kto'], is_staff=True).first()
        if user is None:
            raise CommandError('Decyzję podejmuje członek personelu (is_staff); nie ma takiego loginu.')
        if not user.has_perm('news.can_decide_causalchain'):
            raise CommandError('To konto nie ma uprawnienia news.can_decide_causalchain.')
        try:
            if action == 'zatwierdz':
                chain = causal_chain.approve(chain, user, opts['uwaga'], override=opts['mimo_uwag'])
            else:
                if not opts['uwaga'].strip():
                    raise CommandError('Odrzucenie wymaga uzasadnienia (--uwaga).')
                chain = causal_chain.reject(chain, user, opts['uwaga'])
        except causal_chain.ChainError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f'{chain.pk}: {chain.status}')

"""Karty „tylko metadane” dla redakcji z publicznym RSS (właściciel 6.10: więcej artykułów w drzewach, legalnie).

python manage.py zatwierdz_media_metadane --plan   - co zrobi, bez zapisów i bez sieci
python manage.py zatwierdz_media_metadane          - zapisuje karty, włącza źródła, notuje listy o zgodę (Prawnik)

Zasady: scraper/media_metadata.py (LEGAL 1, 2, 6; art. 4 DSM przy pobraniu). Źródło z zapisaną odmową, opt-outem albo
paywallem idzie na listę listów o zgodę (wydruk i notatka Prawnika), nie dostaje karty. Przebieg jest idempotentny.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import Source
from scraper import media_metadata as media
from scraper.access_gate import reviewed_instruction_for_endpoint

NOTE_TITLE = 'Listy o zgodę na metadane RSS'


class Command(BaseCommand):
    help = 'Zatwierdza redakcje z publicznym RSS wyłącznie na metadane (tytuł, data, redakcja, adres). --plan: bez zapisów.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', action='store_true', help='Tylko wypisuje, co by zrobił; nic nie zapisuje.')

    def handle(self, *args, **options):
        plan = options['plan']
        out = self.stdout.write
        out('PLAN: bez zapisów i bez sieci.' if plan else 'ZAPIS: karty metadanych, włączenie źródeł, notatka Prawnika.')
        cards_new, enabled, letters, skipped = [], [], [], defaultdict(list)
        now = timezone.now()
        for source in Source.objects.filter(source_type__in=media.MEDIA_TYPES).order_by('name', 'pk').iterator():
            label = f'{source.name} (id={source.pk})'
            reason = media.eligibility(source)
            if reason:
                skipped[reason].append(label)
                continue
            cards = list(source.access_instructions.order_by('-version'))
            refusal = media.refusal(source, cards)
            if refusal:
                letters.append((source, refusal))
                out(f'LIST: {label}: {refusal}')
                continue
            current = reviewed_instruction_for_endpoint(source, 'rss', source.rss_url)
            live = source.catalog_stage == 'configured' and source.is_active and source.scrape_enabled
            if current is not None and live:
                skipped['Aktualna karta już przepuszcza kanał'].append(label)
                continue
            if current is None and media.broken(source):
                skipped[f'Kanał do naprawy adresu ({source.last_error[:40]})'].append(label)
                continue
            if not plan:
                with transaction.atomic():
                    locked = Source.objects.select_for_update().get(pk=source.pk)
                    if current is None:
                        card = media.build_card(locked, cards, now)
                        card.full_clean()
                        card.save()
                    locked.catalog_stage = 'configured'
                    locked.is_active = locked.scrape_enabled = True
                    if locked.last_error == 'no_approved_instruction':
                        locked.last_error = ''
                    locked.full_clean()
                    locked.save()
            (enabled if current is not None else cards_new).append(label)
            out(f'{"WŁĄCZONO" if current is not None else "KARTA"}: {label}: rss {source.rss_url}; '
                f'metadane (tytuł, data, redakcja, adres), 24/dobę, 90 dni.')
        note_id = None
        if letters and not plan:
            note_id = self.save_letters(letters)
        prefix = 'Do zapisu' if plan else 'Zapisano'
        out(f'{prefix}: karty: {len(cards_new)}, włączone przy ważnej karcie: {len(enabled)}, do listu o zgodę: {len(letters)}, '
            f'pominięto: {sum(map(len, skipped.values()))}.')
        if letters:
            out('Listy o zgodę (bez karty, dopóki wydawca nie odpowie):')
            for source, refusal in letters:
                out(f'  - {source.name} ({source.url or source.rss_url}): {refusal}')
            out(f'Notatka Prawnika: #{note_id}' if note_id else 'Notatka Prawnika: w planie bez zapisu')
        for reason, labels in sorted(skipped.items()):
            out(f'{reason}: {len(labels)}')
            for label in labels:
                out(f'  - {label}')

    @staticmethod
    def save_letters(letters):
        """Jedna otwarta notatka Prawnika (kind=request) z listą redakcji do listu; kolejny przebieg ją odświeża."""
        from news.agent_models import AgentNote
        body = '\n'.join(f'- {s.name} ({s.url or s.rss_url}): {reason}' for s, reason in letters)
        body = ('Redakcje z publicznym RSS, ale z zapisaną odmową, opt-outem albo paywallem. Bez karty do czasu zgody. '
                'Prośba: list o zgodę na indeks metadanych (tytuł, data, redakcja, adres; bez treści i zdjęć).\n' + body)
        sources = [{'name': s.name, 'url': s.url or '', 'rss_url': s.rss_url, 'reason': reason} for s, reason in letters]
        title = f'{NOTE_TITLE}: {len(letters)} redakcji'
        note = AgentNote.objects.filter(agent='prawnik', kind='request', title__startswith=NOTE_TITLE,
                                        status__in=('new', 'pending')).order_by('-created_at').first()
        if note is None:
            note = AgentNote(agent='prawnik', kind='request', status='pending')
        note.title, note.body, note.sources = title, body, sources
        note.save()
        return note.pk

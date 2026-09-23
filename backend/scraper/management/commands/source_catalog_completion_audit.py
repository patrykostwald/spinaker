"""Prove that every catalog record is either explicitly allowed or explicitly off."""
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from news.models import Source, SourceReviewDecision
from scraper.access_gate import has_current_approved_instruction


class Command(BaseCommand):
    help = 'Kontrola końcowa katalogu: aktywne źródła muszą mieć kartę, kandydaci decyzję; bez zmian danych.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='reports/source-catalog-completion-audit-current.md')
        parser.add_argument('--strict', action='store_true', help='Zwraca błąd, gdy katalog nie jest kompletny.')

    def handle(self, *args, **options):
        active = list(Source.objects.filter(catalog_stage='configured', is_active=True, scrape_enabled=True).order_by('pk'))
        candidates = list(Source.objects.filter(catalog_stage='candidate', is_active=False, scrape_enabled=False)
                          .select_related('review_decision').order_by('pk'))
        active_failures, candidate_failures = [], []
        valid_active = 0
        for source in active:
            if not has_current_approved_instruction(source):
                active_failures.append((source.pk, source.name, 'missing_or_expired_access_card'))
            else:
                valid_active += 1
        decisions = Counter()
        for source in candidates:
            decision = getattr(source, 'review_decision', None)
            if decision is None:
                candidate_failures.append((source.pk, source.name, 'missing_review_decision'))
            else:
                decisions[decision.decision] += 1

        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# Source catalog completion audit', '',
            'This report is read-only. It does not enable a source, import content, or send mail.', '',
            f'- Active configured sources with a valid exact access card: **{valid_active}/{len(active)}**.',
            f'- Inactive candidates with a durable review decision: **{len(candidates) - len(candidate_failures)}/{len(candidates)}**.',
            '', '## Candidate decisions', '', '| Decision | Count |', '|---|---:|',
        ]
        for decision, label in SourceReviewDecision.Decision.choices:
            lines.append(f'| {decision} | {decisions[decision]} |')
        if active_failures:
            lines += ['', '## Active sources requiring review', '', '| ID | Source | Reason |', '|---:|---|---|']
            lines += [f'| {pk} | {name} | {reason} |' for pk, name, reason in active_failures]
        if candidate_failures:
            lines += ['', '## Candidates missing a decision', '', '| ID | Source | Reason |', '|---:|---|---|']
            lines += [f'| {pk} | {name} | {reason} |' for pk, name, reason in candidate_failures]
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        complete = not active_failures and not candidate_failures
        self.stdout.write(self.style.SUCCESS(
            f'SOURCE_CATALOG_COMPLETION: active_cards={valid_active}/{len(active)} '
            f'candidate_decisions={len(candidates) - len(candidate_failures)}/{len(candidates)} complete={str(complete).lower()}; {output}'
        ))
        if options['strict'] and not complete:
            raise CommandError('Katalog nie jest kompletny; sprawdź raport.')

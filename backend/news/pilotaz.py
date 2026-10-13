"""Pilotaż v3 (decyzja właściciela 13.10, docs/PILOTAZ_V3.md): par „Wcześniej i teraz” i ciągów przyczyn przed włączeniem flag.

Arkusz do przeglądu człowieka (CSV + MD), metryki i próg akceptacji:
- pary: odsetek odrzuceń z powodu „inna_sprawa” albo „kontekst” < 10% (recenzja Fable, sekcja 5);
- łańcuchy: odsetek odrzuceń merytorycznych < 20%.
Symetria obozów: równy podział próbki między obozy i porównanie z udziałem kont i diagnoz (bilans).
Nic nie jest publikowane: flagi zostają wyłączone, decyzje z arkusza nie zmieniają statusów.
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

PAIR_COLUMNS = ['id', 'osoba', 'oboz', 'temat', 'data_A', 'A', 'zrodlo_A', 'data_B', 'B', 'zrodlo_B', 'kontekst',
                'kontekst_zrodlo', 'decyzja', 'powod', 'czas_s']
CHAIN_COLUMNS = ['id', 'dzien', 'oboz', 'kroki', 'bramki', 'model', 'decyzja', 'powod', 'czas_s']
REASONS = ('ok', 'inna_sprawa', 'kontekst', 'cytat', 'glos', 'nazwisko', 'fakt_bez_zrodla', 'jezyk', 'inne')
# Słownik powodów odrzucenia dla każdego rodzaju (recenzja Codex 3): odrzucony wiersz z pustym albo spoza słownika powodem = błąd.
REJECT_REASONS = {'par': {'inna_sprawa', 'kontekst', 'cytat', 'glos', 'inne'},
                  'lancuch': {'fakt_bez_zrodla', 'nazwisko', 'kontekst', 'inna_sprawa', 'cytat', 'jezyk', 'inne'}}
BLOCKING = {'par': {'inna_sprawa', 'kontekst'}, 'lancuch': REJECT_REASONS['lancuch'] - {'jezyk'}}


class ReportError(ValueError):
    pass
PAIR_BLOCKING = {'inna_sprawa', 'kontekst'}
THRESHOLDS = {'par': 0.10, 'lancuch': 0.20}
COST_NOTE = ('Koszt w wywołaniach darmowych modeli: pary z pętli Zmiana zdania - 0 nowych; generator tematów - do 6 na osobę '
             'i temat; łańcuch - 1 generowanie + 3 przeglądy = 4 na przekaz (2 obozy x 20 dni = do 160).')


def output_dir(path=None) -> Path:
    target = Path(path) if path else Path(settings.BASE_DIR) / 'tmp' / 'pilotaz' / timezone.localdate().isoformat()
    target.mkdir(parents=True, exist_ok=True)
    return target


def figure_camp(figure) -> str:
    from news.przeszlosc_osoba import x_accounts
    camps = sorted({a.camp for a, _ in x_accounts(figure)})
    return '/'.join(camps) or 'brak konta'


def balance() -> dict:
    """Bilans miary: udział kont i opublikowanych diagnoz wg obozu (punkt odniesienia dla symetrii próbki)."""
    from news.clinic import published_diagnoses
    from news.political_models import PoliticalAccount
    accounts = Counter(PoliticalAccount.objects.filter(enabled=True).values_list('camp', flat=True))
    diagnoses = Counter(published_diagnoses().values_list('post__camp_at_collection', flat=True))

    def share(counter):
        total = sum(counter.values()) or 1
        return {k: round(v / total, 3) for k, v in sorted(counter.items())}
    return {'accounts': share(accounts), 'diagnoses': share(diagnoses)}


def _side_text(side) -> str:
    if side.get('kind') == 'glos':
        return f"{side.get('vote_label') or side.get('vote')} | {side.get('vote_subject', '')}"
    return side.get('quote') or ''


def round_robin(by_camp: dict, n: int) -> list:
    """Recenzja Codex 3: wszystkie obozy (także „brak konta” i inne), po jednym na kolejkę, aż do n; przy nieparzystym n
    różnica najwyżej 1, a pierwszy obóz w kolejce zmienia się z dniem (bez stałego faworyzowania)."""
    camps = sorted(by_camp)
    if not camps:
        return []
    shift = timezone.localdate().toordinal() % len(camps)
    camps = camps[shift:] + camps[:shift]
    queues = {c: list(by_camp[c]) for c in camps}
    sample = []
    while len(sample) < n and any(queues.values()):
        for camp in camps:
            if queues[camp] and len(sample) < n:
                sample.append((camp, queues[camp].pop(0)))
    return sample


def pairs(n=50, *, generate=False, topics=(), ask=None, max_calls=60, dry_run=False, path=None) -> dict:
    """Arkusz par do przeglądu: kandydaci z pętli (bez modeli) i opcjonalnie z generatora tematów; równy podział obozów."""
    from news import position_pairs as pp
    from news.clinic_models import PositionPair
    log = {'from_checks': None, 'from_topic': [], 'calls': 0}
    if not dry_run:
        log['from_checks'] = pp.from_checks(limit=max(n * 4, 100))
        if generate:
            for topic in topics:
                for figure in _figures_for_topic(topic):
                    if log['calls'] >= max_calls:
                        break
                    result = pp.from_topic(figure, topic, ask=ask, max_asks=min(6, max_calls - log['calls']))
                    log['calls'] += result['asked']
                    log['from_topic'].append({'topic': topic, 'figure': figure.pk, **result})
    candidates = list(PositionPair.objects.filter(status='suggested').select_related('figure').order_by('-created_at')[:n * 10])
    by_camp = defaultdict(list)
    for pair in candidates:
        by_camp[figure_camp(pair.figure)].append(pair)
    sample = round_robin(by_camp, n)
    target = output_dir(path)
    stamp = timezone.now().strftime('%Y%m%d-%H%M')
    csv_path = target / f'pilotaz-par-{stamp}.csv'
    with csv_path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_COLUMNS, delimiter=';')
        writer.writeheader()
        for camp, p in sample:
            writer.writerow({'id': p.pk, 'osoba': p.figure.canonical_name, 'oboz': camp, 'temat': p.topic,
                             'data_A': p.a.get('date'), 'A': _side_text(p.a), 'zrodlo_A': (p.a.get('source') or {}).get('url'),
                             'data_B': p.b.get('date'), 'B': _side_text(p.b), 'zrodlo_B': (p.b.get('source') or {}).get('url'),
                             'kontekst': p.context, 'kontekst_zrodlo': p.context_source, 'decyzja': '', 'powod': '', 'czas_s': ''})
    counts = Counter(camp for camp, _ in sample)
    md = target / f'pilotaz-par-{stamp}.md'
    md.write_text('\n'.join([
        f'# Pilotaż par „Wcześniej i teraz” ({timezone.localdate().isoformat()})', '',
        f'Próbka: {len(sample)} z {len(candidates)} kandydatów; obozy w próbce: {dict(counts)}.',
        f'Bilans (udział kont / diagnoz): {balance()}.', f'Wywołania modeli w tym przebiegu: {log["calls"]}. {COST_NOTE}', '',
        'Instrukcja: w CSV wpisz `decyzja` (tak/nie), `powod` (' + ', '.join(REASONS) + ') i `czas_s` (sekundy przeglądu).',
        'Czytaj oba źródła w całości. Potem: `python manage.py pilotaz raport --plik <csv>`.',
        f'Próg akceptacji: odrzucenia z powodu inna_sprawa albo kontekst < {int(THRESHOLDS["par"] * 100)}% przeglądniętych.']),
        encoding='utf-8')
    return {'csv': str(csv_path), 'md': str(md), 'sample': len(sample), 'by_camp': dict(counts), 'log': log,
            'candidates_by_camp': {c: len(v) for c, v in sorted(by_camp.items())}, 'excluded_camps': []}


def _figures_for_topic(topic, limit=10):
    from news.political_models import PublicFigure
    from news.position_pairs import topic_items
    out = []
    for figure in PublicFigure.objects.filter(archived=False).order_by('pk')[:500]:
        if len(out) >= limit:
            break
        if len(topic_items(figure, topic, limit=20)) >= 2:
            out.append(figure)
    return out


def chains(days=20, *, generate=False, ask=None, max_calls=160, dry_run=False, path=None) -> dict:
    """Arkusz łańcuchów: przekazy obu obozów z ostatnich `days` dni; opcjonalnie generowanie (4 wywołania na przekaz)."""
    from news import causal_chain
    from news.clinic import published_messages
    from news.clinic_models import CausalChain
    since = timezone.localdate() - timedelta(days=days)
    messages = list(published_messages().filter(day__gte=since).order_by('-day', 'camp'))
    calls = 0
    if generate and not dry_run:
        for message in messages:
            if calls + 4 > max_calls:
                break
            causal_chain.generate(message, ask=ask)
            calls += 4
    target = output_dir(path)
    stamp = timezone.now().strftime('%Y%m%d-%H%M')
    csv_path = target / f'pilotaz-lancuch-{stamp}.csv'
    chains_by_message = {c.message_id: c for c in CausalChain.objects.filter(message__in=messages)}
    rows = 0
    with csv_path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CHAIN_COLUMNS, delimiter=';')
        writer.writeheader()
        for message in messages:
            chain = chains_by_message.get(message.pk)
            if chain is None:
                continue
            steps = ' || '.join(f"{s['kind']}: {s['text']}" + (f" [{s['source']['name']}]" if s.get('source') else '')
                                for s in chain.steps)
            gates = ', '.join(f"{k}={v.get('status')}" for k, v in (chain.gates or {}).items())
            writer.writerow({'id': chain.pk, 'dzien': message.day.isoformat(), 'oboz': message.camp, 'kroki': steps,
                             'bramki': gates, 'model': chain.model_name, 'decyzja': '', 'powod': '', 'czas_s': ''})
            rows += 1
    return {'csv': str(csv_path), 'messages': len(messages), 'chains': rows, 'calls': calls}


def report(path, kind='par') -> dict:
    """Metryki z wypełnionego arkusza: odsetek odrzuceń (ogółem i z powodów blokujących), czas przeglądu, symetria obozów,
    werdykt względem progu. Zapisuje obok plik MD."""
    with open(path, encoding='utf-8-sig', newline='') as handle:
        rows = [r for r in csv.DictReader(handle, delimiter=';') if (r.get('decyzja') or '').strip()]
    total = len(rows)
    decisions = {'tak', 't', 'nie', 'n', 'odrzuc', 'odrzucona'}
    bad = [r.get('id') for r in rows if r['decyzja'].strip().lower() not in decisions]
    if bad:
        raise ReportError(f'Nieznana decyzja (tak/nie) w wierszach: {bad[:10]}')
    rejected = [r for r in rows if r['decyzja'].strip().lower() in ('nie', 'n', 'odrzuc', 'odrzucona')]
    invalid = [r.get('id') for r in rejected if (r.get('powod') or '').strip() not in REJECT_REASONS[kind]]
    if invalid:
        raise ReportError(f'Odrzucone wiersze bez powodu ze słownika ({", ".join(sorted(REJECT_REASONS[kind]))}): {invalid[:10]}')
    blocking = BLOCKING[kind]
    blocked = [r for r in rejected if (r.get('powod') or '').strip() in blocking]
    times = [float(r['czas_s']) for r in rows if (r.get('czas_s') or '').replace('.', '', 1).isdigit()]
    camps = defaultdict(lambda: {'przegladniete': 0, 'odrzucone': 0})
    for r in rows:
        camps[r.get('oboz', '')]['przegladniete'] += 1
        if r in rejected:
            camps[r.get('oboz', '')]['odrzucone'] += 1
    for value in camps.values():
        value['odsetek_odrzucen'] = round(value['odrzucone'] / value['przegladniete'], 3) if value['przegladniete'] else None
    rate = round(len(blocked) / total, 3) if total else None
    threshold = THRESHOLDS[kind]
    result = {'kind': kind, 'reviewed': total, 'rejected': len(rejected), 'blocking_rejected': len(blocked),
              'blocking_rate': rate, 'threshold': threshold, 'reasons': dict(Counter((r.get('powod') or '').strip() for r in rejected)),
              'time_median_s': statistics.median(times) if times else None, 'time_total_min': round(sum(times) / 60, 1) if times else None,
              'camps': dict(camps), 'minimum_reviewed': 50 if kind == 'par' else 20,
              'accepted': bool(total and rate is not None and rate < threshold and total >= (50 if kind == 'par' else 20))}
    md = Path(path).with_suffix('.raport.md')
    md.write_text('\n'.join([
        f'# Raport pilotażu: {"pary" if kind == "par" else "łańcuchy"}', '',
        f'Przeglądnięte: {total} (minimum {result["minimum_reviewed"]}); odrzucone: {len(rejected)}; '
        f'z powodów blokujących ({", ".join(sorted(blocking))}): {len(blocked)} = {rate}.',
        f'Próg: < {threshold}. Werdykt: {"PRZYJĘTY" if result["accepted"] else "NIE PRZYJĘTY"}.',
        f'Powody odrzuceń: {result["reasons"]}.', f'Czas przeglądu: mediana {result["time_median_s"]} s, razem {result["time_total_min"]} min.',
        f'Obozy: {result["camps"]}.', f'Bilans miary (udział kont / diagnoz): {balance()}.']), encoding='utf-8')
    result['md'] = str(md)
    return result

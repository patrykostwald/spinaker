"""Raport tygodniowy dla instytucji (plan finansowy 6.10, ruch 6): PDF + CSV co poniedziałek za poprzedni pełny tydzień.

Bez AI i bez sieci: liczy kod z opublikowanych diagnoz Dr. Spina (te same, które widzą czytelnicy). Zawartość:
wypowiedzi tygodnia (diagnozy z linkami), techniki po obu stronach, trend klubów (ten tydzień wobec poprzedniego) i metoda.
Ta sama miara dla wszystkich: jeden wzór wskaźnika, jeden próg minimalnej próby dla każdego klubu, ta sama oferta
dla każdego kupującego (także partii). Kupujący nie ma wpływu na kryteria ani na treść.

Publiczna próbka (tylko liczby zbiorcze, bez listy wypowiedzi) wychodzi na /dla-redakcji dopiero po zatwierdzeniu
w panelu albo, gdy właściciel zatwierdzi format na stałe, automatycznie (WEEKLY_SAMPLE_AUTO_PUBLIC=true).
"""
import csv
import io
import os
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from news import clinic, report_data
from news.report_exports import PAD, WIDTH, Pages, safe_cell
from news.spin_colors import strength_color

WARSAW = report_data.WARSAW
CLUB_MIN = 3  # ten sam próg dla każdego klubu: mniej diagnoz w tygodniu = „za mało danych”, bez wskaźnika
METHOD_EXTRA = ('Kluby: przynależność z potwierdzonego profilu osoby (rola albo klub w Sejmie), w chwili przygotowania raportu. '
                f'Wskaźnik klubu liczymy tylko przy co najmniej {CLUB_MIN} diagnozach w tygodniu - ten sam próg dla każdego klubu. '
                'Trend to różnica wskaźnika ważonego wobec poprzedniego tygodnia w punktach procentowych. '
                'Kupujący raport nie ma wpływu na kryteria Dr. Spina, wybór wpisów ani treść serwisu; '
                'raport sprzedajemy wszystkim na tych samych warunkach.')


def week_bounds(today=None):
    """Poprzedni pełny tydzień: poniedziałek (włącznie) do poniedziałku (wyłącznie)."""
    today = today or timezone.now().astimezone(WARSAW).date()
    end = today - timedelta(days=today.weekday())
    return end - timedelta(days=7), end


def auto_public():
    return os.environ.get('WEEKLY_SAMPLE_AUTO_PUBLIC', '').strip().lower() == 'true'


def _rows(start, end):
    from news.clinic_models import SpinDiagnosis
    rows = report_data.diagnosis_rows(start, end)
    ids = [int(r['id'].split(':')[1]) for r in rows]
    accounts = dict(SpinDiagnosis.objects.filter(pk__in=ids).values_list('pk', 'post__account_id'))
    figures = clinic.figures_by_account(set(accounts.values()))
    for row in rows:
        figure = figures.get(accounts.get(int(row['id'].split(':')[1])))
        party = clinic.party_data(figure) if figure else None
        row['club'] = (party or {}).get('short') or ''
        row['person'] = figure.canonical_name if figure else ''
    return rows


def _index(selected):
    counts = Counter(r['verdict'] for r in selected)
    return round(100 * (counts['spin'] + .5 * counts['partial']) / len(selected), 1) if selected else None


def clubs(rows, previous):
    """Trend klubów: ten sam wzór i próg dla każdego klubu; kolejność wg liczby diagnoz, potem nazwy."""
    result = []
    for club in sorted({r['club'] for r in rows if r['club']}):
        selected = [r for r in rows if r['club'] == club]
        before = [r for r in previous if r['club'] == club]
        enough, enough_before = len(selected) >= CLUB_MIN, len(before) >= CLUB_MIN
        index, index_before = (_index(selected) if enough else None), (_index(before) if enough_before else None)
        result.append({'club': club, 'camp': Counter(r['camp'] for r in selected).most_common(1)[0][0],
                       'count': len(selected), 'count_before': len(before), 'weighted_spin_percent': index,
                       'trend_pp': round(index - index_before, 1) if index is not None and index_before is not None else None,
                       'average_intensity': round(sum(r['intensity'] for r in selected) / len(selected), 1) if enough else None,
                       'techniques': [t for t, _ in Counter(t for r in selected for t in set(r['techniques'])).most_common(3)] if enough else []})
    return sorted(result, key=lambda c: (-c['count'], c['club']))


def build(start, end):
    rows = _rows(start, end)
    previous = _rows(start - timedelta(days=7), start)
    aggregates = report_data.aggregate(rows)
    camps = {camp: {**values, 'top_techniques': [t for t, _ in Counter(values['techniques']).most_common(5)]}
             for camp, values in aggregates.items()}
    top = sorted(rows, key=lambda r: (-r['intensity'], r['id']))[:10]
    return {'version': 1, 'start': str(start), 'end_exclusive': str(end), 'week_end': str(end - timedelta(days=1)),
            'generated_at': timezone.now().isoformat(), 'total': len(rows), 'total_before': len(previous),
            'camps': camps, 'clubs': clubs(rows, previous), 'top': top, 'rows': rows,
            'method': report_data.METHOD['pl'] + ' ' + METHOD_EXTRA, 'club_min': CLUB_MIN}


def _date(value):
    from datetime import date
    return date.fromisoformat(value).strftime('%d.%m.%Y')


def pl(value):
    """Liczba z przecinkiem dziesiętnym (polski zapis)."""
    return str(value).replace('.', ',')


def signed(value):
    return ('+' if value > 0 else '') + pl(value)


def summary_lines(data):
    """Zdania liczone przez kod (bez modelu): co raport mówi na pierwszej stronie."""
    g, o = data['camps']['government'], data['camps']['opposition']
    lines = [f"Dr. Spin ocenił {data['total']} wypowiedzi (tydzień wcześniej: {data['total_before']}): "
             f"rządzący {g['count']}, opozycja {o['count']}."]
    for label, values in (('Rządzący', g), ('Opozycja', o)):
        if values['count']:
            techniques = ', '.join(t.lower() for t in values['top_techniques'][:3]) or 'brak rozpoznanych technik'
            lines.append(f"{label}: wskaźnik ważony spinu {pl(values['weighted_spin_percent'])}%, średnia siła "
                         f"{pl(values['average_intensity'])}/100; najczęstsze techniki: {techniques}.")
    moved = [c for c in data['clubs'] if c['trend_pp'] is not None]
    if moved:
        biggest = max(moved, key=lambda c: (abs(c['trend_pp']), c['club']))
        lines.append(f"Największa zmiana wskaźnika wśród klubów: {biggest['club']} "
                     f"({signed(biggest['trend_pp'])} pkt proc. wobec poprzedniego tygodnia).")
    return lines


def render_pdf(data):
    pages = Pages(False)
    pages.text('Raport tygodniowy przekazu', 42, True)
    pages.text(f"{_date(data['start'])} - {_date(data['week_end'])}", 24, color='#536174')
    pages.heading('Podsumowanie')
    for line in summary_lines(data):
        pages.text(line)
    if data['total']:
        pages.chart({camp: {'count': v['count'], 'weighted_spin': (v['weighted_spin_percent'] or 0) / 100
                            if v['weighted_spin_percent'] is not None else None} for camp, v in data['camps'].items()})
        pages.text('Wskaźnik nie jest odsetkiem wpisów ze spinem.', 18, color='#536174')
    for camp, label in (('government', 'Rządzący'), ('opposition', 'Opozycja')):
        values = data['camps'][camp]
        pages.heading(f'{label}: techniki')
        if not values['count']:
            pages.text('Brak ocenionych wypowiedzi w tym tygodniu.', 20)
            continue
        for technique, n in sorted(values['techniques'].items(), key=lambda item: (-item[1], item[0]))[:8]:
            pages.need(40)
            pages.text(f'{technique}: {n}', 20)
            pages.draw.rectangle((PAD, pages.y - 4, PAD + 600 * n / max(values['count'], 1), pages.y + 6), fill='#4a6fa5')
            pages.y += 14
    pages.heading('Kluby: trend tygodnia')
    pages.text(f"Ten sam próg dla każdego klubu: co najmniej {data['club_min']} diagnozy w tygodniu.", 18, color='#536174')
    if not data['clubs']:
        pages.text('Brak wypowiedzi z potwierdzoną przynależnością klubową.', 20)
    for c in data['clubs']:
        index = 'za mało danych' if c['weighted_spin_percent'] is None else f"wskaźnik {pl(c['weighted_spin_percent'])}%"
        trend = '' if c['trend_pp'] is None else f", zmiana {signed(c['trend_pp'])} pkt proc."
        pages.text(f"{c['club']}: {c['count']} wypowiedzi (poprz. {c['count_before']}), {index}{trend}", 20, True)
        if c['techniques']:
            pages.text('Techniki: ' + ', '.join(c['techniques']), 18, color='#536174')
    pages.heading('Najsilniejsze wypowiedzi tygodnia')
    for row in data['top']:
        who = ' | '.join(x for x in (row.get('person'), row.get('club')) if x)
        pages.text(f"{_date(row['date'])} | {who or ('Rządzący' if row['camp'] == 'government' else 'Opozycja')} | {row['intensity']}/100", 20, True)
        pages.draw.rectangle((WIDTH - PAD - 35, pages.y - 36, WIDTH - PAD - 15, pages.y - 16), fill=strength_color(row['intensity']))
        if row.get('headline'):
            pages.text(row['headline'], 18, color='#536174')
        pages.text(row['analysis_url'], 16, color='#536174')
    pages.text('Pełna lista wypowiedzi z linkami do źródeł: plik CSV.', 18, color='#536174')
    pages.new()
    pages.text('Metoda i źródła', 30, True)
    pages.text(data['method'], 18)
    pages.text(f"Okres: {_date(data['start'])} - {_date(data['week_end'])}. Stan danych: {data['generated_at'][:16].replace('T', ' ')} UTC.", 18)
    pages.text('Wydawca: spin.clinic, iapply sp. z o.o., Poznań. Kontakt: kontakt@spin.clinic.', 18)
    out = io.BytesIO()
    images = pages.finish()
    images[0].save(out, format='PDF', save_all=True, append_images=images[1:], resolution=150,
                   title='spin.clinic - Raport tygodniowy', author='spin.clinic')
    return out.getvalue()


def render_csv(data):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['sekcja', 'id', 'data', 'obóz', 'klub', 'osoba', 'werdykt', 'siła', 'techniki', 'nagłówek',
                     'źródło', 'analiza', 'liczba', 'liczba_poprz', 'wskaźnik_proc', 'trend_pp'])
    for r in data['rows']:
        writer.writerow([safe_cell(v) for v in ('wypowiedź', r['id'], r['date'], r['camp'], r['club'], r['person'], r['verdict'],
                                                r['intensity'], '; '.join(r['techniques']), r.get('headline', ''), r['url'],
                                                r['analysis_url'], '', '', '', '')])
    for camp, v in data['camps'].items():
        writer.writerow([safe_cell(x) for x in ('obóz', camp, data['start'], camp, '', '', '', v['average_intensity'] or '',
                                                '; '.join(v['top_techniques']), '', '', '', v['count'], '',
                                                v['weighted_spin_percent'] if v['weighted_spin_percent'] is not None else '', '')])
    for c in data['clubs']:
        writer.writerow([safe_cell(x) for x in ('klub', c['club'], data['start'], c['camp'], c['club'], '', '', c['average_intensity'] or '',
                                                '; '.join(c['techniques']), '', '', '', c['count'], c['count_before'],
                                                '' if c['weighted_spin_percent'] is None else c['weighted_spin_percent'],
                                                '' if c['trend_pp'] is None else c['trend_pp'])])
    return ('﻿' + stream.getvalue()).encode('utf-8')


def generate(today=None, force=False):
    """Idempotentnie: jeden numer na tydzień. Wcześniejszy błąd albo force=True liczy numer od nowa (naprawa sama)."""
    from news.sales_models import WeeklyReportIssue
    start, end = week_bounds(today)
    issue = WeeklyReportIssue.objects.filter(week_start=start).first()
    if issue and issue.status != 'failed' and not force:
        return {'status': 'already_done', 'issue': issue.pk, 'produced': 0}
    issue = issue or WeeklyReportIssue(week_start=start, week_end=end - timedelta(days=1))
    try:
        data = build(start, end)
        issue.data = {k: v for k, v in data.items() if k != 'rows'}
        issue.pdf, issue.csv = render_pdf(data), render_csv(data)
        issue.status = 'ready' if data['total'] else 'empty'
    except Exception as error:  # noqa: BLE001 - zapis błędu, następny bieg naprawia
        issue.status, issue.data = 'failed', {'error': type(error).__name__}
    issue.generated_at = timezone.now()
    if issue.status == 'ready' and auto_public() and not issue.public_approved_at:
        issue.public_approved_at = timezone.now()
    issue.save()
    return {'status': 'ok' if issue.status != 'failed' else 'error', 'issue': issue.pk, 'week': str(start),
            'produced': int(issue.status == 'ready'), **({'error': issue.data.get('error')} if issue.status == 'failed' else {})}


def _sample_unavailable(reason):
    now = timezone.now().astimezone(WARSAW)
    next_report = (now + timedelta(days=(-now.weekday()) % 7)).replace(
        hour=6, minute=40, second=0, microsecond=0)
    if next_report <= now:
        next_report += timedelta(days=7)
    return {'available': False, 'reason': reason, 'next_report_at': next_report.isoformat()}


def public_sample():
    """Zatwierdzony numer: wyłącznie sprawdzone liczby zbiorcze i jawny zakres próbki."""
    from news.sales_models import WeeklyReportIssue
    issue = WeeklyReportIssue.objects.filter(status='ready', public_approved_at__isnull=False).order_by('-week_start').first()
    if not issue:
        return _sample_unavailable('no_approved_report')
    data = issue.data
    if not isinstance(data, dict):
        return _sample_unavailable('invalid_report_data')
    # Nie przekazujemy tekstów ani dodatkowych pól ze snapshotu prywatnego raportu.
    def count(value):
        return type(value) is int and value >= 0

    if not count(data.get('total')) or not data['total'] or not count(data.get('total_before')):
        return _sample_unavailable('invalid_report_data')
    source = data.get('camps')
    if not isinstance(source, dict):
        return _sample_unavailable('invalid_report_data')
    camps = {}
    for camp in ('government', 'opposition'):
        values = source.get(camp)
        if not isinstance(values, dict) or not count(values.get('count')):
            return _sample_unavailable('invalid_report_data')
        public = {'count': values['count']}
        for key in ('weighted_spin_percent', 'average_intensity'):
            value = values.get(key)
            if values['count'] == 0:
                if value is not None:
                    return _sample_unavailable('invalid_report_data')
            elif type(value) not in (int, float) or not 0 <= value <= 100:
                return _sample_unavailable('invalid_report_data')
            public[key] = value
        camps[camp] = public
    if sum(values['count'] for values in camps.values()) != data['total']:
        return _sample_unavailable('invalid_report_data')
    return {'available': True, 'start': issue.week_start.isoformat(), 'week_end': issue.week_end.isoformat(),
            'total': data['total'], 'total_before': data['total_before'], 'camps': camps,
            'scope': 'Próbka obejmuje liczby zbiorcze za pełny tydzień. Pełny raport zawiera zestawienie technik, '
                     'trendy klubów i linki do analiz. Próbka nie zawiera listy wypowiedzi ani pełnych tabel.',
            'method': report_data.METHOD['pl'] + ' Te same kryteria i wzór wskaźnika stosujemy dla wszystkich obozów.'}

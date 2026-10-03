"""Offline Pillow PDF, CSV and method page using the existing card font and tokens."""
import csv
import io
import json

from PIL import Image, ImageDraw

from news.report_models import REPORT_TYPES
from news.spin_colors import VERDICT_COLORS, strength_color
from news.x_card import _font, ACCENT

WIDTH, HEIGHT, PAD = 1240, 1754, 90
INK, MUTED, BG = '#17212e', '#536174', '#ffffff'
TECHNIQUES_EN = {
    'Straszenie': 'Fear appeal', 'Przypisywanie sobie zasług': 'Claiming credit',
    'Przypisywanie intencji': 'Attributing intentions', 'Atak na osobę': 'Personal attack',
    'Fałszywa alternatywa': 'False dilemma', 'Słomiany człowiek': 'Straw man',
    'Fałszywa analogia i skojarzenie': 'False analogy and association',
    'Przeinaczenie faktów': 'Distorting facts', 'Sugestia i niedopowiedzenie': 'Insinuation and vagueness',
    'Fałszywa przyczynowość': 'False causation', 'Liczba bez punktu odniesienia': 'Number without a baseline',
    'Wybiórcze dane': 'Selective data', 'Pominięcie kontekstu': 'Omitted context',
    'Nadmierne uogólnienie': 'Overgeneralisation', 'Etykietowanie': 'Labelling',
    'My kontra oni': 'Us versus them', 'Zmiana tematu': 'Changing the subject',
    'Odwołanie do autorytetu': 'Appeal to authority', 'Teza bez dowodu': 'Unsupported claim',
    'Przesada': 'Exaggeration', 'Apel do emocji': 'Appeal to emotion', 'Inne': 'Other',
}


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value


def csv_bytes(snapshot):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    fields = ('id', 'kind', 'date', 'camp', 'verdict', 'intensity', 'headline', 'techniques', 'vote', 'url', 'analysis_url',
              'topic', 'analysis', 'confidence', 'confidence_reason', 'corroborating_url', 'figure_id', 'diagnosis_id',
              'stance', 'ballot_id', 'vote_url', 'supporting_vote', 'data')
    writer.writerow(fields)
    rows = snapshot['rows'] + [{'id': key, 'kind': 'computed_fact', 'data': value}
                               for key, value in snapshot['facts'].items()]
    for row in rows:
        writer.writerow([safe_cell(json.dumps(row.get(key), ensure_ascii=False, sort_keys=True)
                                  if isinstance(row.get(key), (list, dict)) else row.get(key, '')) for key in fields])
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def method_text(snapshot):
    en = snapshot['language'] == 'en'
    title = 'Method and sources' if en else 'Metoda i źródła'
    lines = [title, snapshot['method'], '',
             ('Window (end exclusive): ' if en else 'Okres (koniec wyłączny): ') + snapshot['start'] + ' / ' + snapshot['end_exclusive'],
             ('Snapshot: ' if en else 'Stan danych: ') + snapshot['generated_at'],
             ('Data thresholds: ' if en else 'Progi danych: ') + '; '.join(
                 f'{label}: {snapshot["thresholds"][key]}' for key, label in (
                     [('weeks', 'complete weeks'), ('weekly_per_camp', 'diagnoses per camp per week'),
                      ('statements', 'profile statements'), ('votes', 'profile votes'), ('research', 'research diagnoses'), ('topic', 'topic records')]
                     if en else [('weeks', 'pełne tygodnie'), ('weekly_per_camp', 'diagnozy na obóz tygodniowo'),
                                 ('statements', 'wypowiedzi w profilu'), ('votes', 'głosowania w profilu'),
                                 ('research', 'diagnozy do badań'), ('topic', 'rekordy tematu')])),
             ('Threshold rationale: consecutive weeks reduce single-event effects; equal sample minima avoid '
              'one-sided comparisons. These are operational thresholds, not statistical significance or representativeness.' if en else
              'Uzasadnienie progów: kolejne tygodnie ograniczają wpływ pojedynczego wydarzenia; jednakowe minima próby '
              'ograniczają jednostronne porównania. To progi operacyjne, nie dowód istotności statystycznej ani reprezentatywności.'),
             ('The weekly minimum supports descriptive comparison across consecutive weeks. Profile minima require '
              'both statements and votes; comparison still needs a verified link. The research minimum supports '
              'aggregate distributions. Topic monitoring needs the record minimum plus at least one legislative '
              'record and one statement. No minimum number of lobbying signals is required.' if en else
              'Minimum tygodniowe służy opisowym porównaniom kolejnych tygodni. Profil wymaga zarówno wypowiedzi, '
              'jak i głosowań; ich porównanie nadal wymaga potwierdzonego powiązania. Minimum badawcze służy zestawianiu '
              'rozkładów. Monitoring wymaga wskazanej liczby rekordów, w tym co najmniej jednego projektu lub poprawki '
              'i jednej wypowiedzi. Nie wymagamy dodatniej liczby sygnałów lobbingu.'),
             *snapshot['limitations'], '', 'Sources' if en else 'Źródła']
    for row in snapshot['rows']:
        lines.append(f"{row['id']} | {row['date']} | {row.get('url', '')}")
        for key in ('corroborating_url', 'vote_url'):
            if row.get(key):
                lines.append(f"{row['id']} | {row[key]}")
    return '\n'.join(lines)


class Pages:
    def __init__(self, en):
        self.en, self.pages = en, []
        self.new()

    def new(self):
        self.image = Image.new('RGB', (WIDTH, HEIGHT), BG)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.rectangle((0, 0, WIDTH, 20), fill=ACCENT)
        self.draw.text((PAD, 57), 'spin.clinic', font=_font(23, 700), fill=INK)
        self.draw.text((WIDTH - PAD, 61), 'ANALYSIS' if self.en else 'ANALIZY',
                       font=_font(16), fill=MUTED, anchor='ra')
        self.y = 130
        self.pages.append(self.image)

    def need(self, height):
        if self.y + height > HEIGHT - 120:
            self.new()

    def text(self, text, size=22, bold=False, color=INK):
        # Split long identifiers/URLs instead of clipping or silently truncating them.
        text = str(text).replace('—', '-').replace('–', '-')
        font = _font(size, 700 if bold else 500)
        for paragraph in text.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = (line + ' ' + word).strip()
                if self.draw.textlength(candidate, font=font) > WIDTH - 2 * PAD and line:
                    self._line(line, font, size, color)
                    line = ''
                for char in word:
                    candidate = line + char
                    if self.draw.textlength(candidate, font=font) > WIDTH - 2 * PAD:
                        self._line(line, font, size, color)
                        line = ''
                    line += char
                line += ' '
            self._line(line.strip(), font, size, color)
        self.y += 4

    def _line(self, line, font, size, color):
        self.need(size + 14)
        self.draw.text((PAD, self.y), line, font=font, fill=color, anchor='lt')
        self.y += size + 10

    def heading(self, text):
        self.need(125)
        self.y += 16
        self.text(text, 29, True)

    def chart(self, aggregates):
        self.need(300)
        self.heading('Weighted spin index' if self.en else 'Wskaźnik ważony spinu')
        for camp, title in [('government', 'Government' if self.en else 'Rządzący'),
                            ('opposition', 'Opposition' if self.en else 'Opozycja')]:
            values = aggregates[camp]
            self.text(f"{title}  |  n = {values['count']}", 22, True)
            x, right = PAD + 250, WIDTH - PAD - 110
            self.draw.rectangle((x, self.y, right, self.y + 24), fill='#e9edf2')
            value = values['weighted_spin']
            if value is not None:
                self.draw.rectangle((x, self.y, x + (right - x) * value, self.y + 24), fill=ACCENT)
            self.draw.text((right + 20, self.y), '-' if value is None else f'{value * 100:.1f}%', font=_font(22), fill=INK)
            self.y += 54
        for value in (0, 50, 100):
            self.draw.text((x + (right - x) * value / 100, self.y), f'{value}%',
                           font=_font(17), fill=MUTED, anchor='mt')
        self.y += 32

    def finish(self):
        for i, page in enumerate(self.pages, 1):
            draw = ImageDraw.Draw(page)
            draw.line((PAD, HEIGHT - 90, WIDTH - PAD, HEIGHT - 90), fill='#dce2e9', width=2)
            draw.text((PAD, HEIGHT - 66), 'spin.clinic | ' + ('Selected analyses' if self.en else 'Analizy wybranej próby'),
                      font=_font(16), fill=MUTED)
            draw.text((WIDTH - PAD, HEIGHT - 66), f'{i} / {len(self.pages)}', font=_font(16), fill=MUTED, anchor='ra')
        return self.pages


def render_pages(snapshot, draft):
    en = snapshot['language'] == 'en'
    pages = Pages(en)
    pages.text('Weekly briefing' if en else dict(REPORT_TYPES)[snapshot['kind']], 42, True)
    if snapshot['facts'].get('person'):
        pages.text(snapshot['facts']['person']['canonical_name'], 28, True)
    pages.text(f"{snapshot['start']} / {snapshot['end_exclusive']} " + ('(end exclusive)' if en else '(koniec wyłączny)'), 20, color=MUTED)
    if snapshot.get('synthetic'):
        pages.text('SYNTHETIC TEST DATA' if en else 'DANE SYNTETYCZNE - PRZYKŁAD TESTOWY', 23, True, '#9b3a2f')
    pages.heading('Overview' if en else 'Podsumowanie')
    for row in draft['sentences']:
        pages.text(row['text'])
        pages.text('[' + ', '.join(row['fact_ids']) + ']', 16, color=MUTED)
    if snapshot['kind'] != 'topic':
        pages.chart(snapshot['aggregates'])
        pages.text('The index is not the share of posts containing spin.' if en else
                   'Wskaźnik nie jest odsetkiem wpisów ze spinem.', 18, color=MUTED)
    camps = [] if snapshot['kind'] == 'topic' else [('government', 'Government' if en else 'Rządzący'), ('opposition', 'Opposition' if en else 'Opozycja')]
    for camp, label in camps:
        values = snapshot['aggregates'][camp]
        pages.heading(label)
        pages.text(('Average intensity: ' if en else 'Średnia siła: ') + str(values['average_intensity']) + ' / 100')
        for verdict, n in sorted(values['verdicts'].items()):
            names = {'spin': 'Spin', 'partial': 'Partial spin' if en else 'Częściowy spin',
                     'no_spin': 'No spin' if en else 'Bez spinu', 'unclear': 'Unclear' if en else 'Nie da się ocenić'}
            pages.text(f"{names.get(verdict, verdict)}: {n}", 20)
            pages.draw.rectangle((WIDTH - PAD - 35, pages.y - 36, WIDTH - PAD - 15, pages.y - 16),
                                 fill=VERDICT_COLORS.get(verdict, '#8b9097'))
        pages.text(('Techniques: ' if en else 'Techniki: ') +
                   ', '.join(f'{TECHNIQUES_EN[k] if en else k}: {v}' for k, v in sorted(values['techniques'].items())), 20)
        pages.need(160)
        pages.text('Highest intensity diagnoses' if en else 'Najsilniejsze diagnozy', 22, True)
        for row in snapshot['facts'].get('top:' + camp, []):
            pages.text(f"{row['date']} | {row['id']} | {row['intensity']}/100", 20)
            pages.draw.rectangle((WIDTH - PAD - 35, pages.y - 36, WIDTH - PAD - 15, pages.y - 16),
                                 fill=strength_color(row['intensity']))
            if row.get('headline') and not en:
                pages.text(row['headline'], 18, color=MUTED)
    # The short English brief shares the full evidence CSV; no unreviewed AI translations.
    if not en:
        if snapshot['kind'] == 'topic':
            from news.report_models import ReportObservation
            facts = snapshot['facts']['topic']
            pages.heading('Zakres monitoringu: ' + facts['topic'])
            kinds = dict(ReportObservation.KINDS)
            for kind, n in sorted(facts['counts'].items()):
                pages.text(f'{kinds[kind]}: {n}', 22, True)
                pages.need(40)
                pages.draw.rectangle((PAD, pages.y, PAD + 700, pages.y + 18), fill='#e9edf2')
                pages.draw.rectangle((PAD, pages.y, PAD + 700 * n / max(facts['counts'].values()), pages.y + 18), fill=ACCENT)
                pages.y += 40
            for item in facts['observations']:
                pages.heading(f"{item['date']} | {kinds[item['kind']]} [{item['id']}]")
                pages.text(item['analysis'])
                certainty = {'low': 'niska', 'medium': 'umiarkowana', 'high': 'wysoka'}[item['confidence']]
                pages.text(f"Pewność: {certainty}. {item['confidence_reason']}", 18, color=MUTED)
        for key, fact in snapshot['facts'].items():
            if key.startswith('message:'):
                pages.heading(f"{fact['date']} | " + ('Rządzący' if fact['camp'] == 'government' else 'Opozycja'))
                pages.text(fact['thesis'] or 'Brak ustrukturyzowanej tezy.')
                pages.text('Wątki: ' + json.dumps(fact['themes'], ensure_ascii=False), 20)
                pages.text('Ton: ' + json.dumps(fact['tone'], ensure_ascii=False) if fact['tone'] else 'Brak pełnej klasyfikacji tonu.', 20)
        if 'profile' in snapshot['facts']:
            pages.heading('Historia wypowiedzi i głosowania')
            pages.text('Chronologia i identyfikatory źródeł znajdują się w CSV. ' +
                       'Głosowania: ' + json.dumps(snapshot['facts']['profile']['votes'], ensure_ascii=False))
            for row in snapshot['facts']['profile']['unavailable']:
                pages.text(f"Wpis niedostępny od {row['date']}. Przyczyna nieustalona. [{row['id']}]", 20)
            for row in snapshot['facts']['profile']['interviews']:
                pages.text(f"Wywiad {row['date']}: {row['headline']} [{row['id']}]", 20)
            comparisons = snapshot['facts']['profile_comparisons']
            stances = {'support': 'poparcie', 'oppose': 'sprzeciw', 'neutral': 'neutralne'}
            pages.heading('Zmiany stanowiska i zgodność z głosowaniem')
            for row in comparisons['position_changes']:
                pages.text(f"{row['date']}: {stances[row['from']]} - {stances[row['to']]} "
                           f"[{row['from_id']}, {row['to_id']}]", 20)
            labels = {'consistent': 'Zgodne', 'different': 'Rozbieżne', 'unassessed': 'Nieocenione'}
            for label, n in comparisons['alignment_counts'].items():
                pages.text(f'{labels[label]}: {n}', 20)
            if not comparisons['position_changes'] and not comparisons['vote_alignment']:
                pages.text('Brak zweryfikowanych porównań w próbie.', 20)
    pages.new()
    method = method_text(snapshot)
    for i, paragraph in enumerate(method.splitlines()):
        pages.text(paragraph, 30 if i == 0 else 18, i == 0)
    return pages.finish()


def render(snapshot, draft):
    pages = render_pages(snapshot, draft)
    output = io.BytesIO()
    pages[0].save(output, format='PDF', save_all=True, append_images=pages[1:], resolution=150,
                  title='spin.clinic - ' + dict(REPORT_TYPES)[snapshot['kind']], author='spin.clinic')
    return output.getvalue(), csv_bytes(snapshot), method_text(snapshot)

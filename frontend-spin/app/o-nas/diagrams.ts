/**
 * Schematy strony „O nas” rysowane znakami (| _ - + o). Ramki i tabele składamy z dopełnianych
 * linii, dlatego zawsze się domykają — także z polskimi znakami (każdy to jeden znak w foncie
 * o stałej szerokości). Treść jest przykładowa, bez prawdziwych publikacji.
 */

/** Ramka: ` ___ ` u góry, `|  tekst  |` w środku, `|___|` na dole. */
export function frame(lines: string[], width = Math.max(...lines.map((line) => line.length)) + 6, indent = ''): string {
  const inner = width - 2;
  const body = lines.map((line) => `${indent}|  ${line.padEnd(inner - 2)}|`);
  return [`${indent} ${'_'.repeat(inner)}`, ...body, `${indent}|${'_'.repeat(inner)}|`].join('\n');
}

/** Tabela z kolumnami o stałej szerokości. */
export function table(head: string[], rows: string[][], widths: number[]): string {
  const cells = (values: string[]) => values.map((value, index) => ` ${value.padEnd(widths[index] - 1)}`).join('|') + '|';
  const rule = widths.map((width) => '-'.repeat(width)).join('+') + '+';
  return [cells(head), rule, ...rows.map(cells)].join('\n');
}

/** Rząd małych boxów obok siebie. */
export function boxRow(labels: string[], size = 7, gap = ' '): string {
  const top = labels.map(() => ` ${'_'.repeat(size)} `).join(gap);
  const empty = labels.map(() => `|${' '.repeat(size)}|`).join(gap);
  const mid = labels.map((label) => `|${label.padStart(Math.floor((size + label.length) / 2)).padEnd(size)}|`).join(gap);
  const bottom = labels.map(() => `|${'_'.repeat(size)}|`).join(gap);
  return [top, empty, mid, bottom].join('\n');
}

export const BOX = frame([
  '',
  'KOMUNIKAT                     25.09, 12:00',
  'Ministerstwo Finansów',
  '',
  'Tytuł materiału — tak, jak podał go',
  'wydawca',
  '',
  '* Publiczne                  oryginał ->',
]);

export const EXPANDED = [
  frame([
    '[ miniatura ]   Tytuł materiału',
    '                Ministerstwo Finansów · 25.09 · oryginał ->',
    '                Krótki opis, jeśli wydawca go udostępnia',
  ]),
  '',
  '  1. OŚ CZASU — 15 najważniejszych powiązanych, od najnowszego ->',
  '',
  '  o---------o---------O---------o---------o---------o------ ->',
  '  25.09     24.09     23.09     22.09     20.09     18.09',
  '                      ^',
  '                      otwarty box stoi na swoim miejscu na osi',
  '',
  '  2. REAKCJE    + przydatne 12    - nieprzydatne 3    komentarze 7',
  '',
  '  3. BAZA POWIĄZANYCH — kolumny: kategorie, wiersze: daty',
  '',
  table(
    ['', 'Artykuł', 'Film', 'Publiczne', 'Reportaż'],
    [
      ['25.09', '[box]', '', '[box]', ''],
      ['24.09', '[box]', '[box]', '', ''],
      ['23.09', '', '', '[box] [box]', '[box]'],
      ['...', '', '', '', ''],
    ],
    [8, 10, 8, 13, 10],
  )
    .split('\n')
    .map((line) => `  ${line}`)
    .join('\n'),
].join('\n');

export const NEWS_THREAD = [
  '  TWOJA NITKA  hasło: "Sejm" · kategoria: Publiczne · źródła: wszystkie     1 z 5',
  '',
  boxRow(['box', 'box', 'box', 'box', 'box'])
    .split('\n')
    .map((line, index) => `  ${line}${index === 2 ? '   ->  przewijasz w bok' : ''}`)
    .join('\n'),
].join('\n');

export const CONTEXT_THREAD = [
  '  NITKA KONTEKSTOWA · Dr. Spin',
  '',
  frame(['BOX OTWIERAJĄCY', 'to, co chcemy pokazać, wyjaśnić', 'albo wypromować'], 38, '  '),
  '                   |',
  '                   +-- 12.09  dokument źródłowy',
  '                   |          „tu zaczyna się sprawa”',
  '                   |',
  '                   +-- 14.09  komunikat ministerstwa',
  '                   |',
  '                   +-- 15.09  wywiad',
  '                   |          „co zmieniło się po rozmowie”',
  '                   |',
  "                   '-- 17.09  artykuł",
].join('\n');

export const DR_SPIN = [
  '  [ przekazy dnia partii ]        [ najczęściej powtarzane spiny ]',
  '               \\                          /',
  '                v                        v',
  '            [   Dr. Spin: programy + modele AI   ]',
  '                            |',
  '          szuka w bazie źródeł materiałów, które:',
  '        potwierdzają  ·  podważają  ·  wyjaśniają',
  '                            |',
  '                            v',
  '            [   redakcja sprawdza i zatwierdza   ]',
  '                            |',
  '                            v',
  '            [   nitka kontekstowa na stronie     ]',
].join('\n');

export const DR_SPIN_LATER = [
  '  materiał',
  '    |',
  '    +-- osoby wymienione w materiale',
  '          |',
  '          +-- rejestr osób publicznych',
  '                |',
  '                +-- funkcje i stanowiska publiczne (z datami)',
  '                +-- spółki, fundacje, stowarzyszenia (rejestry publiczne)',
  '                +-- powiązane osoby i podmioty',
  '                |',
  "                '-- każde połączenie z odnośnikiem do źródła",
].join('\n');

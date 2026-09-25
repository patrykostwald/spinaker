/**
 * Schematy strony „O nas” rysowane znakami (| _ - + o). Ramki składamy z dopełnianych linii,
 * dlatego zawsze się domykają — także z polskimi znakami (każdy to jeden znak w foncie
 * o stałej szerokości). Treść jest przykładowa, bez prawdziwych publikacji.
 */

/** Ramka: ` ___ ` u góry, `|  tekst  |` w środku, `|___|` na dole. */
export function frame(lines: string[], width = Math.max(...lines.map((line) => line.length)) + 6, indent = ''): string {
  const inner = width - 2;
  const body = lines.map((line) => `${indent}|  ${line.padEnd(inner - 2)}|`);
  return [`${indent} ${'_'.repeat(inner)}`, ...body, `${indent}|${'_'.repeat(inner)}|`].join('\n');
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

export const CLINIC = [
  '  nowy post polityka na X  (konto potwierdzone oficjalnym dowodem)',
  '                |',
  '                v',
  '  [ selekcja: czy jest teza do oceny? ] -- nie --> pomijamy',
  '                | tak                              (życzenia, zapowiedzi)',
  '                v',
  '  [ Dr. Spin (AI): techniki z cytatami, twierdzenia ze źródłami ]',
  '                |',
  '                v',
  '  [ człowiek: zatwierdza albo odrzuca — bez zmian w treści ]',
  '                |',
  '                v',
  '  [ Klinika: karta diagnozy · waga · reakcje czytelników ]',
].join('\n');

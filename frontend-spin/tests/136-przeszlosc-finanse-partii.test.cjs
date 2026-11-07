// przeszłość.today: strona „Finanse partii i komitetów” (app/przeszlosc/FinansePartii.tsx), 6.11.2026.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const c = read('app/przeszlosc/FinansePartii.tsx');

test('strona nie jest indeksowana i używa wspólnego paska i stopki', () => {
  assert.match(read('app/przeszlosc/finanse-partii/page.tsx'), /robots: \{ index: false, follow: false \}/);
  assert.match(read('app/przeszlosc/finanse-partii/FinansePartiiPage.tsx'), /<Bar \/>[\s\S]*<FinansePartii \/>[\s\S]*<Foot \/>/);
});

test('zapytania do API: szukanie, rodzaj, tylko z kwotami i stronicowanie', () => {
  assert.match(c, /\/api\/przeszlosc\/pkw\//);
  for (const key of ["p.set('q', q)", "p.set('rodzaj', kind)", "p.set('z_danymi', '1')", 'na_strone']) assert.ok(c.includes(key), key);
});

test('karta: decyzja i kwoty z cytatem w podpowiedzi, powód braku odczytu, zawsze odnośnik do oryginału', () => {
  assert.match(c, /title=\{a\.quote \? `Z uchwały: „\$\{a\.quote\}”` : undefined\}/);
  assert.match(c, /Nie odczytujemy kwot z tego pliku: \{r\.report\.reason\}/);
  assert.match(c, /Oryginał \(PDF\) na pkw\.gov\.pl/);
  assert.match(c, /rel="noopener noreferrer"/);
});

test('bez danych osobowych: komponent nie ma pól na nazwiska darczyńców ani numery rachunków', () => {
  assert.ok(!/account_number|donor_name|numer rachunku/i.test(c));
});

test('etykiety stanu karty i data wgrania pliku (nie data sprawozdania)', () => {
  for (const key of ["text: 'z kwotami'", "'skan'", "text: 'do odczytu'", 'px-fp__state', 'plik wgrany na stronę PKW']) assert.ok(c.includes(key), key);
});

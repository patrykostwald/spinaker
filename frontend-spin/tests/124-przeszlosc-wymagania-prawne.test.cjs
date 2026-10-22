// Wymagania prawne przeszłość.today (docs/PROJEKTANT_WYMAGANIA_PRAWNE.md, 13.10.2026): drzewo pieniędzy po przebudowie v3
// musi pokazywać gałąź "Dotacje (unijne i krajowe)", źródło każdego wiersza (FTS / NIW-CRSO), licencje w stopce gałęzi,
// dopisek przy wierszu NIW (attribution), dopiski zbiorcze grants.sums_note / grants.note / people.note, kwoty PLN i EUR
// osobno, bez słów sugerujących zależność i bez strzałek przyczynowych; stan pusty z opisem (bez zer udających pomiar).
// Render: TreeView z fikstury w kształcie GET /api/przeszlosc/spolka/0000037027/ (organizacja z dotacjami NIW), react-dom/server.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.join(__dirname, '..');
const cache = new Map();
function load(file) {
  const abs = path.resolve(file);
  if (cache.has(abs)) return cache.get(abs).exports;
  const src = fs.readFileSync(abs, 'utf8');
  const out = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  cache.set(abs, module);
  const req = name => {
    if (name.endsWith('.css')) return {};
    if (name === 'react' || name === 'react/jsx-runtime') return require(name);
    if (name === '@spin-clinic/ui/kit') return { Loading: () => null };
    if (name === '@spin-clinic/ui') return { useFeature: () => false };
    if (name.startsWith('.')) {
      const base = path.resolve(path.dirname(abs), name);
      const hit = ['.tsx', '.ts', '/index.tsx', '/index.ts'].map(x => base + x).find(f => fs.existsSync(f));
      if (hit) return load(hit);
    }
    return {};
  };
  vm.runInNewContext(out, { module, exports: module.exports, require: req, process: { env: {} }, console, URL, Intl, Date, Math, JSON, setTimeout, clearTimeout, window: undefined, document: undefined });
  return module.exports;
}

const fixture = () => ({
  organisation: { id: 1, name: 'Fundacja Przykładowa', kind: 'foundation', krs_number: '0000037027', nip: '1234567890', regon: '123456789', url: 'https://rejestr.io/krs/37027' },
  identifiers_missing: false,
  contracts: { count: 0, sums: [], results: [], suspect_count: 0 },
  grants: {
    count: 2,
    sums: [{ currency: 'PLN', total: 150000 }, { currency: 'EUR', total: 20000 }],
    sums_note: 'Środki krajowe, unijne i z 1,5% PIT pokazujemy osobno i nie sumujemy.',
    note: 'Plik NIW-CRSO, stan na 30.09.2026.',
    results: [
      { id: 'niw:1', source: 'niw', title: 'Wsparcie wolontariatu', programme: 'FIO', amount: 150000, currency: 'PLN', date: '2026-03-01', year: 2026, url: 'https://niw.gov.pl/', matched_by: 'KRS',
        attribution: 'Źródło: NIW-CRSO, stan pliku 30.09.2026; opracowanie iapply, nie jest publikacją NIW; kwota wynika z umowy i nie oznacza wypłaty.', beneficiary: 'Fundacja Przykładowa', contract_no: 'FIO/1', file_date: '2026-09-30' },
      { id: 'fts:2', source: 'fts', title: 'Projekt unijny', programme: 'ESF', amount: 20000, currency: 'EUR', date: '2025-05-01', year: 2025, url: 'https://ec.europa.eu/', matched_by: 'NIP' },
    ],
  },
  people: { count: 0, results: [], note: 'Powiązanie z rejestrów jawnych, nie oznacza decyzji ani zależności; daty roli i umowy pokazujemy obok siebie.' },
  unlinked: { count: 0, results: [] },
  sources: [{ key: 'fts', label: 'FTS', url: 'https://ec.europa.eu/budget/financial-transparency-system/', license: 'CC BY 4.0' }, { key: 'niw', label: 'NIW-CRSO', url: 'https://niw.gov.pl/', license: 'informacja publiczna' }],
  note: 'Dane z rejestrów publicznych.',
  generated_at: '2026-10-13T12:00:00+02:00',
  access: { beta: true, locked: [] },
});

function render(data) {
  const { TreeView } = load(path.join(root, 'app/przeszlosc/DrzewoPieniedzy.tsx'));
  return renderToStaticMarkup(React.createElement(TreeView, { data, lines: false }));
}

test('gałąź "Dotacje (unijne i krajowe)", źródło wiersza i licencje w stopce gałęzi', () => {
  let html;
  try { html = render(fixture()); } catch (e) { assert.fail('render TreeView: ' + e.message); }
  assert.match(html, /Dotacje \(unijne i krajowe\)/);
  assert.doesNotMatch(html, /Dotacje UE|dotacje UE/);
  assert.match(html, /NIW-CRSO/);
  assert.match(html, /FTS/);
  assert.match(html, /informacja publiczna/);
});

// nb() wstawia twarde spacje po jednoliterowych słowach - porównujemy tekst ze zwykłymi spacjami
const text = html => html.replace(/\u00a0/g, ' ');

test('dopisek przy wierszu NIW i dopiski zbiorcze widoczne', () => {
  const html = text(render(fixture()));
  assert.match(html, /opracowanie iapply, nie jest publikacją NIW/);
  assert.match(html, /kwota wynika z umowy i nie oznacza wypłaty/);
  assert.match(html, /pokazujemy osobno i nie sumujemy/);
  assert.match(html, /stan na 30\.09\.2026/);
  assert.match(html, /nie oznacza decyzji ani zależności/);
});

test('PLN i EUR osobno, bez słów sugerujących zależność i bez strzałek przyczynowych', () => {
  const html = text(render(fixture()));
  // sumLine: każda waluta osobno ("150 tys. zł + 20 tys. €"), nigdy jedna przeliczona suma
  assert.match(html, /150 tys\. zł/);
  assert.match(html, /20 tys\. €/);
  assert.doesNotMatch(html, /170 (tys|000)/, 'brak sumy walut');
  // słowa zależności poza dosłownym dopiskiem prawnym API ("nie oznacza decyzji ani zależności")
  const bez = html.replace(/nie oznacza decyzji ani zależności/g, '');
  assert.doesNotMatch(bez, /zależn|związan[yaei] z/i);
  assert.doesNotMatch(html, /[⇒⟶➔→]\s*(dotacj|zamówie|pieni)/i);
});

test('stan pusty z opisem, bez zer udających pomiar', () => {
  const d = fixture();
  d.grants = { count: 0, sums: [], results: [] };
  const html = render(d);
  assert.match(html, /Brak rekordów po identyfikatorach podmiotu\./);
});

test('profil osoby i strona podmiotu: etykieta dotacji unijnych i krajowych', () => {
  const src = fs.readFileSync(path.join(root, 'app/przeszlosc/PersonProfile.tsx'), 'utf8') + fs.readFileSync(path.join(root, 'app/przeszlosc/spolka/[krs]/page.tsx'), 'utf8') + fs.readFileSync(path.join(root, 'app/przeszlosc/najwazniejsze-dane.ts'), 'utf8');
  assert.doesNotMatch(src, /dotacje UE|Dotacje UE/);
  assert.match(src, /dotacje \(unijne i krajowe\)|dotacje \(UE: FTS; krajowe: NIW-CRSO\)/);
});
test('opp_tax: osobny blok "1,5% podatku (wskazanie podatników)" poza gałęzią dotacji; dopiski, źródło MF CC0, bez sumowania; stan pusty z opisem', () => {
  const d = fixture();
  d.opp_tax = { count: 2, note: 'Kwoty z 1,5% podatku to wskazania podatników, nie decyzje organu i nie dotacje; pokazujemy je osobno i nie sumujemy z dotacjami krajowymi ani unijnymi.',
    results: [
      { id: 'mf_opp:1', tax_year: 2024, payment_year: 2025, amount: 10000, currency: 'PLN', source: 'mf_opp', url: 'https://www.podatki.gov.pl/', attribution: 'Źródło: Ministerstwo Finansów, wykaz OPP, rok podatkowy 2024, stan na 2025-09-30. Kwota pochodzi z 1,5% podatku wskazanego przez podatników, nie jest dotacją i nie sumuje się z dotacjami.' },
      { id: 'mf_opp:2', tax_year: 2023, payment_year: 2024, amount: 5000, currency: 'PLN', source: 'mf_opp', url: 'https://www.podatki.gov.pl/', attribution: 'Źródło: Ministerstwo Finansów, wykaz OPP, rok podatkowy 2023.' }] };
  d.sources.push({ key: 'mf_opp', label: 'Ministerstwo Finansów, wykaz OPP', url: 'https://www.podatki.gov.pl/', license: 'CC0 1.0' });
  const html = text(render(d));
  const block = html.slice(html.indexOf('1,5% podatku (wskazanie podatników)'));
  assert.ok(html.includes('1,5% podatku (wskazanie podatników)'), 'tytuł bloku dokładnie');
  const grantsBranch = html.slice(html.indexOf('Dotacje (unijne i krajowe)'), html.indexOf('Osoby z funkcjami w KRS'));
  assert.doesNotMatch(grantsBranch, /mf_opp|wykaz OPP|1,5% podatku \(wskazanie/, 'OPP nie w gałęzi dotacji');
  assert.match(block, /nie jest dotacją i nie sumuje się z dotacjami/);
  assert.match(block, /pokazujemy je osobno i nie sumujemy/);
  assert.match(block, /CC0 1\.0/);
  assert.match(block, /rok podatkowy 2024 · wypłata w 2025/);
  assert.match(block, /rok podatkowy 2023 · wypłata w 2024/);
  assert.doesNotMatch(block, /15 tys/, 'lata OPP nie sumowane');
  assert.match(html, /150 tys\. zł \+ 20 tys\. €/, 'suma dotacji bez OPP');
  const empty = fixture(); empty.opp_tax = { count: 0, results: [], note: d.opp_tax.note };
  assert.match(text(render(empty)), /Brak w naszych danych wskazań 1,5% podatku/);
});
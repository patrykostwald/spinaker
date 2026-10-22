// Decyzje właściciela 13.10.2026 (API-v3 sekcja 0): (a) klauzula RODO art. 14 i formularz sprzeciwu, (b) odpowiedź osoby
// pod parą "Wcześniej i teraz", (c) kafel oświadczeń majątkowych z listy API, (d) wykaz OPP z 1,5% podatku w drzewie pieniędzy.
// Funkcje czyste + render react-dom/server z fikstur w kształcie kontraktu; bez nowych pakietów.
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
  const out = ts.transpileModule(fs.readFileSync(abs, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
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
  vm.runInNewContext(out, { module, exports: module.exports, require: req, process: { env: {} }, console, URL, Intl, Date, Math, JSON, setTimeout, clearTimeout });
  return module.exports;
}
const text = html => html.replace(/ /g, ' ');
const P = f => path.join(root, 'app/przeszlosc', f);

const NOTICE = { version: 'art14-szkic-1', date: '2026-10-13', status: 'szkic do prawnika', title: 'Informacja o danych (RODO, art. 14)',
  sections: [{ heading: 'Kto przetwarza dane', text: 'Administrator: operator serwisu.' }, { heading: 'Puste', text: '   ' }],
  objection_url: '/api/przeszlosc/osoba/241-monika-rosa/sprzeciw/', contact: 'kontakt@iapply.pl' };

test('(a) klauzula: zwinięta jedna linia z wersją, datą i statusem; sekcje z treścią; formularz tylko z adresem serwisu', () => {
  const d = load(P('informacja-dane.ts'));
  assert.equal(d.noticeLine(NOTICE), 'Informacja o danych (RODO, art. 14) (wersja art14-szkic-1, z 2026-10-13, szkic do prawnika)');
  assert.equal(d.noticeSections(NOTICE).length, 1);
  assert.equal(d.objectionUrl(NOTICE), '/api/przeszlosc/osoba/241-monika-rosa/sprzeciw/');
  assert.equal(d.objectionUrl({ objection_url: 'javascript:alert(1)' }), null);
  assert.equal(d.objectionUrl({ objection_url: '//evil.example/x' }), null);
  const { InformacjaODanych } = load(P('InformacjaODanych.tsx'));
  const html = text(renderToStaticMarkup(React.createElement(InformacjaODanych, { notice: NOTICE })));
  assert.match(html, /<details class="pt-info"/);
  assert.doesNotMatch(html, /<details[^>]* open/, 'domyślnie zwinięta');
  assert.match(html, /wersja art14-szkic-1/);
  assert.match(html, /Rozwiń/);
  assert.match(html, /Zgłoś sprzeciw/);
  assert.equal(renderToStaticMarkup(React.createElement(InformacjaODanych, { notice: null })), '');
});

test('(a) walidacja sprzeciwu: powód >= 20 znaków, e-mail, relacja z listy; treść wysyłki zgodna z kontraktem', () => {
  const d = load(P('informacja-dane.ts'));
  assert.match(d.objectionError('krótko', 'a@b.pl', 'osoba'), /co najmniej 20/);
  assert.match(d.objectionError('Powód dostatecznie długi, by przejść.', 'nie-email', 'osoba'), /e-mail/);
  assert.match(d.objectionError('Powód dostatecznie długi, by przejść.', 'a@b.pl', ''), /kogo dotyczy/);
  assert.equal(d.objectionError('Powód dostatecznie długi, by przejść.', 'a@b.pl', 'osoba'), null);
  assert.deepEqual(JSON.parse(JSON.stringify(d.objectionBody('  Powód  ', ' a@b.pl ', 'przedstawiciel'))), { reason: 'Powód', contact: 'a@b.pl', relation: 'przedstawiciel' });
  assert.deepEqual(JSON.parse(JSON.stringify(d.RELATIONS.map(r => r[0]))), ['osoba', 'przedstawiciel', 'inna']);
  assert.equal(d.RELATIONS[0][1], 'Dotyczy mnie');
});

test('(b) odpowiedź osoby: tekst 1-600 znaków, etykieta domyślna, data ISO; inaczej null', () => {
  const pp = load(path.join(root, '../packages/ui/src/lib/positionPairs.ts'));
  assert.deepEqual(JSON.parse(JSON.stringify(pp.normalizeResponse({ label: 'Odpowiedź osoby', text: ' Nie zmieniłem zdania, kontekst był inny. ', date: '2026-10-12' }))),
    { label: 'Odpowiedź osoby', text: 'Nie zmieniłem zdania, kontekst był inny.', date: '2026-10-12' });
  assert.equal(pp.normalizeResponse(null), null);
  assert.equal(pp.normalizeResponse({ text: '' }), null);
  assert.equal(pp.normalizeResponse({ text: 'x'.repeat(601) }), null);
  assert.equal(pp.normalizeResponse({ text: 'Krótka odpowiedź osoby.' }).label, 'Odpowiedź osoby');
});

test('(c) oświadczenia majątkowe z listy API: lata, rodzaj, data, PDF, "sprawdź w PDF"; pusta lista = stan brak danych', () => {
  const d = load(P('najwazniejsze-dane.ts'));
  const base = { generated_at: '2026-10-13T12:00:00+02:00', votes: { available: true } };
  const t = d.majatekTile({ ...base, assets_declarations: { items: [
    { year: 2024, kind: 'oswiadczenie', kind_label: 'oświadczenie', published_on: '2025-05-29', url: 'https://www.sejm.gov.pl/a.pdf', checked_at: '2026-10-12', auto_read: null },
    { year: 2025, kind: 'korekta', kind_label: 'korekta', published_on: '2026-05-30', url: 'https://www.sejm.gov.pl/b.pdf', checked_at: '2026-10-11', auto_read: { pages: 9, note: 'Odczytane automatycznie, sprawdź w PDF.' } },
  ], notice: 'Odnośniki do PDF w serwisie Sejmu; bez sum i porównań.', source: { name: 'Sejm RP', url: 'https://www.sejm.gov.pl/', license: 'informacja publiczna' } } });
  assert.equal(t.state, 'ok');
  assert.equal(t.value, '2');
  assert.equal(t.docs[0].title, '2025 · korekta', 'najnowszy rok pierwszy');
  assert.match(t.docs[0].meta, /opublikowano 30\.05\.2026 · PDF na sejm\.gov\.pl/);
  assert.match(t.docs[0].auto, /9 stron · Odczytane automatycznie, sprawdź w PDF\./);
  assert.equal(t.docs[1].auto, '');
  assert.match(t.source[0].label, /Sejm RP \(informacja publiczna\)/);
  assert.match(t.stampText, /sprawdzono 12\.10\.2026/);
  assert.doesNotMatch(JSON.stringify(t), /suma|średni|mediana|wzrost|spadek/i, 'bez sum i porównań');
  const e = d.majatekTile({ ...base, assets_declarations: { items: [] } });
  assert.equal(e.state, 'empty');
  assert.equal(e.value, 'brak w naszych danych');
  const n = d.majatekTile({ ...base, assets_declarations: null });
  assert.equal(n.state, 'empty', 'null = brak danych, kafel zostaje widoczny');
});

test('(d) wykaz OPP: osobna sekcja, kwota bez sumowania z dotacjami, dopisek i źródło MF z licencją', () => {
  const { TreeView } = load(P('DrzewoPieniedzy.tsx'));
  const data = {
    organisation: { id: 1, name: 'Fundacja Przykładowa', kind: 'foundation', krs_number: '0000037027', nip: '', regon: '', url: 'https://rejestr.io/krs/37027' },
    identifiers_missing: false, contracts: { count: 0, sums: [], results: [], suspect_count: 0 },
    grants: { count: 1, sums: [{ currency: 'PLN', total: 150000 }], results: [{ id: 'niw:1', source: 'niw', title: 'Dotacja', programme: 'FIO', amount: 150000, currency: 'PLN', date: '2026-03-01', year: 2026, url: 'https://niw.gov.pl/', matched_by: 'KRS' }], sums_note: 'Środki krajowe, unijne i z 1,5% PIT pokazujemy osobno i nie sumujemy.' },
    opp_tax: { count: 1, results: [{ id: 'mf_opp:1', tax_year: 2024, payment_year: 2025, amount: 12345.67, currency: 'PLN', source: 'mf_opp', url: 'https://www.podatki.gov.pl/', attribution: 'Źródło: Ministerstwo Finansów, wykaz OPP, rok podatkowy 2024. Kwota pochodzi z 1,5% podatku wskazanego przez podatników, nie jest dotacją i nie sumuje się z dotacjami.' }],
      note: 'Kwoty z 1,5% podatku to wskazania podatników, nie decyzje organu i nie dotacje; pokazujemy je osobno i nie sumujemy z dotacjami krajowymi ani unijnymi.' },
    people: { count: 0, results: [] }, unlinked: { count: 0, results: [] },
    sources: [{ key: 'niw', label: 'NIW-CRSO', url: 'https://niw.gov.pl/', license: 'informacja publiczna' }, { key: 'mf_opp', label: 'Ministerstwo Finansów, wykaz OPP', url: 'https://www.podatki.gov.pl/', license: 'CC0 1.0' }],
    note: 'Dane z rejestrów publicznych.', generated_at: '2026-10-13T12:00:00+02:00', access: { beta: true, locked: [] },
  };
  const html = text(renderToStaticMarkup(React.createElement(TreeView, { data, lines: false })));
  assert.match(html, /1,5% podatku \(wskazanie podatników\)/);
  assert.match(html, /rok podatkowy 2024 · wypłata w 2025/);
  assert.match(html, /nie jest dotacją i nie sumuje się z dotacjami/);
  assert.match(html, /pokazujemy je osobno i nie sumujemy/);
  assert.match(html, /CC0 1\.0/);
  // suma dotacji nie zawiera kwoty OPP (150 tys. zł, nie 162 tys.)
  assert.match(html, /150 tys\. zł/);
  assert.doesNotMatch(html, /162 tys/);
  const empty = text(renderToStaticMarkup(React.createElement(TreeView, { data: { ...data, opp_tax: { count: 0, results: [], note: data.opp_tax.note } }, lines: false })));
  assert.match(empty, /Brak w naszych danych wskazań 1,5% podatku/);
  const none = text(renderToStaticMarkup(React.createElement(TreeView, { data: { ...data, opp_tax: undefined }, lines: false })));
  assert.doesNotMatch(none, /1,5% podatku \(wskazanie/, 'brak klucza = starsze API, bez sekcji');
});

test('(3. recenzja) sprzeciw: jeden neutralny komunikat; strona potwierdzenia: 200 / 410 / 404', () => {
  const d = load(P('informacja-dane.ts'));
  assert.equal(d.OBJECTION_SENT, 'Wniosek przyjęty, sprawdź e-mail.');
  assert.equal(d.confirmMessage(410).title, 'Link wygasł lub został już użyty');
  assert.equal(d.confirmMessage(200).title, 'Sprzeciw potwierdzony');
  assert.equal(d.confirmMessage(404).title, 'Nie znaleziono linku');
  const src = fs.readFileSync(P('InformacjaODanych.tsx'), 'utf8');
  assert.match(src, /msg: OBJECTION_SENT/);
  assert.doesNotMatch(src, /body\?\.detail/, 'treść z serwera nie trafia do komunikatu');
});

test('(3. recenzja) odpowiedź osoby: "Kod z wiadomości", 404 = komunikat jak dla nieistniejącego, 403 = potwierdź adres', () => {
  const pp = load(path.join(root, '../packages/ui/src/lib/positionPairs.ts'));
  assert.match(pp.replyError('krótko', ''), /co najmniej 10/);
  assert.equal(pp.replyError('Odpowiedź dostatecznie długa.', ''), null);
  assert.match(pp.replyError('Odpowiedź dostatecznie długa.', 'kod z spacją'), /litery, cyfry/);
  assert.deepEqual(JSON.parse(JSON.stringify(pp.replyBody(' Tekst odpowiedzi osoby. ', ' AB12-CD34 '))), { text: 'Tekst odpowiedzi osoby.', token: 'AB12-CD34' });
  assert.deepEqual(JSON.parse(JSON.stringify(pp.replyBody('Tekst odpowiedzi osoby.', ''))), { text: 'Tekst odpowiedzi osoby.' });
  assert.equal(pp.replyStatusMessage(404), 'Nie znaleziono tego zestawienia.');
  assert.match(pp.replyStatusMessage(403), /kod z wiadomości/);
  const ui = fs.readFileSync(path.join(root, '../packages/ui/src/kit/PositionPairReply.tsx'), 'utf8');
  assert.match(ui, /Kod z wiadomości/);
  assert.doesNotMatch(ui, />Token</i);
});
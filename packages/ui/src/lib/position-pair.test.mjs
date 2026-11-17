// „Wcześniej i teraz” (13.10.2026): kontrakt API-v3.md sekcja 5 na froncie + komponent PositionPair.
// Uruchom: node --test src/lib/position-pair.test.mjs (z katalogu packages/ui). Transpilacja TS/TSX typescriptem z frontend-spin,
// render react-dom/server; bez nowych pakietów (wzór: v3-seria2.test.mjs).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const require = createRequire(new URL('../../../../frontend-spin/package.json', import.meta.url));
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup: render } = require('react-dom/server');
const renderToStaticMarkup = el => render(el).replace(/ /g, ' ');

function load(rel, mocks = {}, env = {}) {
  const src = readFileSync(new URL(rel, import.meta.url), 'utf8');
  const out = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  const req = name => mocks[name] ?? (name === 'react' || name === 'react/jsx-runtime' ? require(name) : {});
  vm.runInNewContext(out, { module, exports: module.exports, require: req, process: { env }, URL, Intl, Date, Number, String, Math, Set, Array, Object, JSON, console, ResizeObserver: undefined });
  return module.exports;
}

const lib = load('./positionPairs.ts', { './typography': load('./typography.ts'), './api': { apiFetch: async () => ({}), ApiError: class extends Error {} } });
const Link = ({ href, children, ...rest }) => React.createElement('a', { href, ...rest }, children);
const report = load('../kit/PositionPairReport.tsx', { '../lib/positionPairs': lib, '../lib/api': { apiWrite: async () => ({}), ApiError: class {} } });
const comp = load('../kit/PositionPair.tsx', { '../lib/positionPairs': lib, './PositionPairReport': report, 'next/link': { __esModule: true, default: Link } });

const RAW = {
  id: 17, topic: 'podatek od nieruchomości',
  a: { kind: 'wpis', kind_label: 'Wpis na X', date: '2025-03-04', quote: 'Nie podniesiemy podatku od nieruchomości w tej kadencji.', vote: null,
    source: { name: '@posel_test na X', url: 'https://x.com/posel_test/status/1', fetched_at: '2025-03-04' } },
  b: { kind: 'glos', kind_label: 'Głosowanie w Sejmie', date: '2026-09-26', quote: null, vote: 'za',
    vote_subject: 'Pkt 5. Rządowy projekt ustawy o podatkach i opłatach lokalnych - całość projektu',
    source: { name: 'Sejm RP, głosowanie 41/12 (kadencja 10)', url: 'https://www.sejm.gov.pl/glosowanie/41', fetched_at: '2026-09-26' } },
  context: 'Projekt podnosi górną stawkę podatku od nieruchomości od 2027 roku.',
  approved_at: '2026-10-13T10:02:00+02:00', ai_suggested: true,
  notice: 'Dwie wypowiedzi o tym samym temacie. Pokazujemy je obok siebie bez oceny. Sprawdź źródła i kontekst.', report_url: '/api/stanowiska/17/zgloszenie/',
};
const clone = over => ({ ...RAW, ...over });

test('normalizePair: kształt kontraktu przechodzi, braki strukturalne odrzucają parę (ta sama zasada dla każdej)', () => {
  const pair = lib.normalizePair(RAW);
  assert.equal(pair.id, 17);
  assert.equal(pair.b.vote, 'za');
  assert.equal(pair.a.source.fetched_at, '2025-03-04');
  assert.equal(lib.normalizePair(null), null);
  assert.equal(lib.normalizePair(clone({ topic: '' })), null, 'bez tematu');
  assert.equal(lib.normalizePair(clone({ id: 'x' })), null, 'zły id');
  assert.equal(lib.normalizePair(clone({ a: { ...RAW.a, date: 'wczoraj' } })), null, 'zła data');
  assert.equal(lib.normalizePair(clone({ a: { ...RAW.a, quote: '', vote: null } })), null, 'ani cytatu, ani głosu');
  assert.equal(lib.normalizePair(clone({ a: { ...RAW.a, source: { name: 'x', url: 'javascript:alert(1)' } } })), null, 'zły adres źródła');
  assert.equal(lib.normalizePair(clone({ a: { ...RAW.a, source: { name: '', url: 'https://x.com/1' } } })), null, 'bez nazwy źródła');
  assert.equal(lib.normalizePair(clone({ a: { ...RAW.b, date: '2026-10-01' }, b: { ...RAW.a, date: '2025-01-01', quote: 'x' } })), null, 'A nie może być nowsza niż B');
});

test('normalizeBlock: brak klucza = brak bloku; paused i niepoprawne pary', () => {
  assert.equal(lib.normalizeBlock(undefined), null);
  assert.equal(lib.normalizeBlock(null), null);
  const block = lib.normalizeBlock({ items: [RAW, { id: 1 }], notice: '', paused: false });
  assert.equal(block.items.length, 1);
  assert.equal(block.notice, lib.POSITION_PAIRS_NOTICE);
  assert.equal(lib.normalizeBlock({ items: [], paused: true }).paused, true);
});

test('daty po polsku i etykieta dostępności "Wcześniej: data, Teraz: data"', () => {
  const pair = lib.normalizePair(RAW);
  assert.equal(lib.pairDate('2025-03-04'), '4 marca 2025', 'twarde spacje w dacie');
  assert.equal(lib.pairAriaLabel(pair).replace(/ /g, ' '), 'Wcześniej: 4 marca 2025, Teraz: 26 września 2026');
  assert.equal(lib.pairAriaLabel(pair, ['Boks 2', 'Boks 3']).replace(/ /g, ' '), 'Boks 2: 4 marca 2025, Boks 3: 26 września 2026');
});

test('adresy: strona pary, profil osoby (kotwice), bezpieczny adres źródła, domena', () => {
  assert.equal(lib.pairDetailHref(17), '/klinika/stanowiska/17');
  assert.equal(lib.pairDetailHref(17, 74), '/klinika/stanowiska/17?osoba=74');
  assert.equal(lib.personPairsHref('74-jaroslaw-kaczynski'), '/przeszlosc/osoba/74-jaroslaw-kaczynski#wczesniej-i-teraz');
  assert.equal(lib.personPairsHref('74-x', 17), '/przeszlosc/osoba/74-x#stanowiska-17');
  assert.equal(lib.safeHttpUrl('data:text/html,x'), null);
  assert.equal(lib.safeHttpUrl('https://www.sejm.gov.pl/a'), 'https://www.sejm.gov.pl/a');
  assert.equal(lib.sourceDomain('https://www.sejm.gov.pl/a'), 'sejm.gov.pl');
});

test('PositionPair: A przed B, etykieta grupy, rodzaj, data, cytat, głos, źródło http(s) z celem w nowym oknie', () => {
  const html = renderToStaticMarkup(React.createElement(comp.PositionPair, { pair: lib.normalizePair(RAW) }));
  assert.match(html, /role="group" aria-label="Wcześniej: 4 marca 2025, Teraz: 26 września 2026"/);
  assert.ok(html.indexOf('data-side="a"') < html.indexOf('data-side="b"'), 'kolejność czytania A potem B');
  assert.match(html, /<time class="sc-pp__date" dateTime="2025-03-04">4 marca 2025<\/time>/);
  assert.match(html, /Wpis na X/);
  assert.match(html, /Głosowanie w Sejmie/);
  assert.match(html, /Nie podniesiemy podatku od nieruchomości w tej kadencji\./);
  assert.match(html, /Głos: <b>za<\/b>/);
  assert.match(html, /Pkt 5\. Rządowy projekt ustawy/);
  assert.match(html, /href="https:\/\/x\.com\/posel_test\/status\/1" target="_blank" rel="noopener noreferrer"/);
  assert.match(html, />x\.com<i/);
  assert.match(html, /inaczej niż/);
  assert.match(html, /Kontekst:<\/b> Projekt podnosi/);
  assert.match(html, /Zgłoś błąd lub sprostowanie/);
  assert.match(html, /Dwie wypowiedzi o tym samym temacie\. Pokazujemy je obok siebie bez oceny\. Sprawdź źródła i kontekst\./);
});

test('PositionPair: bez kolorów ostrzegawczych, słów oceniających, licznika i rankingu', () => {
  const html = renderToStaticMarkup(React.createElement(comp.PositionPair, { pair: lib.normalizePair(RAW) }));
  assert.doesNotMatch(html, /style=/i, 'żadnych kolorów w atrybucie style');
  assert.doesNotMatch(html, /hipokryt|kłamst|sprzecz|przeczy|zmienił zdanie|ostrzeż|uwaga|fałsz|zdrad/i);
  assert.doesNotMatch(html, /data-tone|warning|negative/i);
  const css = readFileSync(new URL('../kit/position-pair.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /--sc-(negative|warning|positive|live|spin-|fam-)/, 'tokeny ostrzegawcze zakazane');
  assert.doesNotMatch(css, /border:\s*1px solid var\(--sc-line\)/, 'boksy bez obrysów');
});

test('PositionPairs: lista bez licznika i rankingu, zdanie o kompletności, cisza wyborcza = tylko informacja', () => {
  const pair = lib.normalizePair(RAW);
  const html = renderToStaticMarkup(React.createElement(comp.PositionPairs, { block: { items: [pair, { ...pair, id: 18 }], notice: pair.notice, paused: false } }));
  assert.match(html, /<h2[^>]*>Wcześniej i teraz<\/h2>/);
  assert.equal((html.match(/data-pair="/g) || []).length, 2);
  assert.equal((html.match(/Dwie wypowiedzi o tym samym temacie\./g) || []).length, 1, 'zdanie nad listą raz, nie przy każdej parze');
  assert.match(html, /Brak zestawienia nie oznacza, że wypowiedzi się nie różnią\./);
  assert.match(html, /id="stanowiska-17"/);
  assert.doesNotMatch(html, /\d+\s+(par|zestawień|wypowiedzi różni)/i, 'bez licznika');
  const paused = renderToStaticMarkup(React.createElement(comp.PositionPairs, { block: { items: [], notice: '', paused: true } }));
  assert.match(paused, /wstrzymane na czas ciszy wyborczej/);
  assert.doesNotMatch(paused, /data-pair/);
  assert.equal(renderToStaticMarkup(React.createElement(comp.PositionPairs, { block: { items: [], notice: '', paused: false } })), '', 'bez par nic');
});

test('PositionPairsNote: jedna linia tylko gdy para istnieje', () => {
  const none = renderToStaticMarkup(React.createElement(comp.PositionPairsNote, { pairs: [], person: 74, detailHref: lib.pairDetailHref }));
  assert.equal(none, '');
  const one = renderToStaticMarkup(React.createElement(comp.PositionPairsNote, { pairs: [{ id: 17, topic: 'podatek' }], person: 74, detailHref: lib.pairDetailHref }));
  assert.match(one, /Ta osoba wypowiadała się wcześniej na ten temat:/);
  assert.match(one, /href="\/klinika\/stanowiska\/17\?osoba=74"/);
});

test('PositionPairReport: przycisk "Zgłoś błąd lub sprostowanie", formularz dopiero po kliknięciu (procedura z kontraktu)', () => {
  const html = renderToStaticMarkup(React.createElement(report.PositionPairReport, { pair: { id: 17, topic: 't', report_url: '/api/stanowiska/17/zgloszenie/' } }));
  assert.match(html, /<button[^>]*aria-haspopup="dialog"[^>]*>Zgłoś błąd lub sprostowanie<\/button>/);
  assert.doesNotMatch(html, /<dialog/);
  const src = readFileSync(new URL('../kit/PositionPairReport.tsx', import.meta.url), 'utf8');
  assert.match(src, /pair\.report_url/);
  assert.match(src, /reason: reason\.trim\(\), contact: contact\.trim\(\), is_subject: subject/);
});

test('flaga: domyślnie wyłączona w features.ts; wiązanie z NEXT_PUBLIC_POSITION_PAIRS', () => {
  const src = readFileSync(new URL('./features.ts', import.meta.url), 'utf8');
  assert.match(src, /POSITION_PAIRS_ENABLED: process\.env\.NEXT_PUBLIC_POSITION_PAIRS === 'true'/);
});

test('spinka: łącznik "przeczy" ma w interfejsie nazwę "inaczej niż" (typ w danych bez zmian)', () => {
  const steps = readFileSync(new URL('../components/community/ThreadSteps.tsx', import.meta.url), 'utf8');
  const strip = readFileSync(new URL('../components/community/ThreadStrip.tsx', import.meta.url), 'utf8');
  assert.match(steps, /przeczy: 'inaczej niż'/);
  assert.match(strip, /przeczy: 'inaczej niż'/);
  assert.match(steps, /przeczy: 'not'/, 'klucz danych zostaje');
});

test('PositionPair: odpowiedź osoby pod parą (decyzja właściciela 13.10) - etykieta z datą, tekst, bez kolorów stron; null = brak bloku', () => {
  const withResp = lib.normalizePair({ ...RAW, subject_response: { label: 'Odpowiedź osoby', text: 'Kontekst obu wypowiedzi był inny.', date: '2026-10-12' } });
  const html = renderToStaticMarkup(React.createElement(comp.PositionPair, { pair: withResp })).replace(/\u00a0/g, ' ');
  assert.match(html, /class="sc-pp__resp"/);
  assert.match(html, /Odpowiedź osoby, /);
  assert.match(html, /Kontekst obu wypowiedzi był inny\./);
  assert.ok(html.indexOf('sc-pp__resp') > html.indexOf('data-pp="b"') || html.indexOf('sc-pp__resp') > html.lastIndexOf('sc-pp__side'), 'pod parą');
  assert.doesNotMatch(html.slice(html.indexOf('sc-pp__resp')), /data-side|--sc-side/);
  const none = renderToStaticMarkup(React.createElement(comp.PositionPair, { pair: lib.normalizePair({ ...RAW, subject_response: null }) }));
  assert.doesNotMatch(none, /sc-pp__resp/);
});
// przeszłość.today v3 (13.10.2026): lista głosowań Sejmu i sieć powiązań osoby - funkcje czyste (app/przeszlosc/glosowania-lista.ts)
// oraz kontrola kształtu plików. Bez nowych pakietów: TS przez typescript.transpileModule, jak w teście 117.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const eq = (a, b, m) => assert.equal(JSON.stringify(a), JSON.stringify(b), m);
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
function load(file) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: () => ({}), URL, URLSearchParams, Intl, Number, String, Map, Set, Date });
  return exports;
}
const L = load('app/przeszlosc/glosowania-lista.ts');

const vote = (over = {}) => ({ id: '10/1/1', term: 10, sitting: 1, number: 1, title: 'Pkt. 1 Ustawa', motion: 'wniosek', date: '2026-09-26', kind: 'ELECTRONIC',
  result: { yes: 200, no: 230, abstain: 0, notParticipating: 30 }, majority: null, outcome: 'nieustalone', url: 'https://www.sejm.gov.pl/x', ...over });

test('zapytanie: tylko poprawne parametry, q od 3 znaków, od > do zamienione, na_strone 1-50', () => {
  const none = new URLSearchParams(L.buildVotesQuery(L.EMPTY_FILTERS));
  assert.equal([...none.keys()].sort().join(), 'na_strone,strona');
  assert.equal(none.get('strona'), '1'); assert.equal(none.get('na_strone'), '20');
  const short = new URLSearchParams(L.buildVotesQuery({ ...L.EMPTY_FILTERS, q: 'ab' }));
  assert.equal(short.has('q'), false);
  const full = new URLSearchParams(L.buildVotesQuery({ q: '  budżet  ', klub: 'KO', wynik: 'odrzucone', od: '2026-10-05', do: '2026-09-01' }, 3, 99));
  assert.equal(full.get('q'), 'budżet'); assert.equal(full.get('klub'), 'KO'); assert.equal(full.get('wynik'), 'odrzucone');
  assert.equal(full.get('od'), '2026-09-01'); assert.equal(full.get('do'), '2026-10-05');
  assert.equal(full.get('strona'), '3'); assert.equal(full.get('na_strone'), '50');
  const bad = new URLSearchParams(L.buildVotesQuery({ q: '', klub: '', wynik: 'wygrane', od: '2026-13-45', do: 'jutro' }, -4, 0));
  assert.equal(bad.has('wynik'), false); assert.equal(bad.has('od'), false); assert.equal(bad.has('do'), false);
  assert.equal(bad.get('strona'), '1'); assert.equal(bad.get('na_strone'), '20');
  assert.equal(new URLSearchParams(L.buildVotesQuery({ ...L.EMPTY_FILTERS, q: 'x'.repeat(300) })).get('q').length, 120);
});

test('filtry <-> adres strony i krótkie zapytanie', () => {
  const f = L.parseFilters('?q=Kodeks&klub=PiS&wynik=przyjete&od=2026-01-02&do=2026-02-03');
  eq({ ...f }, { q: 'Kodeks', klub: 'PiS', wynik: 'przyjete', od: '2026-01-02', do: '2026-02-03' });
  assert.equal(L.filtersToSearch(f), '?q=Kodeks&klub=PiS&wynik=przyjete&od=2026-01-02&do=2026-02-03');
  assert.equal(L.filtersToSearch(L.EMPTY_FILTERS), '');
  assert.equal(L.parseFilters('?wynik=<script>&od=zły').wynik, '');
  assert.equal(L.parseFilters('?od=zły').od, '');
  assert.equal(L.hasFilters(L.EMPTY_FILTERS), false); assert.equal(L.hasFilters({ ...L.EMPTY_FILTERS, klub: 'KO' }), true);
  assert.equal(L.queryTooShort('ab'), true); assert.equal(L.queryTooShort(''), false); assert.equal(L.queryTooShort('abc'), false);
});

test('sortowanie po stronie klienta: data i wynik ogółem, stabilne, brak liczb na końcu', () => {
  const rows = [
    vote({ id: 'a', date: '2026-09-01', number: 3, result: { yes: 10, no: 5 } }),
    vote({ id: 'b', date: '2026-10-01', number: 1, result: { yes: 300, no: 100 } }),
    vote({ id: 'c', date: '2026-10-01', number: 2, result: { yes: 300, no: 90 } }),
    vote({ id: 'd', date: '2026-08-01', number: 9, result: null }),
  ];
  eq(L.sortRows(rows, 'date', 'desc').map(r => r.id), ['c', 'b', 'a', 'd']);
  eq(L.sortRows(rows, 'date', 'asc').map(r => r.id), ['d', 'a', 'b', 'c']);
  eq(L.sortRows(rows, 'result', 'desc').map(r => r.id), ['b', 'c', 'a', 'd']);
  eq(L.sortRows(rows, 'result', 'asc').map(r => r.id), ['a', 'c', 'b', 'd']);
  eq(rows.map(r => r.id), ['a', 'b', 'c', 'd'], 'wejście bez zmian');
  eq(L.mergeRows(rows, [rows[0], vote({ id: 'e' })]).map(r => r.id), ['a', 'b', 'c', 'd', 'e']);
});

test('głos klubu: dominujący głos oddany, nieobecni nie są głosem, brak danych = null', () => {
  assert.equal(L.clubSummary(null), null);
  assert.equal(L.clubSummary({ club: 'KO', votes: {} }), null);
  const a = L.clubSummary({ club: 'KO', votes: { nieobecny: 3, przeciw: 153 } });
  assert.equal(a.word, 'przeciw'); assert.equal(a.split, false); assert.equal(a.counts, '153 przeciw, 3 nieob.');
  const b = L.clubSummary({ club: 'PiS', votes: { za: 100, przeciw: 20, 'wstrzymał się': 5 } });
  assert.equal(b.word, 'za'); assert.equal(b.split, true); assert.equal(b.counts, '100 za, 20 przeciw, 5 wstrzymał się');
  assert.equal(L.clubSummary({ club: 'X', votes: { nieobecny: 7 } }).word, 'nieobecny');
  assert.equal(L.outcomeLabel('przyjete'), 'przyjęte'); assert.equal(L.outcomeLabel('cokolwiek'), 'wynik nieustalony');
});

test('CSV z widocznych wierszy: średnik, BOM, cudzysłowy, formuły zneutralizowane, stopka z zakresem', () => {
  const rows = [vote({ title: '="zły" tytuł; z średnikiem', club_votes: { club: 'KO', votes: { przeciw: 150, nieobecny: 2 } } }),
    vote({ id: '10/1/2', number: 2, result: null, club_votes: null })];
  const csv = L.votesToCsv(rows, { klub: 'KO', stamp: '2026-10-13', total: 350, description: 'To nie jest pełne archiwum.' });
  assert.ok(csv.startsWith('﻿"data";"kadencja"'));
  const lines = csv.slice(1).split('\r\n');
  assert.equal(lines.length, 5);
  assert.ok(lines[0].includes('"glos_klubu_KO"'));
  assert.ok(lines[1].includes(`"'=""zły""`), 'formuła poprzedzona apostrofem, cudzysłowy podwojone');
  assert.ok(lines[1].includes('"przeciw";"150 przeciw, 2 nieob."'));
  assert.ok(lines[2].includes('"brak w naszych danych"'));
  assert.ok(lines[4].includes('To nie jest pełne archiwum.') && lines[4].includes('Wiersze: 2 z 350') && lines[4].includes('2026-10-13'));
  assert.equal(L.csvCell('a\n b'), '"a b"'); assert.equal(L.csvCell('@x'), `"'@x"`); assert.equal(L.csvCell(null), '""');
  const plain = L.votesToCsv(rows, { stamp: '2026-10-13' });
  assert.equal(plain.includes('glos_klubu'), false);
});

test('adresy z danych zewnętrznych: tylko http(s) i ścieżki serwisu', () => {
  assert.equal(L.safeUrl('https://www.sejm.gov.pl/a?b=1'), 'https://www.sejm.gov.pl/a?b=1');
  assert.equal(L.safeUrl('/przeszlosc/osoba/12'), '/przeszlosc/osoba/12');
  for (const bad of ['javascript:alert(1)', '//evil.example', 'data:text/html,x', '', null, undefined, 5, 'https://a b']) assert.equal(L.safeUrl(bad), null, String(bad));
});

const net = {
  nodes: [
    { id: 'figure:1', kind: 'osoba', label: 'Osoba Główna', root: true },
    { id: 'figure:2', kind: 'osoba', label: 'Anna Nowak', role: 'Posłanka', slug: '2-anna-nowak' },
    { id: 'figure:3', kind: 'osoba', label: 'Jan Ąbacki', club: 'KO' },
    { id: 'mp:10:77', kind: 'osoba', label: 'Piotr Zieliński', club: 'PiS' },
  ],
  edges: [
    { source: 'figure:1', target: 'figure:2', kind: 'krs', weight: 1, label: 'te same podmioty w KRS', evidence: [] },
    { source: 'figure:1', target: 'figure:3', kind: 'wspolwystepowanie', weight: 7, label: 'wspólne dokumenty i tematy', evidence: [{ kind: 'dokument', label: 'x', url: 'https://a.pl' }] },
    { source: 'figure:1', target: 'figure:2', kind: 'wspolwystepowanie', weight: 7, label: 'wspólne dokumenty i tematy', evidence: [] },
    { source: 'figure:1', target: 'mp:10:77', kind: 'glosowania', weight: 81, label: 'zgodność głosów 81% (spoza klubu)', evidence: [] },
    { source: 'figure:1', target: 'figure:404', kind: 'glosowania', weight: 90, label: 'zgodność głosów 90%', evidence: [] },
  ],
};

test('sieć: grupy w stałej kolejności, waga malejąco potem nazwisko, krawędzie bez węzła pominięte', () => {
  const g = L.groupEdges(net);
  eq(g.map(x => x.kind), ['wspolwystepowanie', 'glosowania', 'krs']);
  eq(g[0].rows.map(r => r.node.label), ['Anna Nowak', 'Jan Ąbacki']);
  assert.equal(g[1].rows.length, 1, 'krawędź do nieznanego węzła pominięta');
  assert.equal(L.netTotal(g), 4);
  assert.equal(g[1].rows[0].weightText, '81%');
  assert.equal(g[1].rows[0].labelText, 'zgodność głosów (spoza klubu)', 'procent jest w kolumnie wagi');
  assert.equal(g[0].rows[0].weightText, '7 punktów');
  assert.equal(g[2].rows[0].weightText, '1 podmiot');
  assert.equal(L.isContext('krs'), true); assert.equal(L.isContext('glosowania'), false);
  assert.equal(L.groupEdges({ nodes: [], edges: [] }).length, 0);
});

test('sieć: adresy profili, bez odnośnika dla węzłów spoza rejestru; podgląd skraca grupy, lista tekstowa ma wszystko', () => {
  assert.equal(L.nodeHref(net.nodes[1]), '/przeszlosc/osoba/2-anna-nowak');
  assert.equal(L.nodeHref(net.nodes[2]), '/przeszlosc/osoba/3');
  assert.equal(L.nodeHref(net.nodes[3]), null);
  assert.equal(L.nodeHref({ id: 'figure:9', kind: 'osoba', label: 'x', slug: '../../etc' }), '/przeszlosc/osoba/9');
  const many = { nodes: [net.nodes[0]], edges: [] };
  for (let i = 0; i < 9; i++) { many.nodes.push({ id: `figure:${10 + i}`, kind: 'osoba', label: `Osoba ${i}` }); many.edges.push({ source: 'figure:1', target: `figure:${10 + i}`, kind: 'wspolwystepowanie', weight: i, label: 'x', evidence: [] }); }
  const g = L.groupEdges(many);
  assert.equal(L.netTotal(L.visibleGroups(g, false)), L.NET_PREVIEW);
  assert.equal(L.netTotal(L.visibleGroups(g, true)), 9);
  assert.equal(g[0].rows.length, 9, 'visibleGroups nie zmienia danych wejściowych');
});

test('pliki: menu z Głosowaniami, sieć w aktach, strona z metadanymi, bez długiego myślnika i pasków', () => {
  const ui = read('app/przeszlosc/ui.tsx');
  assert.ok(ui.includes("['/przeszlosc/glosowania', 'Głosowania']"));
  assert.ok(ui.includes("p.startsWith('/przeszlosc/glosowania')"));
  const profile = read('app/przeszlosc/PersonProfile.tsx');
  assert.ok(profile.includes("import { Siec, type NetAvailability } from './Siec'"));
  // od landingu (13.10) wpis "Sieć" w spisie sekcji jest w landingIndex (najwazniejsze-dane.ts), nie w PersonProfile
  assert.ok(profile.includes("['pp-siec', 'Sieć']") || read('app/przeszlosc/najwazniejsze-dane.ts').includes("['pp-siec', 'Sieć']"));
  const page = read('app/przeszlosc/glosowania/page.tsx');
  assert.ok(page.includes('robots') && page.includes('title:'));
  const files = ['app/przeszlosc/glosowania/GlosowaniaPage.tsx', 'app/przeszlosc/glosowania/page.tsx', 'app/przeszlosc/Siec.tsx', 'app/przeszlosc/glosowania-lista.ts',
    'app/przeszlosc/glosowania-lista.css', 'app/przeszlosc/siec.css'];
  for (const f of files) {
    const s = read(f);
    assert.equal(/[–—]/.test(s), false, `${f}: długi myślnik`);
    assert.equal(s.includes('�'), false, `${f}: uszkodzone znaki`);
  }
  const css = read('app/przeszlosc/glosowania-lista.css') + read('app/przeszlosc/siec.css');
  assert.equal(/overflow(-x|-y)?\s*:\s*(auto|scroll)/.test(css), false, 'żadnych kontenerów przewijanych (paski)');
});

// przeszłość.today v3 (13.10.2026): landing profilu osoby "Najważniejsze" - funkcje czyste (app/przeszlosc/najwazniejsze-dane.ts)
// i kontrola kształtu plików. Bez nowych pakietów: TS przez typescript.transpileModule, jak w testach 117 i 119.
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
  vm.runInNewContext(source, { exports, require: () => ({}), URL, Number, String, Math, Set, Map, Date, RegExp });
  return exports;
}
const N = load('app/przeszlosc/najwazniejsze-dane.ts');
const NB = ' ';

const org = (over = {}) => ({ id: 1, name: 'Fundacja "Dobra Fabryka"', krs_number: '0000123456', official_register_url: 'https://wyszukiwarka-krs.ms.gov.pl/',
  extra_register_url: 'https://rejestr.io/krs/123456', public_role: 'członek Rady Fundacji', organ: 'organ nadzoru', relation_status: 'current',
  since: '2014-08-08', until: null, kind: 'foundation', legal_form: 'fundacja', verified_at: '2026-10-02T10:00:00Z', ...over });
const base = (over = {}) => ({ generated_at: '2026-10-13T06:29+00:00', organisations: [], money_trail: null, committees: [], employment_timeline: [],
  documents: { by_kind: {}, results: [] }, votes: { available: true, count: 10, deviation: null }, open_data: null, materials: { count: 0 }, posts: { count: 0 }, access: { locked: [] }, ...over });
// teksty kafli porównujemy ze zwykłymi spacjami (twarde spacje sprawdza osobny test funkcji pomocniczych)
const plain = o => JSON.parse(JSON.stringify(o), (k, v) => (typeof v === 'string' ? v.replace(/ /g, ' ') : v));
const tile = (d, id) => plain(N.buildLanding(d).tiles.find(t => t.id === id));

test('funkcje pomocnicze: liczby po polsku, daty, odmiana, twarda spacja, bezpieczny adres', () => {
  assert.equal(N.num(1387695), `1${NB}387${NB}695`);
  assert.equal(N.num(0.2, 1), '0,2'); assert.equal(N.num(1, 1), '1'); assert.equal(N.num(23267.95), `23${NB}268`);
  assert.equal(N.ymd('2026-10-13T06:29+00:00'), '13.10.2026'); assert.equal(N.ymd(null), ''); assert.equal(N.ymd('xx'), '');
  assert.equal(N.plural(1, 'podmiot', 'podmioty', 'podmiotów'), 'podmiot'); assert.equal(N.plural(3, 'podmiot', 'podmioty', 'podmiotów'), 'podmioty');
  assert.equal(N.plural(12, 'podmiot', 'podmioty', 'podmiotów'), 'podmiotów'); assert.equal(N.plural(22, 'podmiot', 'podmioty', 'podmiotów'), 'podmioty');
  assert.equal(N.nb('Mediana w kadencji i w Sejmie'), `Mediana w${NB}kadencji i${NB}w${NB}Sejmie`);
  assert.equal(N.safeUrl('javascript:alert(1)'), null); assert.equal(N.safeUrl('//evil.example'), null);
  assert.equal(N.safeUrl('https://sejm.gov.pl/x'), 'https://sejm.gov.pl/x'); assert.equal(N.safeUrl('/przeszlosc/spolka/1'), '/przeszlosc/spolka/1');
  assert.equal(N.hostOf('https://api.sejm.gov.pl/x'), 'sejm.gov.pl'); assert.equal(N.hostOf('https://www.europarl.europa.eu/a'), 'europarl.europa.eu');
});

test('podmioty: sortowanie (obecne najpierw), rodzaj słowami, okres, odnośnik wewnętrzny po KRS, lista z odnośnikiem do rejestru', () => {
  const list = [org({ id: 1, name: 'B Dawna', relation_status: 'former', since: '2001-01-01', until: '2005-06-02' }),
    org({ id: 2, name: 'A Obecna' }), org({ id: 3, name: 'C Nowsza dawna', relation_status: 'former', since: '2010-01-01', until: '2020-05-05', kind: 'company', legal_form: 'spółka z ograniczoną odpowiedzialnością' }),
    org({ id: 4, name: 'D Inna', kind: 'other', legal_form: 'polski związek sportowy', krs_number: 'x' })];
  const t = tile(base({ organisations: list }), 'podmioty');
  assert.equal(t.state, 'ok'); assert.equal(t.value, '4'); assert.match(t.unit, /podmioty powiązane po KRS/);
  eq(t.orgs.map(r => r.name), ['A Obecna', 'D Inna', 'C Nowsza dawna', 'B Dawna']);
  const a = t.orgs[0], d = t.orgs[1], c = t.orgs[2];
  assert.equal(a.href, '/przeszlosc/spolka/0000123456'); assert.equal(a.krsUrl, 'https://rejestr.io/krs/123456');
  assert.equal(a.type, 'fundacja'); assert.equal(a.period, 'od 2014'); assert.equal(a.statusText, 'obecnie');
  assert.equal(d.href, null); assert.equal(d.krs, ''); assert.equal(d.type, 'polski związek sportowy');
  assert.equal(c.type, 'spółka'); assert.equal(c.period, '2010 - 2020'); assert.equal(c.statusText, 'wcześniej');
  assert.equal(t.lines[0], 'obecnie: 2 · wcześniej: 2 · 2 fundacje · 1 spółka · 1 inny podmiot');
  assert.equal(t.link.label, 'Zobacz wszystko →'); assert.equal(t.link.href, '#pp-krs');
  assert.equal(t.stamp, '2026-10-02T10:00:00Z'); assert.match(t.stampText, /^sprawdzono 02\.10\.2026$/);
  assert.equal(t.source[0].label, 'KRS (Ministerstwo Sprawiedliwości)');
});

test('podmioty: więcej niż 5 -> licznik w odnośniku; brak -> "brak w naszych danych" z zakresem i datą; pilotaż', () => {
  const many = Array.from({ length: 8 }, (_, i) => org({ id: i + 1, name: `P${i}` }));
  const t = tile(base({ organisations: many }), 'podmioty');
  assert.equal(t.orgs.length, 8); assert.equal(t.link.label, 'Zobacz wszystko (8) →'); assert.equal(N.SHOWN_ORGS, 5);
  const e = tile(base(), 'podmioty');
  assert.equal(e.state, 'empty'); assert.equal(e.value, 'brak w naszych danych'); assert.match(e.lines[0], /^Zakres: /);
  assert.equal(e.stampText, 'stan na 13.10.2026'); assert.equal(N.buildLanding(base()).lean, true); assert.equal(N.buildLanding(base({ organisations: many })).lean, false);
  const locked = tile(base({ organisations: many, access: { locked: ['krs'] } }), 'podmioty');
  assert.equal(locked.state, 'locked'); assert.equal(locked.orgs.length, 0); assert.equal(locked.link.href, '/przeszlosc/pilot');
});

test('podmioty: zamówienia i dotacje tylko z money_trail (bez wymyślania), 0 jest zerem', () => {
  const o = [org()];
  assert.equal(tile(base({ organisations: o, money_trail: null }), 'podmioty').extra, null);
  assert.equal(tile(base({ organisations: o, money_trail: { results: [] } }), 'podmioty').extra, null);
  const zero = tile(base({ organisations: o, money_trail: { results: [{ contracts: { count: 0 }, grants: { count: 0 } }] } }), 'podmioty').extra;
  assert.match(zero.text, /w naszych danych: 0\.$/); assert.equal(zero.href, '#pp-pieniadze');
  const some = tile(base({ organisations: o, money_trail: { results: [{ contracts: { count: 2 }, grants: { count: 1 } }, { contracts: { count: 4 } }] } }), 'podmioty').extra;
  assert.match(some.text, /: 7\.$/);
  assert.equal(tile(base({ organisations: o, money_trail: { results: [{ contracts: { count: 2 } }] }, access: { locked: ['money_trail'] } }), 'podmioty').extra, null);
});

test('oświadczenia majątkowe: tylko z indeksu dokumentów Sejmu; rok jednoznaczny; brak = brak w naszych danych', () => {
  assert.equal(N.assetYear('Oświadczenie majątkowe za rok 2024'), 2024);
  assert.equal(N.assetYear('Oświadczenie za 2023 i korekta 2024'), null);
  assert.equal(N.assetYear('plik 12345.pdf'), null);
  const none = tile(base(), 'majatek');
  assert.equal(none.state, 'empty'); assert.equal(none.value, 'brak w naszych danych'); assert.match(none.lines[0], /indeks oświadczeń posłów/);
  const non = tile(base({ votes: { available: false } }), 'majatek');
  assert.match(non.lines[0], /nie jest posłem w naszych danych/);
  const t = tile(base({ documents: { by_kind: { 'Oświadczenie majątkowe': 3, 'Interpelacja': 9 }, results: [
    { kind: 'interpellations', label: 'Interpelacja', title: 'x', url: 'https://sejm.gov.pl/i' },
    { kind: 'asset_document', label: 'Oświadczenie majątkowe', title: 'Oświadczenie majątkowe za rok 2024', url: 'https://www.sejm.gov.pl/a.pdf' },
    { kind: 'asset_document', label: 'Oświadczenie majątkowe', title: 'Oświadczenie majątkowe za rok 2023', url: 'javascript:x' }] } }), 'majatek');
  assert.equal(t.state, 'ok'); assert.equal(t.value, '3'); assert.equal(t.docs.length, 2); assert.equal(t.docs[0].year, 2024); assert.equal(t.docs[1].url, null);
  assert.match(t.lines[0], /za rok 2024/); assert.equal(t.link.filter, 'record');
});

test('kilometrówki i rozliczenia: najnowszy okres, przebieg gdy jest, biuro poselskie z zastrzeżeniem, brak = brak w naszych danych', () => {
  const od = { mp_expenses: { mileage: [
    { period: '2024', amount_pln: 22463.81, km: 19534, check: 'zgodne', origin: 'skrotpolityczny.pl', origin_url: 'https://skrotpolityczny.pl/polityk/x/' },
    { period: '2025', amount_pln: 23267.95, km: null, check: 'zgodne', origin: 'sprawozdania_pos9', origin_url: 'https://jakglosuja.pl/sprawozdania/1096' }],
  offices: [{ year: 2025, total_pln: 304164.41, pdf_url: 'https://orka.sejm.gov.pl/x.pdf', check: 'PDF bez warstwy tekstu - nie sprawdzono automatycznie' }] } };
  const t = tile(base({ open_data: od }), 'km');
  assert.equal(t.state, 'ok'); assert.equal(t.value, '23 268 zł'); assert.equal(t.unit, 'kilometrówka za rok 2025');
  assert.match(t.lines[0], /Przebieg za rok 2025: brak w naszych danych/); assert.match(t.lines[1], /Biuro poselskie 2025: 304 164 zł \(PDF bez kontroli automatycznej\)/);
  eq(t.source.map(s => s.label), ['jakglosuja.pl', 'sejm.gov.pl (PDF)']); assert.equal(t.link.href, '#pp-exp-h');
  const km = tile(base({ open_data: { mp_expenses: { mileage: [{ period: '2024', amount_pln: 0, km: 0, origin_url: 'https://skrotpolityczny.pl/x' }], offices: [] } } }), 'km');
  assert.equal(km.value, '0 zł'); assert.equal(km.label, 'Rozliczenia (kilometrówki)'); assert.match(km.lines[0], /Przebieg: 0 km/);
  const none = tile(base(), 'km'); assert.equal(none.state, 'empty'); assert.equal(none.value, 'brak w naszych danych'); assert.match(none.lines[0], /^Zakres: kilometrówki/);
  const pe = tile(base({ votes: { available: false }, open_data: { ep_integrity: { income: { total_eur: 9438.97, paid: 2 }, meetings: { count: 1 }, declarations: [{ title: 'D', url: 'https://www.europarl.europa.eu/d.pdf' }] } } }), 'km');
  assert.equal(pe.label, 'Rozliczenia (deklaracja PE)'); assert.equal(pe.value, '9 439 €'); assert.equal(pe.link.href, '#pp-iw-h');
});

test('głosy inne niż większość klubu: sama liczba, metoda w podpisie, bez mediany, flagi i ocen', () => {
  const dev = { term: 10, club: 'KO', share: 0.2, club_median: 0.2, flagged: true, counted: 1544, rebellions_total: 0, latest: null };
  const t = tile(base({ votes: { available: true, deviation: dev } }), 'klub');
  assert.equal(t.label, 'Głosy inne niż większość klubu'); assert.equal(t.value, '0'); assert.equal(t.unit, 'przy zgodności klubu ≥ 80%');
  assert.equal(t.lines.length, 1);
  assert.equal(t.lines[0], 'Wszystkie głosy inne niż większość klubu KO: 0,2% z 1 544 głosowań w 10. kadencji.');
  assert.equal(t.link.filter, 'vote');
  assert.doesNotMatch(JSON.stringify(t), /mediana|medianą|wbrew|Wyróżnion/i);
  const latest = tile(base({ votes: { available: true, deviation: { ...dev, rebellions_total: 1, latest: { url: 'https://www.sejm.gov.pl/g', date: '2026-01-02' } } } }), 'klub');
  assert.equal(latest.value, '1'); assert.equal(latest.source[0].url, 'https://www.sejm.gov.pl/g');
  const mp = tile(base({ votes: { available: true, deviation: null } }), 'klub'); assert.equal(mp.state, 'empty'); assert.match(mp.lines[0], /zestawienie z klubem liczone co noc/);
  const non = tile(base({ votes: { available: false, deviation: null } }), 'klub'); assert.match(non.lines[0], /nie jest posłem w naszych danych/);
});

test('funkcje: mandat przed innymi funkcjami, komisje, kierownictwo komisji, bez wymyślania', () => {
  const emp = [{ position: 'Prezes partii', organisation: 'Prawo i Sprawiedliwość', status: 'current', since: '2003-01-01', source: { url: 'https://pis.org.pl' } },
    { position: 'Poseł na Sejm RP', organisation: 'Sejm RP · X kadencja', status: 'current', since: '2023-11-13', checked_at: '2026-10-12T03:20:06Z', source: { url: 'https://api.sejm.gov.pl/sejm/term10/MP/148' } },
    { position: 'Poseł na Sejm RP', organisation: 'Sejm RP · IX kadencja', status: 'former', since: '2019-11-12', until: '2023-11-12' }];
  const com = [{ code: 'PET', name: 'Komisja do Spraw Petycji', role: 'członek', url: 'https://www.sejm.gov.pl/k' },
    { code: 'DIM', name: 'Komisja do Spraw Dzieci i Młodzieży', role: 'przewodniczący', url: 'https://www.sejm.gov.pl/d' }];
  const t = tile(base({ employment_timeline: emp, committees: com }), 'funkcje');
  assert.equal(t.value, '2'); assert.equal(t.unit, 'komisje sejmowe');
  assert.match(t.lines[0], /^Poseł na Sejm RP, Sejm RP · X kadencja, od 2023\.$/);
  assert.match(t.lines[1], /przewodniczący: Komisja do Spraw Dzieci i Młodzieży/);
  assert.equal(t.stamp, '2026-10-12T03:20:06Z'); eq(t.source.map(s => s.label), ['sejm.gov.pl']);
  const only = tile(base({ employment_timeline: emp.slice(0, 1) }), 'funkcje'); assert.equal(only.value, '1'); assert.equal(only.unit, 'obecna funkcja');
  const e = tile(base(), 'funkcje'); assert.equal(e.state, 'empty'); assert.equal(e.value, 'brak w naszych danych');
});

test('media: liczby z profilu; brak = brak w naszych danych; pasek jest ostatnim kafelkiem', () => {
  const t = tile(base({ articles_total: 3139, materials: { count: 2 }, posts: { count: 5 } }), 'media');
  assert.equal(t.value, '3 139'); assert.match(t.lines[0], /potwierdzonych: 2 · wpisów na X: 5/);
  assert.equal(tile(base(), 'media').state, 'empty');
  eq(N.buildLanding(base()).tiles.map(x => x.id), ['podmioty', 'majatek', 'km', 'klub', 'funkcje', 'media']);
});

test('każdy kafel ma źródło (albo zakres) i datę odświeżenia; zdanie neutralne; źródła bez duplikatów', () => {
  const full = base({ organisations: [org()], documents: { by_kind: { 'Oświadczenie majątkowe': 1 }, results: [{ kind: 'asset_document', title: 'za 2024', url: 'https://sejm.gov.pl/a' }] },
    open_data: { mp_expenses: { mileage: [{ period: '2025', amount_pln: 100, km: 1, origin_url: 'https://jakglosuja.pl/x' }], offices: [] } },
    votes: { available: true, deviation: { term: 10, club: 'KO', share: 1, club_median: 1, flagged: false, counted: 100, rebellions_total: 2, latest: null } },
    employment_timeline: [{ position: 'Poseł na Sejm RP', organisation: 'Sejm', status: 'current', source: { url: 'https://api.sejm.gov.pl/x' } }], articles_total: 4 });
  for (const d of [full, base(), base({ votes: { available: false } })]) {
    const l = N.buildLanding(d);
    for (const t of l.tiles) {
      assert.match(t.stampText, /\d{2}\.\d{2}\.\d{4}$/, `${t.id}: data`);
      assert.ok(t.source.length > 0 || t.state === 'empty' || t.id === 'media' || t.state === 'ok', `${t.id}: źródło`);
      assert.ok(t.value.length > 0 && t.label.length > 0 && t.link.href.length > 0, `${t.id}: kształt`);
      for (const line of t.lines) assert.ok(!/\bundefined\b|\bnull\b|NaN|\[object/.test(line), `${t.id}: ${line}`);
    }
    assert.equal(l.disclaimer, N.LANDING_RULE);
    assert.match(l.disclaimer, /Nie ocenia osób i nie wyciąga wniosków: wnioski należą do Ciebie\. Powiązanie w danych nie jest zarzutem\.$/);
    assert.equal(new Set(l.sources.map(s => s.label)).size, l.sources.length);
  }
  assert.ok(tile(full, 'km').source.length >= 1 && tile(full, 'klub').source.length >= 1 && tile(full, 'funkcje').source.length >= 1);
});

test('nazwy kafli wg właściciela i brak słów oceniających w tekstach landingu', () => {
  const full = base({ organisations: [org()], documents: { by_kind: { 'Oświadczenie majątkowe': 1 }, results: [{ kind: 'asset_document', title: 'za 2024', url: 'https://sejm.gov.pl/a' }] },
    open_data: { mp_expenses: { mileage: [{ period: '2025', amount_pln: 100, km: 1, origin_url: 'https://jakglosuja.pl/x' }], offices: [] } },
    votes: { available: true, deviation: { term: 10, club: 'KO', share: 1, club_median: 0.5, flagged: true, counted: 100, rebellions_total: 2, latest: null } },
    employment_timeline: [{ position: 'Poseł na Sejm RP', organisation: 'Sejm', status: 'current' }], articles_total: 4 });
  const l = N.buildLanding(full);
  eq(l.tiles.map(t => t.label), ['Fundacje i spółki powiązane w KRS', 'Oświadczenia majątkowe', 'Rozliczenia (kilometrówki)', 'Głosy inne niż większość klubu', 'Funkcje', 'Wpisy i media']);
  assert.equal(N.LANDING_TITLE, 'Dane w jednym miejscu');
  const text = JSON.stringify({ ...l, disclaimer: '' }); // zdanie zasady naczelnej celowo mówi, że powiązanie nie jest zarzutem
  assert.doesNotMatch(text, /najważniejsz|ważne|alarm|podejrz|wbrew|mediana|medianą|ranking|sygnał|wyróżnion/i, 'słowa oceniające');
  assert.match(N.LANDING_RULE_SHORT, /nie oceniamy osób, wnioski należą do Ciebie\. Powiązanie w danych nie jest zarzutem\.$/);
});

test('spis sekcji (indeks akt): landing najpierw, potem dotychczasowe sekcje; Sieć i Mianowniki warunkowo', () => {
  const full = N.landingIndex({ hasDenominators: true, hasNet: true });
  eq(full.map(x => x[1]), ['Fundacje i spółki', 'Oświadczenia', 'Rozliczenia', 'Głosowania', 'Funkcje', 'Źródła', 'Oś czasu', 'Sieć', 'Mianowniki']);
  eq(N.landingIndex({ hasDenominators: true, hasNet: false }).map(x => x[0]).slice(-2), ['pp-os', 'dn']);
  eq(N.landingIndex({ hasDenominators: false, hasNet: true }).map(x => x[0]).slice(-1), ['pp-os']);
  const ids = new Set(full.map(x => x[0])); assert.equal(ids.size, full.length);
});

test('pliki: komponent importowany w profilu, indeks z landingIndex, filtr osi czasu, arkusz bez obramowań i pasków, brak długiego myślnika', () => {
  const profile = read('app/przeszlosc/PersonProfile.tsx');
  assert.match(profile, /import \{ Najwazniejsze \} from '\.\/Najwazniejsze'/);
  assert.match(profile, /landingIndex\(/); assert.match(profile, /<Najwazniejsze data=\{data\} onFilter=/);
  const comp = read('app/przeszlosc/Najwazniejsze.tsx');
  assert.match(comp, /id="pp-zrodla"/); assert.match(comp, /data-pt-source/); assert.match(comp, /aria-labelledby/);
  const css = read('app/przeszlosc/najwazniejsze.css');
  assert.doesNotMatch(css, /overflow(-[xy])?:\s*scroll/); assert.doesNotMatch(css, /\bborder:\s*1px solid/);
  assert.match(css, /prefers-reduced-motion: no-preference/); assert.match(css, /grid-template-rows: auto minmax\(0, 1fr\) auto/);
  for (const f of ['app/przeszlosc/najwazniejsze-dane.ts', 'app/przeszlosc/Najwazniejsze.tsx', 'app/przeszlosc/najwazniejsze.css']) {
    const src = read(f);
    assert.doesNotMatch(src, /[–—]/, `${f}: długi myślnik`);
    assert.doesNotMatch(src, /\?\?\?|Å|Ä…/, `${f}: popsute znaki`);
  }
});

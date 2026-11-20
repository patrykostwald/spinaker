// „Teraz”, W4: oś czasu i przełącznik TODAY / PRZESZŁOŚĆ. Czysta logika czasu i kroków (czasOsi.ts): doby w strefie Warszawy
// (także 23- i 25-godzinne), przedziały jak w backendzie (historia.kubelki), adres URL, kroki suwaka, odtwarzanie, walidacja os/
// i wpisy/?na=, luki (nigdy zero) i teksty. node --test.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const cache = new Map();
function load(file) {
  if (file.endsWith('.json')) return JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
  const bez = file.replace(/\.tsx?$/, '');
  const wzgledna = [`${bez}.ts`, `${bez}.tsx`, `${bez}/index.ts`].find(k => fs.existsSync(path.join(root, k)));
  if (!wzgledna) throw new Error(`brak modułu ${file}`);
  const abs = path.join(root, wzgledna);
  if (cache.has(abs)) return cache.get(abs).exports;
  const source = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  cache.set(abs, module);
  const req = name => (name.startsWith('.')
    ? load(path.relative(root, path.resolve(path.dirname(abs), name)).split(path.sep).join('/'))
    : require(name));
  new Function('module', 'exports', 'require', 'process', source)(module, module.exports, req, { env: {} });
  return module.exports;
}
const os = load(`${dir}/czasOsi`);
const T = iso => Date.parse(iso);
const ISO = ms => new Date(ms).toISOString();
const GODZ = 3_600_000;
// „teraz” na wszystkie testy: piątek 20.11.2026, 14:37:20 w Warszawie (13:37:20 UTC)
const TERAZ = T('2026-11-20T13:37:20Z');

test('160: przesunięcie i początek doby w Warszawie (zima, lato)', () => {
  assert.equal(os.przesuniecie(T('2026-11-18T12:00:00Z')), GODZ);
  assert.equal(os.przesuniecie(T('2026-07-01T12:00:00Z')), 2 * GODZ);
  assert.equal(ISO(os.poczatekDnia(T('2026-11-18T12:00:00Z'))), '2026-11-17T23:00:00.000Z');
  assert.equal(ISO(os.poczatekDnia(T('2026-11-18T23:30:00Z'))), '2026-11-18T23:00:00.000Z', '00:30 czasu polskiego to już 19.11');
  assert.equal(ISO(os.poczatekDnia(T('2026-07-01T21:59:00Z'))), '2026-06-30T22:00:00.000Z');
});

test('160: doby 23- i 25-godzinne (zmiana czasu) mają 23 i 25 przedziałów godzinnych', () => {
  const wiosna = os.poczatekDnia(T('2026-03-29T10:00:00Z'));
  assert.equal(ISO(wiosna), '2026-03-28T23:00:00.000Z');
  assert.equal(ISO(os.nastepnyDzien(wiosna)), '2026-03-29T22:00:00.000Z');
  const jesien = os.poczatekDnia(T('2026-10-25T10:00:00Z'));
  assert.equal(ISO(jesien), '2026-10-24T22:00:00.000Z');
  assert.equal(ISO(os.nastepnyDzien(jesien)), '2026-10-25T23:00:00.000Z');
  assert.equal(ISO(os.poprzedniDzien(os.nastepnyDzien(jesien))), ISO(jesien));
  const godziny = na => os.przedzialyOsi({ tryb: 'przeszlosc', na, krok: 'godzina' }, TERAZ).length;
  assert.equal(godziny(T('2026-03-29T10:00:00Z')), 23);
  assert.equal(godziny(T('2026-10-25T10:00:00Z')), 25);
  assert.equal(godziny(T('2026-11-18T10:00:00Z')), 24);
});

test('160: oś dni ma 30 dób do dziś, oś godzin dziś kończy się na bieżącej godzinie', () => {
  const dni = os.przedzialyOsi({ tryb: 'dzis', na: null, krok: 'dzien' }, TERAZ);
  assert.equal(dni.length, os.DNI_OSI);
  assert.equal(ISO(dni[0].od), '2026-10-21T22:00:00.000Z', 'start 22.10 o północy (jeszcze czas letni)');
  assert.equal(ISO(dni.at(-1).od), '2026-11-19T23:00:00.000Z');
  assert.equal(dni[0].od, os.poczatekOsi(TERAZ));
  const godz = os.przedzialyOsi({ tryb: 'dzis', na: null, krok: 'godzina' }, TERAZ);
  assert.equal(godz.length, 15, '0:00-14:59 dziś');
  assert.equal(ISO(godz.at(-1).od), '2026-11-20T13:00:00.000Z');
  // przedziały są ciągłe i rosnące
  for (const lista of [dni, godz]) for (let i = 1; i < lista.length; i++) assert.equal(lista[i].od, lista[i - 1].do);
});

test('160: moment przedziału to jego ostatnia sekunda, nigdy przyszłość; indeks przedziału', () => {
  const dni = os.przedzialyOsi({ tryb: 'dzis', na: null, krok: 'dzien' }, TERAZ);
  assert.equal(ISO(os.momentPrzedzialu(dni.at(-2), TERAZ)), '2026-11-19T22:59:59.000Z', 'wczoraj 23:59:59');
  assert.equal(os.momentPrzedzialu(dni.at(-1), TERAZ), TERAZ);
  assert.equal(os.indeksPrzedzialu(dni, T('2026-11-19T12:00:00Z')), dni.length - 2);
  assert.equal(os.indeksPrzedzialu(dni, T('2020-01-01T00:00:00Z')), 0);
  assert.equal(os.indeksPrzedzialu(dni, T('2030-01-01T00:00:00Z')), dni.length - 1);
});

test('160: adres URL: tryb i moment razem, krok osobno, inne parametry zostają', () => {
  const s = os.parsujStanOsi('?tryb=przeszlosc&na=2026-11-18T22:59:59Z&krok=godzina&warstwy=rcb', TERAZ);
  assert.deepEqual(s, { tryb: 'przeszlosc', na: T('2026-11-18T22:59:59Z'), krok: 'godzina' });
  assert.equal(os.zapytanieOsi(s, '?warstwy=rcb&tryb=dzis'), '?warstwy=rcb&tryb=przeszlosc&na=2026-11-18T22%3A59%3A59Z&krok=godzina');
  assert.deepEqual(os.parsujStanOsi(os.zapytanieOsi(s, ''), TERAZ), s, 'zapis i odczyt dają ten sam stan');
  // TODAY i krok domyślny znikają z adresu, cudze parametry zostają
  assert.equal(os.zapytanieOsi({ tryb: 'dzis', na: null, krok: 'dzien' }, '?okres=7d&tryb=przeszlosc&na=x&krok=godzina'), '?okres=7d');
  assert.equal(os.zapytanieOsi({ tryb: 'dzis', na: null, krok: 'dzien' }, ''), '');
});

test('160: adres URL: archiwum bez poprawnego momentu to TODAY; przyszłość i zbyt stary moment są dociągane', () => {
  const dzis = { tryb: 'dzis', na: null, krok: 'dzien' };
  assert.deepEqual(os.parsujStanOsi('?tryb=przeszlosc', TERAZ), dzis);
  assert.deepEqual(os.parsujStanOsi('?tryb=przeszlosc&na=wczoraj', TERAZ), dzis);
  assert.deepEqual(os.parsujStanOsi('?tryb=przeszlosc&na=1700000000000', TERAZ), dzis, 'liczba to nie ISO');
  assert.deepEqual(os.parsujStanOsi('?na=2026-11-18T10:00:00Z', TERAZ), dzis, 'sam moment bez trybu');
  assert.deepEqual(os.parsujStanOsi('?tryb=PRZESZLOSC&na=2026-11-18T10:00:00Z', TERAZ), dzis);
  assert.equal(os.parsujStanOsi('?tryb=przeszlosc&na=2027-01-01T00:00:00Z', TERAZ).na, TERAZ);
  assert.equal(os.parsujStanOsi('?tryb=przeszlosc&na=2024-01-01T00:00:00Z', TERAZ).na, os.poczatekOsi(TERAZ));
  assert.equal(os.parsujStanOsi('?krok=minuta', TERAZ).krok, 'dzien');
  assert.equal(os.parsujStanOsi(new URLSearchParams('krok=godzina'), TERAZ).krok, 'godzina');
});

test('160: kroki suwaka po dniach: z TODAY wstecz na koniec wczoraj; naprzód z ostatniego przedziału bez zmian', () => {
  const dzis = { tryb: 'dzis', na: null, krok: 'dzien' };
  const wczoraj = os.przesun(dzis, -1, TERAZ);
  assert.equal(ISO(wczoraj), '2026-11-19T22:59:59.000Z');
  assert.equal(os.przesun(dzis, 1, TERAZ), TERAZ, 'TODAY to już koniec osi');
  const arch = { tryb: 'przeszlosc', na: wczoraj, krok: 'dzien' };
  assert.equal(os.przesun(arch, 1, TERAZ), TERAZ, 'z wczoraj naprzód: dziś = teraz');
  assert.equal(ISO(os.przesun(arch, -1, TERAZ)), '2026-11-18T22:59:59.000Z');
  // początek osi: dalej się nie da
  const pierwszy = { tryb: 'przeszlosc', na: os.poczatekOsi(TERAZ) + 1000, krok: 'dzien' };
  assert.equal(os.przesun(pierwszy, -1, TERAZ), pierwszy.na);
  assert.equal(os.naKoncu(dzis, TERAZ), true);
  assert.equal(os.naKoncu(arch, TERAZ), false);
});

test('160: kroki suwaka po godzinach przechodzą przez północ w obie strony', () => {
  const polnoc = { tryb: 'przeszlosc', na: T('2026-11-18T23:30:00Z'), krok: 'godzina' }; // 19.11, 00:30
  assert.equal(ISO(os.przesun(polnoc, -1, TERAZ)), '2026-11-18T22:59:59.000Z', '18.11, 23:59:59');
  const poznoWieczorem = { tryb: 'przeszlosc', na: T('2026-11-18T22:59:59Z'), krok: 'godzina' }; // 18.11, 23:59:59
  assert.equal(ISO(os.przesun(poznoWieczorem, 1, TERAZ)), '2026-11-18T23:59:59.000Z', '19.11, 00:59:59');
  assert.equal(ISO(os.przesun(poznoWieczorem, -1, TERAZ)), '2026-11-18T21:59:59.000Z');
  // dziś: ostatnia godzina to teraz, dalej nie ma
  const terazGodz = { tryb: 'przeszlosc', na: TERAZ, krok: 'godzina' };
  assert.equal(os.przesun(terazGodz, 1, TERAZ), TERAZ);
  // pierwsza godzina najstarszej doby: wstecz się nie da
  const najstarsza = { tryb: 'przeszlosc', na: os.poczatekOsi(TERAZ) + 1000, krok: 'godzina' };
  assert.equal(os.przesun(najstarsza, -1, TERAZ), najstarsza.na);
});

test('160: odtwarzanie: start z początku osi (oś godzin: od północy), klatki po kolei, stop na końcu', () => {
  const dzisDni = { tryb: 'dzis', na: null, krok: 'dzien' };
  const start = os.startOdtwarzania(dzisDni, TERAZ);
  assert.equal(ISO(start), '2026-10-22T21:59:59.000Z', 'koniec pierwszej doby osi');
  const dzien = { tryb: 'przeszlosc', na: T('2026-11-18T12:00:00Z'), krok: 'godzina' };
  assert.equal(os.startOdtwarzania(dzien, TERAZ), dzien.na, 'w środku osi odtwarzamy od bieżącego miejsca');
  const koniecDoby = { tryb: 'przeszlosc', na: T('2026-11-18T22:59:59Z'), krok: 'godzina' };
  assert.equal(ISO(os.startOdtwarzania(koniecDoby, TERAZ)), '2026-11-17T23:59:59.000Z', 'animacja dnia od 0:00-0:59');
  // cała doba godzinami: 23 kroki, ostatni z `koniec`
  let stan = { tryb: 'przeszlosc', na: os.startOdtwarzania(koniecDoby, TERAZ), krok: 'godzina' };
  let kroki = 0, koniec = false;
  while (!koniec && kroki < 50) { const k = os.klatkaOdtwarzania(stan, TERAZ); stan = { ...stan, na: k.na }; koniec = k.koniec; kroki++; }
  assert.equal(kroki, 23);
  assert.equal(ISO(stan.na), '2026-11-18T22:59:59.000Z');
  assert.equal(os.klatkaOdtwarzania(stan, TERAZ).koniec, true, 'na końcu osi nie przewijamy dalej');
  assert.equal(os.klatkaOdtwarzania(stan, TERAZ).na, stan.na);
});

test('160: prędkości odtwarzania i pamięć osi (krok, prędkość; śmieci odrzucone)', () => {
  assert.deepEqual(os.PREDKOSCI.map(p => p.ms), [2000, 1000, 500]);
  assert.equal(os.odstepOdtwarzania(4), 500);
  assert.equal(os.poprawnaPredkosc(3), false);
  assert.deepEqual(os.parsujPamiecOsi('{"krok":"godzina","predkosc":2,"tryb":"przeszlosc","na":"2026-11-18T10:00:00Z"}'), { krok: 'godzina', predkosc: 2 },
    'tryb i moment nie są pamiętane');
  for (const smiec of [null, '', 'nie-json', '[]', '"x"', '{"krok":"minuta","predkosc":"2"}']) assert.deepEqual(os.parsujPamiecOsi(smiec), {}, String(smiec));
});

const kubelek = (od, liczba, extra = {}) => ({ od, do: ISO(T(od) + GODZ), liczba, w_przegladzie: 0, luka_retencji: false, luka_zrodel: [], ...extra });

test('160: walidacja os/: luka nigdy nie jest zerem, zła liczba to „nie wiemy”', () => {
  const d = os.walidujOs({
    krok: 'godzina', luka_retencji: false,
    kubelki: [
      kubelek('2026-11-18T10:00:00Z', 4),
      kubelek('2026-11-18T11:00:00Z', 0, { luka_zrodel: ['wczk-lubuskie'] }),
      kubelek('2026-11-18T12:00:00Z', 0, { luka_retencji: true }),
      kubelek('2026-11-18T13:00:00Z', null),
      kubelek('2026-11-18T14:00:00Z', '5'),
      kubelek('2026-11-18T15:00:00Z', -1),
      kubelek('2026-11-18T16:00:00Z', 1.5),
      kubelek('2026-11-18T17:00:00Z', 0),
      kubelek('2026-11-18T18:00:00Z', 3, { luka_zrodel: ['imgw-hydro'] }),
      { od: 'zły', do: '2026-11-18T19:00:00Z', liczba: 1 },
      'śmieć',
    ],
    brak_danych: [{ powod: 'luka_pobierania', zrodla: ['wczk-lubuskie'], od: '2026-11-18T11:00:00Z', do: '2026-11-18T12:00:00Z' }, { zrodla: [] }],
  });
  assert.deepEqual(d.kubelki.map(k => k.liczba), [4, null, null, null, null, null, null, 0, 3]);
  assert.equal(d.pominiete, 2);
  assert.equal(d.krok, 'godzina');
  assert.equal(d.lukaRetencji, true, 'z kubełków, gdy flaga całości jest fałszywa');
  assert.equal(d.brakDanych.length, 1, 'brak bez powodu odrzucony');
  assert.equal(d.brakDanych[0].od, T('2026-11-18T11:00:00Z'));
  for (const zle of [null, [], {}, { kubelki: 'x' }, 'x']) assert.throws(() => os.walidujOs(zle), /nieznanym formacie/);
});

test('160: słupki: liczba, częściowy, brak, nieznany, ładowanie; wysokość luki to pełne kreskowanie, nie zero', () => {
  const lista = os.przedzialy(T('2026-11-18T10:00:00Z'), T('2026-11-18T15:30:00Z'), 'godzina');
  assert.equal(lista.length, 6);
  const dane = os.walidujOs({ krok: 'godzina', kubelki: [
    kubelek('2026-11-18T10:00:00Z', 8),
    kubelek('2026-11-18T11:00:00Z', 2, { luka_zrodel: ['wczk-lubuskie'] }),
    kubelek('2026-11-18T12:00:00Z', null, { luka_retencji: true }),
    kubelek('2026-11-18T13:00:00Z', 0),
    kubelek('2026-11-18T15:00:00Z', 4),
  ] });
  const s = os.scalSlupki(lista, dane, TERAZ);
  assert.deepEqual(s.map(x => x.stan), ['liczba', 'czesciowy', 'brak', 'liczba', 'nieznany', 'liczba']);
  assert.deepEqual(s.map(os.kreskowany), [false, true, true, false, true, false]);
  assert.deepEqual(os.wysokosci(s), [1, 0.25, 1, 0, 1, 0.5]);
  assert.deepEqual(os.scalSlupki(lista, undefined, TERAZ).map(x => x.stan), Array(6).fill('ladowanie'));
  assert.ok(os.scalSlupki(lista, undefined, TERAZ).every(x => !os.kreskowany(x)), 'w czasie wczytywania nie rysujemy luk');
  // opisy: luka nigdy jako „0”, częściowy jako „co najmniej”
  const opisy = s.map(x => os.opisSlupka(x, 'godzina', TERAZ));
  assert.match(opisy[0], /18 listopada, 11:00-12:00: 8 komunikatów$/);
  assert.match(opisy[1], /co najmniej 2 komunikaty, dane niepełne$/);
  assert.match(opisy[2], /brak w naszych danych$/);
  assert.match(opisy[3], /: 0 komunikatów$/);
  assert.match(opisy[4], /brak w naszych danych$/);
  for (const o of [opisy[1], opisy[2], opisy[4]]) assert.doesNotMatch(o, /: 0 /);
});

test('160: błąd osi to kreskowanie „nie wiemy”, nie pusta oś; krótkie podpisy luk i baneru są policzalne', () => {
  const lista = os.przedzialy(T('2026-11-18T10:00:00Z'), T('2026-11-18T12:30:00Z'), 'godzina');
  assert.deepEqual(os.scalSlupki(lista, undefined, TERAZ, true).map(x => x.stan), ['nieznany', 'nieznany', 'nieznany']);
  assert.ok(os.scalSlupki(lista, undefined, TERAZ, true).every(os.kreskowany));
  assert.equal(os.opisLukKrotko(os.scalSlupki(lista, undefined, TERAZ, true), 'godzina'), 'Kreskowane = brak w naszych danych, nie zero (3 godziny).');
  const pelne = os.walidujOs({ kubelki: lista.map(p => ({ od: ISO(p.od), do: ISO(p.do), liczba: 1, w_przegladzie: 0, luka_retencji: false, luka_zrodel: [] })) });
  assert.equal(os.opisLukKrotko(os.scalSlupki(lista, pelne, TERAZ), 'godzina'), 'Słupki: liczba komunikatów, nie poziom zagrożenia.');
  const braki = [
    { powod: 'luka_pobierania', zrodla: ['a'], od: null, do: null }, { powod: 'luka_pobierania', zrodla: ['b'], od: null, do: null },
    { powod: 'luka_retencji', zrodla: [], od: null, do: null },
  ];
  assert.equal(os.opisBrakowKrotko(braki, 3), 'Dane niepełne: 2 źródła bez odpowiedzi, 3 komunikaty bez wersji z tej chwili, część starszych wpisów usunięta.');
  assert.equal(os.opisBrakowKrotko([], 0), '');
  assert.equal(os.ileZrodel(5), '5 źródeł');
  assert.deepEqual(os.PREDKOSCI.map(p => p.etykieta), ['Tempo 1×', 'Tempo 2×', 'Tempo 4×'], 'widoczna etykieta, nie samo „1×”');
});

test('160: podpis luk: liczba przedziałów z odmianą, źródła po nazwie, retencja; pusty bez luk', () => {
  const lista = os.przedzialy(T('2026-11-10T12:00:00Z'), T('2026-11-15T12:00:00Z'), 'dzien');
  const dane = os.walidujOs({ kubelki: lista.map((p, i) => ({
    od: ISO(p.od), do: ISO(p.do), liczba: i < 2 ? null : 1, w_przegladzie: 0, luka_retencji: i === 0, luka_zrodel: i === 1 || i === 2 ? ['wczk-lubuskie'] : [],
  })) });
  const s = os.scalSlupki(lista, dane, TERAZ);
  const tekst = os.opisLuk(s, 'dzien', slug => (slug === 'wczk-lubuskie' ? 'WCZK lubuskie' : slug));
  assert.equal(tekst, 'Kreskowane: brak w naszych danych, nie zero (3 dni): nie odpowiadało: WCZK lubuskie; część starszych wpisów usunięto zgodnie z zasadami przechowywania.');
  assert.equal(os.opisLuk(s.filter(x => !os.kreskowany(x)), 'dzien'), '');
  assert.equal(os.ileDni(1), '1 dzień');
  assert.equal(os.ileGodzin(2), '2 godziny');
  assert.equal(os.ileGodzin(12), '12 godzin');
  assert.equal(os.ileGodzin(22), '22 godziny');
});

test('160: wpisy/?na=: rekord brak_danych liczony osobno (nie jako zły format), luki stanu opisane', () => {
  const wpis = { id: 1, warstwa: 'rcb', tytul: 'Alert', opublikowano_at: '2026-11-18T10:00:00Z', teryt: ['06'], zasieg: 'obszar' };
  const s = os.walidujStroneNa({
    next: null, na: '2026-11-18T22:59:59Z', luka_retencji: true,
    results: [wpis, { id: 2, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', brak_danych: true, powod: 'historia_niepelna' }, { id: 3 }],
    brak_danych: [{ powod: 'luka_pobierania', zrodla: ['imgw-hydro'], od: null, do: '2026-11-18T22:59:59Z' }, { powod: 'luka_retencji', zrodla: [], od: null, do: '2026-10-20T00:00:00Z' }],
  });
  assert.equal(s.wyniki.length, 1);
  assert.equal(s.bezHistorii, 1);
  assert.equal(s.pominiete, 1);
  assert.equal(s.nastepna, false);
  assert.equal(s.na, '2026-11-18T22:59:59Z');
  assert.equal(s.lukaRetencji, true);
  assert.equal(s.brakDanych[0].od, null, 'od = null: początku luki nie znamy');
  assert.equal(os.opisBrakowNa(s.brakDanych, s.bezHistorii, () => 'Hydro IMGW'),
    'Dane niepełne: w tej chwili nie odpowiadało: Hydro IMGW; 1 komunikat bez wersji z tej chwili (nie pokazujemy); część starszych wpisów usunięto zgodnie z zasadami przechowywania.');
  assert.equal(os.opisBrakowNa([], 0), '');
  assert.throws(() => os.walidujStroneNa({ results: [] }), /nieznanym formacie/);
  assert.throws(() => os.walidujStroneNa({ results: 'x', next: null }), /nieznanym formacie/);
});

test('160: etykieta stanu zawsze mówi „Stan na”; archiwum podaje dzień i godzinę', () => {
  assert.equal(os.etykietaStanu({ tryb: 'dzis', na: null, krok: 'dzien' }, TERAZ, T('2026-11-20T13:36:00Z')), 'Stan na teraz, odświeżone o 14:36');
  assert.equal(os.etykietaStanu({ tryb: 'dzis', na: null, krok: 'dzien' }, TERAZ), 'Stan na teraz');
  assert.equal(os.etykietaStanu({ tryb: 'przeszlosc', na: T('2026-11-18T22:59:59Z'), krok: 'dzien' }, TERAZ), 'Stan na 18 listopada, godz. 23:59');
  assert.equal(os.etykietaStanu({ tryb: 'przeszlosc', na: T('2026-11-19T22:59:59Z'), krok: 'dzien' }, TERAZ), 'Stan na wczoraj, godz. 23:59');
  assert.equal(os.etykietaStanu({ tryb: 'przeszlosc', na: T('2026-11-20T09:59:59Z'), krok: 'godzina' }, TERAZ), 'Stan na dziś, godz. 10:59');
  assert.match(os.opisMomentu(T('2025-12-31T12:00:00Z'), TERAZ), /31 grudnia 2025/, 'inny rok z rokiem');
  assert.equal(os.opisOkna('24h', true), 'Komunikaty z 24 godzin przed tą chwilą.');
  assert.equal(os.opisOkna('1h', false), 'Komunikaty z ostatniej godziny.');
});

test('160: podpisy pod osią: dni (ostatni „dziś” przy prawej krawędzi), godziny co 6', () => {
  const dni = os.przedzialyOsi({ tryb: 'dzis', na: null, krok: 'dzien' }, TERAZ);
  const p = os.podpisyOsi(dni, 'dzien', TERAZ);
  assert.equal(p.length, 4);
  assert.deepEqual([p[0].wyrownanie, p[0].pozycja], ['start', 0]);
  assert.deepEqual([p[3].tekst, p[3].wyrownanie, p[3].pozycja], ['dziś', 'koniec', 100]);
  const godz = os.przedzialyOsi({ tryb: 'przeszlosc', na: T('2026-11-18T12:00:00Z'), krok: 'godzina' }, TERAZ);
  assert.deepEqual(os.podpisyOsi(godz, 'godzina', TERAZ).map(x => [x.tekst, x.pozycja]), [['00:00', 0], ['06:00', 25], ['12:00', 50], ['18:00', 75]]);
});

test('160: dane próbne osi przechodzą walidację, mają lukę źródła i retencję, a luka bez liczby nie jest zerem', () => {
  const z = os.zakresOsi('dzien', null, TERAZ);
  const wpisy = [{ opublikowano_at: ISO(TERAZ - 5 * 86_400_000), pewnosc_lokalizacji: 1, klasa: 'zwykly' }, { opublikowano_at: ISO(TERAZ - GODZ), pewnosc_lokalizacji: 0.5, klasa: 'zwykly' }];
  const d = os.walidujOs(os.probnaOs(z.od, z.do, 'dzien', TERAZ, wpisy));
  assert.equal(d.kubelki.length, 30);
  assert.equal(d.pominiete, 0);
  assert.ok(d.kubelki.some(k => k.lukaZrodel.length && k.liczba === 1), 'luka częściowa (jest wpis)');
  assert.ok(d.kubelki.some(k => k.lukaZrodel.length && k.liczba === null), 'luka bez liczby');
  assert.ok(d.kubelki.some(k => k.lukaRetencji));
  assert.ok(d.kubelki.every(k => !(k.liczba === 0 && (k.lukaRetencji || k.lukaZrodel.length))));
  assert.equal(d.kubelki.at(-1).liczba, 0, 'wpis z pewnością 0,5 nie wchodzi do histogramu');
  assert.equal(os.probneBrakiNa(TERAZ - 5 * 86_400_000, TERAZ).length, 1);
  assert.equal(os.probneBrakiNa(TERAZ - GODZ, TERAZ).length, 0);
  assert.equal(os.isoSekundy(T('2026-11-18T22:59:59.999Z')), '2026-11-18T22:59:59Z');
});

// „Teraz” (W2): łącze i zdrowie źródeł, czysta logika (zrodla.ts): kontrakt z backendem (rodzaje łącza, kody błędów), stany zdrowia,
// zdanie „brak w naszych danych: źródło X, od <data>”, walidacja odpowiedzi zrodla/ i stany danych (ładowanie, awaria, nieaktualne).
// node --test, bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { read, dir, utworzLoader } = require('./150-zrodla-loader.cjs');

const load = utworzLoader();
const z = () => load(`${dir}/zrodla`);
const probne = () => load(`${dir}/dane-probne/zrodla`);

// 20.11.2026, 13:00 w Warszawie (CET, UTC+1)
const TERAZ = Date.parse('2026-11-20T12:00:00Z');
const baza = { slug: 'wczk', nazwa: 'WCZK lubuskie', instytucja: 'WCZK', warstwa: 'urzedy', atrybucja: '', rodzaj_lacza: 'scraping', czestotliwosc_s: 300 };
const zrodlo = (reszta = {}) => ({ ...baza, ostatni_sukces_at: '2026-11-20T11:50:00Z', ostatni_blad: null, luka: false, ...reszta });

test('rodzaje łącza: dokładnie wartości kontraktu backendu, w kolejności ze zlecenia, każdy z etykietą i opisem po polsku', () => {
  const python = read('../backend/teraz/models.py');
  const blok = python.slice(python.indexOf('class RodzajLacza'), python.indexOf('# Domyślny rodzaj łącza'));
  const zBackendu = [...blok.matchAll(/^\s+[A-Z]+ = "([a-z]+)"/gm)].map(m => m[1]);
  assert.deepEqual([...z().KOLEJNOSC_LACZ].sort(), [...zBackendu].sort(), 'te same rodzaje co models.Zrodlo.RodzajLacza');
  assert.deepEqual(z().KOLEJNOSC_LACZ.map(k => z().LACZA[k].etykieta), ['X', 'API', 'MCI', 'RSS', 'scraping', 'WebSocket', 'plik', 'ręcznie']);
  for (const k of [...z().KOLEJNOSC_LACZ, 'nieznane']) {
    const m = z().LACZA[k];
    assert.equal(m.kod, k);
    assert.ok(m.etykieta.length > 0 && m.opis.length > 20, `opis ${k}`);
    assert.match(m.opis, /[ąćęłńóśźż ]/, `opis ${k} jest po polsku`);
  }
});

test('metaLacza: pusta i nieznana wartość to „nieznane”, nie zgadujemy', () => {
  for (const wartosc of ['', null, undefined, 'ftp', 'API', 'Scraping']) assert.equal(z().metaLacza(wartosc).kod, 'nieznane', String(wartosc));
  for (const k of z().KOLEJNOSC_LACZ) assert.equal(z().metaLacza(k).kod, k);
});

test('kody błędów z backendu mają opis po polsku, nieznany kod jest pokazany z kodem', () => {
  const historia = read('../backend/teraz/historia.py');
  for (const nazwa of ['KOD_WSTRZYMANIA', 'KOD_HTTP', 'KOD_OGOLNY']) {
    const kod = new RegExp(`^${nazwa} = "([a-z_]+)"`, 'm').exec(historia)?.[1];
    assert.ok(kod, nazwa);
    assert.ok(z().KODY_BLEDOW[kod], `brak opisu kodu ${kod}`);
  }
  assert.match(z().opisBledu('blad_http'), /Serwer źródła odpowiedział błędem/);
  assert.match(z().opisBledu('cos_nowego'), /Nieznany kod błędu: cos_nowego/);
});

test('stanZdrowia: wstrzymane > błąd > luka > działa', () => {
  const { stanZdrowia } = z();
  assert.equal(stanZdrowia({ ostatni_blad: null, luka: false }), 'dziala');
  assert.equal(stanZdrowia({ ostatni_blad: null, luka: true }), 'luka');
  assert.equal(stanZdrowia({ ostatni_blad: 'blad_http', luka: false }), 'blad');
  assert.equal(stanZdrowia({ ostatni_blad: 'blad_zrodla', luka: true }), 'blad');
  assert.equal(stanZdrowia({ ostatni_blad: 'dostep_wstrzymany', luka: true }), 'wstrzymane');
  assert.equal(stanZdrowia({ ostatni_blad: 'dostep_wstrzymany', luka: false }), 'wstrzymane');
  assert.equal(stanZdrowia({ ostatni_blad: 'kod_z_przyszlosci', luka: false }), 'blad', 'nieznany kod błędu nie jest „działa”');
  for (const s of z().KOLEJNOSC_ZDROWIA) assert.ok(z().ZDROWIE[s].znak && z().ZDROWIE[s].slowo, `znak i słowo: ${s}`);
  assert.deepEqual(z().KOLEJNOSC_ZDROWIA.map(s => z().ZDROWIE[s].znak), ['●', '◐', '✕', '‖']);
});

test('opisBraku: „brak w naszych danych: źródło X, od <data>” dla luki i błędu, null dla źródła, które działa', () => {
  const { opisBraku } = z();
  assert.equal(opisBraku(zrodlo(), TERAZ), null);
  assert.equal(opisBraku(zrodlo({ luka: true, ostatni_sukces_at: '2026-11-17T20:40:00Z' }), TERAZ), 'brak w naszych danych: źródło WCZK lubuskie, od 17 listopada, godz. 21:40');
  assert.equal(opisBraku(zrodlo({ luka: true, ostatni_sukces_at: '2026-11-19T20:40:00Z' }), TERAZ), 'brak w naszych danych: źródło WCZK lubuskie, od wczoraj, godz. 21:40');
  assert.equal(opisBraku(zrodlo({ ostatni_blad: 'blad_http', ostatni_sukces_at: '2026-11-20T10:12:00Z' }), TERAZ), 'brak w naszych danych: źródło WCZK lubuskie, od godz. 11:12');
  assert.equal(opisBraku(zrodlo({ luka: true, ostatni_sukces_at: null }), TERAZ), 'brak w naszych danych: źródło WCZK lubuskie, nie mamy żadnego udanego pobrania');
  assert.equal(opisBraku(zrodlo({ ostatni_blad: 'dostep_wstrzymany', luka: false }), TERAZ).startsWith('brak w naszych danych: źródło WCZK lubuskie, od '), true);
});

test('żaden tekst o stanie źródła nie mówi „bez komunikatów”, „spokojnie” ani „bezpiecznie”', () => {
  const wszystkie = [
    ...Object.values(z().KODY_BLEDOW), ...Object.values(z().LACZA).map(m => m.opis),
    ...Object.values(z().ZDROWIE).map(m => m.opis),
    ...probne().probneZrodla(TERAZ).map(s => z().opisBraku(s, TERAZ) ?? ''),
    z().komunikatZrodel({ niedostepne: true }), z().komunikatZrodel({ nieaktualne: true }), z().komunikatZrodel({ pominiete: 2 }),
  ];
  for (const t of wszystkie) assert.ok(!/bez komunikat|spokojn|bezpieczn/i.test(t), t);
});

test('podsumujZrodla liczy każdy stan osobno', () => {
  const lista = [zrodlo(), zrodlo({ slug: 'b' }), zrodlo({ slug: 'c', luka: true }), zrodlo({ slug: 'd', ostatni_blad: 'blad_http' }), zrodlo({ slug: 'e', ostatni_blad: 'dostep_wstrzymany' })];
  assert.deepEqual({ ...z().podsumujZrodla(lista) }, { razem: 5, dziala: 2, luka: 1, blad: 1, wstrzymane: 1, problemy: 3 });
  assert.deepEqual({ ...z().podsumujZrodla([]) }, { razem: 0, dziala: 0, luka: 0, blad: 0, wstrzymane: 0, problemy: 0 });
});

test('walidujZrodla: poprawny rekord, brakujące pola liczone na niekorzyść danych, zła struktura to wyjątek', () => {
  const { walidujZrodla, BladFormatu } = { ...z(), ...load(`${dir}/walidacja`) };
  const ok = walidujZrodla([{ ...zrodlo(), ostatni_sukces_at: '2026-11-20T11:50:00Z' }]);
  assert.equal(ok.pominiete, 0);
  assert.equal(ok.zrodla[0].rodzaj_lacza, 'scraping');
  assert.equal(ok.zrodla[0].luka, false);
  // brak pola luka: nie zakładamy, że wszystko działa
  const { luka, ...bezLuki } = zrodlo();
  assert.equal(walidujZrodla([bezLuki]).zrodla[0].luka, true);
  // pusty kod błędu to brak błędu, pole złego typu to błąd ogólny, zły czas to brak sukcesu
  assert.equal(walidujZrodla([zrodlo({ ostatni_blad: '' })]).zrodla[0].ostatni_blad, null);
  assert.equal(walidujZrodla([zrodlo({ ostatni_blad: 5 })]).zrodla[0].ostatni_blad, 'blad_zrodla');
  assert.equal(walidujZrodla([zrodlo({ ostatni_sukces_at: 'wczoraj' })]).zrodla[0].ostatni_sukces_at, null);
  // rodzaj łącza zostaje surowy (metaLacza zrobi z niego „nieznane”)
  assert.equal(walidujZrodla([zrodlo({ rodzaj_lacza: 'ftp' })]).zrodla[0].rodzaj_lacza, 'ftp');
  assert.equal(walidujZrodla([zrodlo({ rodzaj_lacza: undefined })]).zrodla[0].rodzaj_lacza, '');
  // rekordy bez slug albo nazwy są pomijane i liczone
  const czesc = walidujZrodla([zrodlo(), { nazwa: 'bez sluga' }, null, zrodlo({ slug: 'x', nazwa: '' })]);
  assert.equal(czesc.zrodla.length, 1);
  assert.equal(czesc.pominiete, 3);
  assert.deepEqual({ ...walidujZrodla([]) }, { zrodla: [], pominiete: 0 });
  for (const zle of [null, {}, 'x', 5, { results: [] }]) assert.throws(() => walidujZrodla(zle), BladFormatu, JSON.stringify(zle));
  assert.throws(() => walidujZrodla([null, 5, {}]), BladFormatu, 'same złe rekordy to awaria, nie „brak źródeł”');
});

test('daneZrodel: ładowanie, awaria bez danych, awaria z wcześniejszymi danymi i sukces to cztery różne stany', () => {
  const { daneZrodel, komunikatZrodel } = z();
  const wynik = { zrodla: [zrodlo()], pominiete: 0 };
  const laduje = daneZrodel({ isPending: true, isError: false, dataUpdatedAt: 0 });
  assert.deepEqual([laduje.ladowanie, laduje.niedostepne, laduje.nieaktualne, laduje.lista], [true, false, false, undefined]);
  const awaria = daneZrodel({ isPending: false, isError: true, dataUpdatedAt: 0 });
  assert.deepEqual([awaria.ladowanie, awaria.niedostepne, awaria.nieaktualne, awaria.lista], [false, true, false, undefined]);
  const stare = daneZrodel({ data: wynik, isPending: false, isError: true, dataUpdatedAt: 1234 });
  assert.deepEqual([stare.niedostepne, stare.nieaktualne, stare.lista.length, stare.pobranoMs], [false, true, 1, 1234]);
  const dobre = daneZrodel({ data: wynik, isPending: false, isError: false, dataUpdatedAt: 99 });
  assert.deepEqual([dobre.niedostepne, dobre.nieaktualne, dobre.pobranoMs], [false, false, 99]);
  assert.equal(komunikatZrodel(dobre), null);
  assert.match(komunikatZrodel(awaria), /Nie udało się pobrać stanu źródeł, więc nie wiemy, które działają/);
  assert.ok(!/brak danych/i.test(komunikatZrodel(awaria)), 'awaria to nie „brak danych”');
  assert.match(komunikatZrodel(stare), /Nie udało się odświeżyć stanu źródeł/);
  assert.match(komunikatZrodel(daneZrodel({ data: { zrodla: [], pominiete: 2 }, isPending: false, isError: false, dataUpdatedAt: 1 })), /Pominięto źródła o nieznanym formacie: 2/);
});

test('znajdzZrodlo i zrodlaWarstwy', () => {
  const dane = z().daneZrodel({ data: { zrodla: [zrodlo({ slug: 'a', warstwa: 'rcb' }), zrodlo({ slug: 'b', warstwa: 'cyber' })], pominiete: 0 }, isPending: false, isError: false, dataUpdatedAt: 1 });
  assert.equal(z().znajdzZrodlo(dane, 'b').warstwa, 'cyber');
  assert.equal(z().znajdzZrodlo(dane, 'nie-ma'), undefined);
  assert.equal(z().znajdzZrodlo(undefined, 'a'), undefined);
  assert.deepEqual(z().zrodlaWarstwy(dane, 'rcb').map(s => s.slug), ['a']);
  assert.deepEqual(z().zrodlaWarstwy(undefined, 'rcb'), []);
});

test('dane próbne źródeł: ten sam format co API, zgodne z warstwami próbnymi, pokrywają wszystkie stany', () => {
  const lista = probne().probneZrodla(TERAZ);
  const slugiWarstw = load(`${dir}/dane-probne/index`).probneWarstwy(TERAZ).flatMap(w => w.zrodla.map(s => s.slug));
  assert.deepEqual(lista.map(s => s.slug).sort(), [...slugiWarstw].sort());
  const wynik = z().walidujZrodla(lista);
  assert.equal(wynik.pominiete, 0, 'format zgodny z walidacją kontraktu');
  const stany = new Set(lista.map(s => z().stanZdrowia(s)));
  assert.deepEqual([...stany].sort(), ['blad', 'dziala', 'wstrzymane'], 'działa, błąd i dostęp wstrzymany (luka bez błędu pokrywa test logiki)');
  const wstrzymane = lista.find(s => s.ostatni_blad === 'dostep_wstrzymany');
  assert.equal(z().opisBraku(wstrzymane, TERAZ), `brak w naszych danych: źródło ${wstrzymane.nazwa}, od 17 listopada, godz. 13:00`);
  assert.ok(lista.every(s => z().metaLacza(s.rodzaj_lacza).kod !== 'nieznane'), 'każde próbne źródło ma znany rodzaj łącza');
});

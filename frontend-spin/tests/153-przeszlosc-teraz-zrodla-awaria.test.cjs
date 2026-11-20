// „Teraz” (W2): pobieranie GET /api/teraz/zrodla/ z obsługą awarii. Każda awaria (sieć, kod HTTP, nie-JSON, zła struktura) kończy się
// błędem zapytania, który interfejs pokazuje jako „stan źródeł niedostępny”; nigdy pustą listą ani „wszystko działa”. node --test.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { dir, utworzLoader } = require('./150-zrodla-loader.cjs');

let wywolania = [];
let odpowiedz = () => { throw new Error('fetch nie jest podstawiony'); };
let opcje = null;
const mocks = { '@tanstack/react-query': { useQuery: o => { opcje = o; return {}; } } };
const load = utworzLoader(mocks, { fetch: (...args) => { wywolania.push(args); return odpowiedz(...args); } });
const api = () => load(`${dir}/api`);
const zr = () => load(`${dir}/zrodla`);

const json = (tresc, status = 200) => () => Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(tresc) });
const surowe = (reszta = {}) => ({
  slug: 'rcb', nazwa: 'Alert RCB', instytucja: 'RCB', warstwa: 'rcb', atrybucja: '', rodzaj_lacza: 'scraping', czestotliwosc_s: 60,
  ostatni_sukces_at: '2026-11-20T11:59:00Z', ostatni_blad: null, luka: false, ...reszta,
});
const pobierzZrodla = () => api().pobierz('zrodla', {}, undefined, zr().walidujZrodla);

test('pobranie: poprawna odpowiedź to zwalidowana lista z adresu /api/teraz/zrodla/', async () => {
  wywolania = [];
  odpowiedz = json([surowe(), surowe({ slug: 'emsc', nazwa: 'EMSC', rodzaj_lacza: 'websocket' })]);
  const wynik = await pobierzZrodla();
  assert.equal(wynik.zrodla.length, 2);
  assert.equal(wynik.pominiete, 0);
  assert.equal(wywolania[0][0], '/api/teraz/zrodla/');
  assert.equal(wywolania[0][1].headers.Accept, 'application/json');
});

test('pobranie: awaria sieci, kod HTTP, nie-JSON i zła struktura to BladApi (nie pusta lista)', async () => {
  const { BladApi } = api();
  const przypadki = [
    ['brak sieci', () => Promise.reject(new TypeError('Failed to fetch')), 0, /Brak połączenia z serwerem/],
    ['HTTP 500', json({ detail: 'x' }, 500), 500, /błędem 500/],
    ['HTTP 404', json({}, 404), 404, /błędem 404/],
    ['HTTP 429', json({}, 429), 429, /błędem 429/],
    ['nie-JSON', () => Promise.resolve({ ok: true, status: 200, json: () => Promise.reject(new SyntaxError('Unexpected token <')) }), 200, /nieznanym formacie/],
    ['obiekt zamiast tablicy', json({ results: [] }), 200, /nieznanym formacie \(zrodla\)/],
    ['null', json(null), 200, /nieznanym formacie/],
    ['same złe rekordy', json([null, 5, { nazwa: 'bez sluga' }]), 200, /nieznanym formacie \(zrodla\)/],
  ];
  for (const [opis, impl, status, wzor] of przypadki) {
    wywolania = [];
    odpowiedz = impl;
    await assert.rejects(pobierzZrodla(), e => {
      assert.ok(e instanceof BladApi, `${opis}: BladApi`);
      assert.equal(e.status, status, `${opis}: status`);
      assert.match(e.message, wzor, opis);
      return true;
    }, opis);
  }
});

test('pobranie: przerwanie zapytania (AbortError) nie jest awarią źródeł', async () => {
  const przerwanie = Object.assign(new Error('przerwano'), { name: 'AbortError' });
  odpowiedz = () => Promise.reject(przerwanie);
  await assert.rejects(pobierzZrodla(), e => e === przerwanie);
});

test('puste źródła z poprawnej odpowiedzi to „serwer nie podał źródeł”, nie awaria i nie „wszystko działa”', async () => {
  odpowiedz = json([]);
  const wynik = await pobierzZrodla();
  assert.deepEqual({ ...wynik }, { zrodla: [], pominiete: 0 });
  const dane = zr().daneZrodel({ data: wynik, isPending: false, isError: false, dataUpdatedAt: 1 });
  assert.equal(dane.niedostepne, false);
  assert.deepEqual(dane.lista, []);
});

test('każda awaria pobrania daje stan „niedostępne” z komunikatem po polsku, a z wcześniejszymi danymi „nieaktualne”', async () => {
  const wczesniej = { zrodla: [zr().walidujZrodla([surowe()]).zrodla[0]], pominiete: 0 };
  for (const impl of [() => Promise.reject(new TypeError('x')), json({}, 503), json({ a: 1 })]) {
    odpowiedz = impl;
    let blad = null;
    try { await pobierzZrodla(); } catch (e) { blad = e; }
    assert.ok(blad, 'awaria');
    const bez = zr().daneZrodel({ isPending: false, isError: true, dataUpdatedAt: 0 });
    assert.equal(bez.niedostepne, true);
    assert.equal(bez.lista, undefined, 'po awarii bez danych nie ma listy, którą można by wziąć za pustą');
    assert.match(zr().komunikatZrodel(bez), /nie wiemy, które działają/);
    const z_danymi = zr().daneZrodel({ data: wczesniej, isPending: false, isError: true, dataUpdatedAt: 5 });
    assert.equal(z_danymi.niedostepne, false);
    assert.equal(z_danymi.nieaktualne, true);
    assert.equal(z_danymi.lista.length, 1);
  }
});

test('useZrodla: własny klucz zapytania, odświeżanie co 60 s, tryb próbny bez sieci', async () => {
  const { useZrodla, ODSWIEZANIE_ZRODEL_MS } = load(`${dir}/zrodla-api`);
  assert.equal(ODSWIEZANIE_ZRODEL_MS, 60_000);
  const sygnal = new AbortController().signal;

  wywolania = [];
  useZrodla(false);
  assert.deepEqual(opcje.queryKey, ['teraz', 'zrodla', false]);
  assert.equal(opcje.refetchInterval, 60_000);
  assert.equal(opcje.staleTime, 30_000);
  assert.equal(opcje.refetchOnWindowFocus, true, 'po powrocie do karty odświeżenie od razu');
  assert.equal(opcje.refetchIntervalInBackground, false);
  assert.equal(opcje.retry, 1);
  odpowiedz = json([surowe()]);
  const zSieci = await opcje.queryFn({ signal: sygnal });
  assert.equal(zSieci.zrodla.length, 1);
  assert.equal(wywolania.length, 1);
  assert.equal(wywolania[0][1].signal, sygnal);

  wywolania = [];
  useZrodla(true);
  assert.deepEqual(opcje.queryKey, ['teraz', 'zrodla', true]);
  const probne = await opcje.queryFn({ signal: sygnal });
  assert.ok(probne.zrodla.length > 3);
  assert.equal(wywolania.length, 0, 'tryb próbny nie wysyła żadnego zapytania');
});

test('zapytania stanu, warstw i wpisów nie zmieniły ustawień (api.ts: tylko eksport wspolne i co)', () => {
  const m = api();
  assert.equal(m.wspolne.retry, 1);
  assert.equal(typeof m.co, 'function');
  assert.deepEqual({ ...m.co(30_000) }, { refetchInterval: 30_000, staleTime: 15_000 });
  assert.equal(m.ODSWIEZANIE_MS, 30_000);
});

// „Teraz” (W2): łącze i zdrowie źródeł na renderze komponentów i całej strony (react-dom/server, useQuery podstawiony):
// etykieta łącza (8 rodzajów + nieznane: ikona i słowo), zdrowie źródła (znak i słowo, „brak w naszych danych”), panel źródeł,
// legenda „Skąd i jak”, etykiety w panelu warstw, na karcie i w liście, awaria pobrania źródeł jako komunikat. node --test.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { dir, utworzLoader, tekst } = require('./150-zrodla-loader.cjs');

const zapytania = { stan: {}, warstwy: {}, wpisy: {}, 'wpisy-powiatow': {}, zdarzenia: {}, zrodla: {} };
const opcje = {};
const mocks = {
  '@tanstack/react-query': { useQuery: o => { opcje[o.queryKey[1]] = o; return zapytania[o.queryKey[1]] ?? {}; } },
  'next/dynamic': () => function MapaZastepcza() { return React.createElement('div', { 'data-mapa': '' }); },
  '../ui': { useStandalone() {} },
};
const load = utworzLoader(mocks);
const h = (komponent, props) => renderToStaticMarkup(React.createElement(komponent, props));
const z = () => load(`${dir}/zrodla`);
const d = () => load(`${dir}/dane-probne/index`);
const udane = data => ({ isSuccess: true, isPending: false, isError: false, isPlaceholderData: false, data, dataUpdatedAt: Date.now() });
const awaria = () => ({ isSuccess: false, isPending: false, isError: true, data: undefined, dataUpdatedAt: 0 });

const TERAZ = Date.parse('2026-11-20T12:00:00Z');
const dane = (lista = load(`${dir}/dane-probne/zrodla`).probneZrodla(), reszta = {}) =>
  ({ ...z().daneZrodel({ data: { zrodla: lista, pominiete: 0 }, isPending: false, isError: false, dataUpdatedAt: TERAZ }), ...reszta });
const daneAwaria = () => z().daneZrodel({ isPending: false, isError: true, dataUpdatedAt: 0 });
const daneLaduje = () => z().daneZrodel({ isPending: true, isError: false, dataUpdatedAt: 0 });
const surowe = (reszta = {}) => ({
  slug: 'wczk', nazwa: 'WCZK lubuskie', instytucja: 'WCZK', warstwa: 'urzedy', atrybucja: '', rodzaj_lacza: 'scraping', czestotliwosc_s: 300,
  ostatni_sukces_at: '2026-11-20T11:50:00Z', ostatni_blad: null, luka: false, ...reszta,
});

// ---------- etykieta łącza ----------

test('ZrodloBadge: każdy z 8 rodzajów ma ikonę, słowo i opis; kolor nie jest jedynym nośnikiem', () => {
  const { ZrodloBadge } = load(`${dir}/ZrodloBadge`);
  const oczekiwane = { x: 'X', api: 'API', mci: 'MCI', rss: 'RSS', scraping: 'scraping', websocket: 'WebSocket', plik: 'plik', reczne: 'ręcznie', nieznane: 'nieznane' };
  for (const [kod, etykieta] of Object.entries(oczekiwane)) {
    const html = h(ZrodloBadge, { rodzaj: kod === 'nieznane' ? 'ftp' : kod });
    assert.match(html, new RegExp(`data-lacze="${kod}"`), kod);
    assert.match(html, /<svg[^>]*aria-hidden="true"/, `ikona ${kod}`);
    assert.equal(tekst(html), `Łącze: ${etykieta}`, `słowo ${kod}: czytnik ekranu czyta „Łącze: ${etykieta}”`);
    assert.match(html, /title="[^"]+: [^"]{20,}"/, `opis po polsku w podpowiedzi ${kod}`);
  }
  assert.equal(tekst(h(ZrodloBadge, { rodzaj: null })), 'Łącze: nieznane');
});

test('ZrodloBadgeWpisu: nic bez danych albo w trakcie pobierania, „nieznane” po awarii i dla źródła spoza listy', () => {
  const { ZrodloBadgeWpisu } = load(`${dir}/ZrodloBadge`);
  assert.equal(h(ZrodloBadgeWpisu, { zrodla: undefined, slug: 'emsc' }), '');
  assert.equal(h(ZrodloBadgeWpisu, { zrodla: daneLaduje(), slug: 'emsc' }), '');
  assert.equal(tekst(h(ZrodloBadgeWpisu, { zrodla: dane(), slug: 'emsc' })), 'Łącze: WebSocket');
  assert.equal(tekst(h(ZrodloBadgeWpisu, { zrodla: daneAwaria(), slug: 'emsc' })), 'Łącze: nieznane');
  assert.equal(tekst(h(ZrodloBadgeWpisu, { zrodla: dane(), slug: 'nie-ma-takiego' })), 'Łącze: nieznane');
});

// ---------- zdrowie źródła ----------

test('ZdrowieZrodla: znak i słowo; luka i błąd to „brak w naszych danych: źródło X, od <data>”', () => {
  const { ZdrowieZrodla } = load(`${dir}/ZdrowieZrodla`);
  const PREFIKS = 'Stan źródła: ';
  // każde słowo stanu ma dla czytnika podmiot („Stan źródła: ”), żeby „działa” czy „wstrzymane” nie stało samo
  const wiersz = (reszta, pelny = true) => {
    const t = tekst(h(ZdrowieZrodla, { zrodlo: surowe(reszta), pelny, teraz: TERAZ }));
    assert.ok(t.startsWith(PREFIKS), t);
    return t.slice(PREFIKS.length);
  };

  const dziala = wiersz({});
  assert.match(dziala, /^● działa/);
  assert.match(dziala, /Ostatnie udane pobranie: dziś o godz\. 12:50\./);
  assert.ok(!/Brak w naszych danych/.test(dziala), 'źródło, które działa, nie ma zdania o braku');

  const luka = wiersz({ luka: true, ostatni_sukces_at: '2026-11-17T20:40:00Z' });
  assert.match(luka, /^◐ luka w danych/);
  assert.match(luka, /Brak w naszych danych: źródło WCZK lubuskie, od 17 listopada, godz\. 21:40\./);

  const blad = wiersz({ ostatni_blad: 'blad_http', luka: true, ostatni_sukces_at: '2026-11-20T10:12:00Z' });
  assert.match(blad, /^✕ błąd pobierania/);
  assert.match(blad, /Serwer źródła odpowiedział błędem\./);
  assert.match(blad, /Brak w naszych danych: źródło WCZK lubuskie, od godz\. 11:12\./);

  const wstrzymane = wiersz({ ostatni_blad: 'dostep_wstrzymany', luka: true, ostatni_sukces_at: '2026-11-15T14:00:00Z' });
  assert.match(wstrzymane, /^‖ wstrzymane/);
  assert.match(wstrzymane, /Dostęp wstrzymany: źródło odmówiło dostępu/);

  const nigdy = wiersz({ luka: true, ostatni_sukces_at: null });
  assert.match(nigdy, /Ostatnie udane pobranie: brak, nigdy się nie udało\./);
  assert.match(nigdy, /Brak w naszych danych: źródło WCZK lubuskie, nie mamy żadnego udanego pobrania\./);

  const nieznanyKod = wiersz({ ostatni_blad: 'kod_z_przyszlosci' });
  assert.match(nieznanyKod, /Nieznany kod błędu: kod_z_przyszlosci/);

  // jedna linia: znak, słowo i czas
  assert.match(wiersz({}, false), /^● działa · ostatnie udane pobranie: dziś o godz\. 12:50$/);
  assert.match(tekst(h(ZdrowieZrodla, { zrodlo: undefined })), /^\? stan źródła nieznany$/);
  // znak jest dekoracją, słowo niesie znaczenie
  assert.match(h(ZdrowieZrodla, { zrodlo: surowe({}), teraz: TERAZ }), /<span class="tz-zdrowie__znak" aria-hidden="true">●<\/span>/);
});

test('StanZrodlaWpisu: ładowanie, awaria, źródło spoza listy i stan znany to osobne teksty', () => {
  const { StanZrodlaWpisu } = load(`${dir}/ZdrowieZrodla`);
  const t = zrodla => tekst(h(StanZrodlaWpisu, { zrodla, slug: 'imgw-hydro', teraz: Date.now() }));
  assert.match(t(daneLaduje()), /^Wczytujemy stan źródła…$/);
  const po_awarii = t(daneAwaria());
  assert.match(po_awarii, /stan źródła nieznany/);
  assert.match(po_awarii, /Nie udało się pobrać stanu źródeł, więc nie wiemy, które działają/);
  assert.ok(!/brak danych/i.test(po_awarii) && !/● działa/.test(po_awarii), 'awaria nie udaje ani braku danych, ani działania');
  assert.match(tekst(h(StanZrodlaWpisu, { zrodla: dane(), slug: 'nie-ma' })), /Tego źródła nie ma na liście źródeł/);
  assert.match(t(dane()), /✕ błąd pobierania.*Brak w naszych danych: źródło Ostrzeżenia hydrologiczne IMGW, od /);
});

test('ZnakProblemuZrodla: tylko dla źródeł z luką, błędem albo wstrzymanych', () => {
  const { ZnakProblemuZrodla } = load(`${dir}/ZdrowieZrodla`);
  const znak = slug => tekst(h(ZnakProblemuZrodla, { zrodla: dane(), slug }));
  assert.equal(znak('emsc'), '');
  assert.equal(znak('rcb-gov-pl'), '');
  // widoczne jest słowo stanu; pełne zdanie o braku dostaje też czytnik (title nie działa na dotyku ani z klawiatury)
  assert.match(znak('imgw-hydro'), /^Stan źródła: ✕ błąd pobierania ?\. Brak w naszych danych: źródło Ostrzeżenia hydrologiczne IMGW, od godz\. \d\d:\d\d\.$/);
  assert.match(znak('cert-polska'), /^Stan źródła: ‖ wstrzymane ?\. Brak w naszych danych: źródło Ostrzeżenia CERT Polska, od 17 listopada, godz\. \d\d:\d\d\.$/);
  assert.match(h(ZnakProblemuZrodla, { zrodla: dane(), slug: 'imgw-hydro' }), /class="tz-sr">\. Brak w naszych danych/);
  assert.equal(tekst(h(ZnakProblemuZrodla, { zrodla: undefined, slug: 'imgw-hydro' })), '');
  assert.equal(tekst(h(ZnakProblemuZrodla, { zrodla: daneAwaria(), slug: 'imgw-hydro' })), '');
});

// ---------- panel źródeł i legenda ----------

test('PanelZrodel: lista ze stanem zdrowia, licznik, a awaria jest komunikatem, nie pustą listą', () => {
  const { PanelZrodel } = load(`${dir}/PanelZrodel`);
  const lista = load(`${dir}/dane-probne/zrodla`).probneZrodla();
  const ok = tekst(h(PanelZrodel, { dane: dane(), teraz: Date.now() }));
  assert.match(ok, new RegExp(`Źródła i ich stan działa ${lista.length - 2} z ${lista.length}, 2 z problemem`));
  for (const s of lista) assert.ok(ok.includes(s.nazwa), s.nazwa);
  assert.match(ok, /Łącze: scraping/);
  assert.match(ok, /Łącze: WebSocket/);
  assert.match(ok, /✕ błąd pobierania/);
  assert.match(ok, /‖ wstrzymane/);
  assert.match(ok, /Stan źródeł z godz\. \d\d:\d\d\. Odświeżamy go co minutę\./);
  assert.equal((h(PanelZrodel, { dane: dane() }).match(/<li class="tz-zrodlo"/g) ?? []).length, lista.length);

  const po_awarii = tekst(h(PanelZrodel, { dane: daneAwaria() }));
  assert.match(po_awarii, /Nie udało się pobrać stanu źródeł, więc nie wiemy, które działają, a które mają lukę/);
  assert.match(po_awarii, /stan niedostępny/);
  assert.ok(!/brak danych/i.test(po_awarii) && !/Serwer nie podał żadnych źródeł/.test(po_awarii), 'awaria to nie pusta lista');
  // jeden komunikat dla czytnika: panel nie ma własnego role=status (to samo zdanie ogłasza KomunikatyDanych)
  assert.ok(!/role="status"/.test(h(PanelZrodel, { dane: daneAwaria() })));
  assert.match(h(PanelZrodel, { dane: dane() }), /<span class="tz-zrodla__tytul"[^>]*>Źródła i ich stan<\/span> <span class="tz-zrodla__licznik"/, 'spacja między tytułem a licznikiem w nazwie summary');

  assert.match(tekst(h(PanelZrodel, { dane: daneLaduje() })), /Wczytujemy stan źródeł…/);
  const nieaktualne = tekst(h(PanelZrodel, { dane: dane(undefined, { nieaktualne: true }) }));
  assert.match(nieaktualne, /Nie udało się odświeżyć stanu źródeł\. Pokazujemy ostatnio pobrany/);
  assert.ok(nieaktualne.includes(lista[0].nazwa), 'nieaktualny stan nadal pokazuje źródła');
  assert.match(tekst(h(PanelZrodel, { dane: dane([]) })), /Serwer nie podał żadnych źródeł, więc nie wiemy, skąd pochodzą komunikaty/);
  assert.match(tekst(h(PanelZrodel, { dane: dane(undefined, { pominiete: 2 }) })), /Pominięto źródła o nieznanym formacie: 2/);
});

test('LegendaSkadIJak: 8 rodzajów łącza, 4 stany i zdanie o braku w naszych danych', () => {
  const { LegendaSkadIJak } = load(`${dir}/PanelZrodel`);
  const html = h(LegendaSkadIJak, {});
  const t = tekst(html);
  assert.match(t, /^Skąd i jak/);
  for (const e of ['X', 'API', 'MCI', 'RSS', 'scraping', 'WebSocket', 'plik', 'ręcznie']) assert.ok(t.includes(`Łącze: ${e}`), e);
  assert.equal((html.match(/class="tz-lacze"/g) ?? []).length, 8);
  for (const s of ['● działa', '◐ luka w danych', '✕ błąd pobierania', '‖ wstrzymane']) assert.ok(t.includes(s), s);
  assert.match(t, /„Brak w naszych danych: źródło X, od…” znaczy, że od tej chwili nie mamy od źródła danych/);
  assert.match(t, /Nie mówi nic o ważności komunikatu/);
});

// ---------- panel warstw ----------

test('PanelWarstw: etykiety łącza i stan przy warstwach, panel źródeł i legenda „Skąd i jak”', () => {
  const { PanelWarstw } = load(`${dir}/PanelWarstw`);
  const warstwy = d().probneWarstwy(Date.now());
  const props = {
    warstwy, wiersze: new Map(), wlaczone: new Set(['rcb']), naMapie: {}, okres: '24h', woj: null, ladowanie: false,
    onPrzelacz() {}, onWszystkie() {}, onOkres() {}, onWoj() {}, onZamknij() {},
  };
  const z_danymi = h(PanelWarstw, { ...props, zrodla: dane() });
  const t = tekst(z_danymi);
  assert.match(t, /Źródła i ich stan/);
  assert.match(t, /Skąd i jak/);
  // przy warstwie z błędem (IMGW hydro) jest zdanie o braku
  assert.match(t, /Brak w naszych danych: źródło Ostrzeżenia hydrologiczne IMGW, od /);
  // przy każdej warstwie ze źródłem jest etykieta łącza: działających warstw ze źródłem jest 7 (rcb, meteo, hydro, powietrze, pożary, wstrząsy, cyber)
  assert.equal((z_danymi.match(/class="tz-warstwa__lacza"/g) ?? []).length, 7);
  // po awarii nie zgadujemy: brak etykiet przy warstwach, ale komunikat w panelu źródeł
  const po_awarii = h(PanelWarstw, { ...props, zrodla: daneAwaria() });
  assert.equal((po_awarii.match(/class="tz-warstwa__lacza"/g) ?? []).length, 0);
  assert.match(tekst(po_awarii), /Nie udało się pobrać stanu źródeł/);
  // bez danych o źródłach (prop pominięty) legenda i tak tłumaczy etykiety, panel źródeł się nie pojawia
  const bez = tekst(h(PanelWarstw, props));
  assert.match(bez, /Skąd i jak/);
  assert.ok(!/Źródła i ich stan/.test(bez));
});

// ---------- karta i lista ----------

const widokWpisu = (id = 9004) => ({ wpis: d().probneWpisy(Date.now()).find(w => w.id === id), status: 'brak', zdarzenie: null });

test('KartaWpisu: wiersz „Łącze i stan źródła” z opisem po polsku; bez danych o źródłach wiersza nie ma', () => {
  const { KartaWpisu } = load(`${dir}/KartaWpisu`);
  const baza = { widok: widokWpisu(9004), warstwy: undefined, adres: () => 'x', onZamknij() {} };
  const t = tekst(h(KartaWpisu, { ...baza, zrodla: dane() }));
  assert.match(t, /Łącze i stan źródła Łącze: API Interfejs programistyczny instytucji/);
  assert.match(t, /● działa Ostatnie udane pobranie/);
  const hydro = tekst(h(KartaWpisu, { ...baza, widok: { wpis: { ...widokWpisu(9004).wpis, zrodlo: 'imgw-hydro' }, status: 'brak', zdarzenie: null }, zrodla: dane() }));
  assert.match(hydro, /✕ błąd pobierania/);
  assert.match(hydro, /Brak w naszych danych: źródło Ostrzeżenia hydrologiczne IMGW, od /);
  const po_awarii = tekst(h(KartaWpisu, { ...baza, zrodla: daneAwaria() }));
  assert.match(po_awarii, /Łącze: nieznane/);
  assert.match(po_awarii, /stan źródła nieznany Nie udało się pobrać stanu źródeł/);
  assert.match(tekst(h(KartaWpisu, { ...baza, zrodla: daneLaduje() })), /Wczytujemy stan źródła…/);
  assert.ok(!/Łącze i stan źródła/.test(tekst(h(KartaWpisu, baza))), 'bez prop `zrodla` karta wygląda jak dotąd');
});

test('ListaWpisow: etykieta łącza przy każdym komunikacie, znak problemu tylko przy źródłach z problemem', () => {
  const { ListaWpisow } = load(`${dir}/ListaWpisow`);
  const wpisy = d().probneWpisy(Date.now());
  const widoki = [wpisy.find(w => w.zrodlo === 'rcb-gov-pl'), wpisy.find(w => w.zrodlo === 'emsc'), { ...wpisy[0], id: 1, zrodlo: 'imgw-hydro' }]
    .map(wpis => ({ wpis, status: 'brak', zdarzenie: null }));
  const props = { widoki, warstwy: undefined, wybrany: null, onWybierz() {}, etykieta: 'Lista', pusta: 'Brak.' };
  const html = h(ListaWpisow, { ...props, zrodla: dane() });
  assert.equal((html.match(/class="tz-lacze"/g) ?? []).length, 3);
  assert.deepEqual([...html.matchAll(/Łącze: <\/span>([^<]+)</g)].map(m => m[1]), ['scraping', 'WebSocket', 'API']);
  assert.equal((html.match(/tz-zdrowie--znak/g) ?? []).length, 1, 'znak problemu tylko przy imgw-hydro');
  assert.match(tekst(html), /✕ błąd pobierania/);
  assert.equal((h(ListaWpisow, props).match(/tz-lacze/g) ?? []).length, 0, 'bez prop `zrodla` bez etykiet');
  assert.equal((h(ListaWpisow, { ...props, zrodla: daneLaduje() }).match(/tz-lacze/g) ?? []).length, 0, 'w trakcie pobierania bez etykiet (bez migania „nieznane”)');
  assert.equal((h(ListaWpisow, { ...props, zrodla: daneAwaria() }).match(/data-lacze="nieznane"/g) ?? []).length, 3, 'po awarii „nieznane”');
});

test('KomunikatyDanych: awaria stanu źródeł to osobny komunikat, stan znany i świeży nie dodaje nic', () => {
  const { KomunikatyDanych } = load(`${dir}/KomunikatyDanych`);
  const spokoj = { niedostepne: false };
  const base = { wpisy: undefined, warstwy: spokoj, zdarzenia: spokoj };
  const awariaT = tekst(h(KomunikatyDanych, { ...base, zrodla: daneAwaria() }));
  assert.match(awariaT, /Stan źródeł niedostępny\. Nie udało się pobrać stanu źródeł/);
  assert.match(h(KomunikatyDanych, { ...base, zrodla: daneAwaria() }), /tz-komunikat--blad" role="status"/);
  assert.match(tekst(h(KomunikatyDanych, { ...base, zrodla: dane(undefined, { nieaktualne: true }) })), /Stan źródeł nieaktualny\./);
  assert.match(tekst(h(KomunikatyDanych, { ...base, zrodla: dane(undefined, { pominiete: 1 }) })), /Stan części źródeł nieznany\./);
  assert.equal(tekst(h(KomunikatyDanych, { ...base, zrodla: dane() })), '');
  assert.equal(tekst(h(KomunikatyDanych, { ...base, zrodla: daneLaduje() })), '', 'ładowanie nie jest awarią');
  assert.equal(tekst(h(KomunikatyDanych, base)), '');
});

// ---------- cała strona ----------

/** Fragment strony bez statycznej legendy „Skąd i jak” (legenda zawsze opisuje wszystkie etykiety i stany). */
const bezLegendy = html => html.replace(/<section class="tz-skad"[\s\S]*?<\/section>/, '');
/** Lista komunikatów (ol.tz-lista) z całej strony. */
const lista = html => /<ol class="tz-lista"[\s\S]*?<\/ol>/.exec(html)?.[0] ?? '';

function ustawDane(zrodla) {
  const teraz = Date.now();
  zapytania.stan = udane(d().probneStan(teraz));
  zapytania.warstwy = udane(d().probneWarstwy(teraz));
  zapytania.zdarzenia = udane({ wyniki: d().probneZdarzenia(teraz), uciete: false, pominiete: 0 });
  zapytania.wpisy = udane({ wpisy: d().probneWpisy(teraz), uciete: false, pominiete: 0 });
  zapytania['wpisy-powiatow'] = udane({ wpisy: d().probneWpisy(teraz), uciete: false, pominiete: 0 });
  zapytania.zrodla = zrodla;
}
function strona(poczatkowy = {}) {
  const { TerazPage } = load(`${dir}/TerazPage`);
  const p = { warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'lista', probne: false, ...poczatkowy };
  return renderToStaticMarkup(React.createElement(TerazPage, { poczatkowy: p, poczatkowePowiaty: [], podkladUrl: '', glifyUrl: '' }));
}

test('TerazPage: lista, karta i panel dostają stan źródeł; zapytanie ma własny klucz i odświeża się co minutę', () => {
  const zrodlaProbne = load(`${dir}/dane-probne/zrodla`).probneZrodla();
  ustawDane(udane({ zrodla: zrodlaProbne, pominiete: 0 }));
  const naLiscie = strona({ widok: 'lista' });
  assert.ok((lista(naLiscie).match(/class="tz-lacze"/g) ?? []).length > 3, 'etykiety przy komunikatach na liście');
  assert.match(lista(naLiscie), /tz-zdrowie--znak/, 'znak problemu przy komunikacie ze źródła z błędem albo luką');
  assert.deepEqual(opcje.zrodla.queryKey, ['teraz', 'zrodla', false]);
  assert.equal(opcje.zrodla.refetchInterval, 60_000);
  assert.equal(opcje.zrodla.refetchOnWindowFocus, true);

  const naMapie = strona({ widok: 'mapa', wpis: 9004 });
  assert.match(naMapie, /Źródła i ich stan/);
  assert.match(tekst(naMapie), /Łącze i stan źródła Łącze: API/);
  assert.match(tekst(naMapie), /Skąd i jak/);
  assert.match(tekst(naMapie), /Brak w naszych danych: źródło Ostrzeżenia hydrologiczne IMGW, od /);
});

test('TerazPage: awaria /zrodla/ to komunikat w każdym widoku z listą, mapą i „Mój powiat”, nigdy „działa” ani „brak danych”', () => {
  ustawDane(awaria());
  for (const widok of ['lista', 'mapa', 'powiat']) {
    const t = tekst(strona({ widok }));
    assert.match(t, /Stan źródeł niedostępny\./, widok);
    assert.ok(!/● działa/.test(tekst(bezLegendy(strona({ widok })))), `${widok}: nie twierdzimy, że źródła działają`);
  }
  const mapa = tekst(strona({ widok: 'mapa' }));
  assert.match(mapa, /Nie udało się pobrać stanu źródeł, więc nie wiemy, które działają, a które mają lukę/);
  // błąd stanu źródeł nie psuje reszty: komunikaty nadal są na liście
  assert.match(lista(strona({ widok: 'lista' })), /tz-pozycja/);
  assert.equal((lista(strona({ widok: 'lista' })).match(/data-lacze="nieznane"/g) ?? []).length, (lista(strona({ widok: 'lista' })).match(/<li>/g) ?? []).length, 'po awarii każdy komunikat ma etykietę „nieznane”');
});

test('TerazPage: źródła w stanie ładowania nie pokazują ani awarii, ani etykiet', () => {
  ustawDane({ isSuccess: false, isPending: true, isError: false, data: undefined, dataUpdatedAt: 0 });
  const t = strona({ widok: 'lista' });
  assert.ok(!/Stan źródeł niedostępny/.test(tekst(t)));
  assert.equal((lista(t).match(/class="tz-lacze"/g) ?? []).length, 0);
  assert.match(strona({ widok: 'mapa' }), /Wczytujemy stan źródeł…/);
});

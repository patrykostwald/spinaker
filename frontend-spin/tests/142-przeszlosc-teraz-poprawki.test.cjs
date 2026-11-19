// „Teraz” (Z6-poprawki): poprawki po recenzji Codexa (#33). Sprawdza: pole `wylaczona`, osobne stany awarii, obcięcia i braku
// komunikatów, walidację odpowiedzi API, przecięcie zasięgów przy filtrze regionu, walidację pamięci i adresu, bezpieczne odnośniki,
// stałe ostrzeżenie nad treścią, zapytania i zgodność lockfile z Node 20. node --test, bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const mocks = { '@tanstack/react-query': { useQuery: () => ({}), keepPreviousData: {} } };
const cache = new Map();
const stub = { fetch: () => { throw new Error('fetch nie jest podstawiony'); } };
function load(file) {
  if (file.endsWith('.json')) return JSON.parse(read(file));
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
  const req = name => {
    if (name in mocks) return mocks[name];
    if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(abs), name)).split(path.sep).join('/'));
    return require(name);
  };
  new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} }, (...args) => stub.fetch(...args));
  return module.exports;
}

const tekstZHtml = html => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
const m = () => load(`${dir}/model`);
const d = () => load(`${dir}/dane-probne/index`);
const w = () => load(`${dir}/walidacja`);

const wpisApi = (id, nadpisz = {}) => ({
  id, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', tytul: `Wpis ${id}`, tresc: '', link: 'https://www.gov.pl/web/rcb',
  opublikowano_at: '2026-11-18T10:00:00Z', pobrano_at: '2026-11-18T10:02:00Z', klasa: 'zwykly', teryt: ['1813'],
  szerokosc: null, dlugosc: null, bbox: null, dokladnosc: 'powiat', pewnosc_lokalizacji: 0, ...nadpisz,
});
const odpowiedz = dane => ({ ok: true, status: 200, json: async () => dane });

// ---------- P1-1: wylaczona ----------

test('wylaczona: wyłączona warstwa znika z wpisów, zdarzeń (karta, powiązania), stanu i wyboru, niezależnie od preferencji i cache', () => {
  const mod = m();
  const dane = d();
  const teraz = Date.now();
  const warstwy = dane.probneWarstwy(teraz).map(x => (x.warstwa === 'pozary' ? { ...x, wylaczona: true, zrodla: [] } : x));
  const wylaczone = mod.kodyWylaczonych(warstwy);
  assert.deepEqual([...wylaczone].sort(), ['media', 'pozary']);
  const wpisy = dane.probneWpisy(teraz);
  const zdarzenia = dane.probneZdarzenia(teraz);
  const wynik = mod.bezWylaczonych(wpisy, zdarzenia, wylaczone);
  assert.ok(wynik.wpisy.length < wpisy.length && wynik.wpisy.every(x => x.warstwa !== 'pozary'), 'wpisy pożarów (z cache klienta) zniknęły');
  assert.ok(!wynik.zdarzenia.some(z => z.status === 'zgloszone'), 'zdarzenia składające się tylko z wpisów wyłączonej warstwy zniknęły');
  assert.ok(wynik.zdarzenia.every(z => z.wpisy.every(x => x.warstwa !== 'pozary')), 'powiązane wpisy bez wyłączonej warstwy');
  // zdarzenie mieszane: zostaje, ale bez wpisów wyłączonej warstwy
  const mieszane = { ...zdarzenia[0], wpisy: [wpisy.find(x => x.warstwa === 'rcb'), wpisy.find(x => x.warstwa === 'pozary')] };
  const po = mod.bezWylaczonych([], [mieszane], wylaczone).zdarzenia;
  assert.equal(po.length, 1); assert.deepEqual(po[0].wpisy.map(x => x.warstwa), ['rcb']);
  assert.strictEqual(mod.bezWylaczonych(wpisy, zdarzenia, new Set()).wpisy, wpisy, 'bez wyłączeń nic nie kopiujemy');
  // zapisany wybór użytkownika nie przywraca wyłączonej warstwy
  assert.deepEqual([...mod.wlaczoneWarstwy(['rcb', 'pozary', 'media', 'nieznana'], warstwy)], ['rcb']);
  assert.ok(!mod.wlaczoneWarstwy(null, warstwy).has('pozary'));
  assert.equal(mod.aktywna(warstwy.find(x => x.warstwa === 'pozary')), false);
  assert.equal(mod.dostepna(warstwy.find(x => x.warstwa === 'pozary')), false);
  // linia stanu i ostrzeżenia też nie pokazują wyłączonej warstwy
  const p = mod.podsumujStan(dane.probneStan(teraz), warstwy);
  assert.ok(!p.wiersze.some(x => wylaczone.has(x.warstwa)) && !p.ostrzezenia.some(x => wylaczone.has(x.warstwa)));
  // bez listy warstw nie mamy z czym porównać: wybór zostaje, nic nie jest ukrywane po cichu
  assert.deepEqual([...mod.wlaczoneWarstwy(['rcb', 'pozary'], [])], ['rcb', 'pozary']);
});

test('wylaczona: strona stosuje wyłączenie do wszystkich widoków (mapa, lista, tabela, „Mój powiat”, karta, powiązania)', () => {
  const strona = read(`${dir}/TerazPage.tsx`);
  // od recenzji PR #38 (P2-7): tylko warstwy potwierdzone w bieżącej odpowiedzi warstwy/ (wyłączone nigdy nie są potwierdzone)
  assert.match(strona, /tylkoPotwierdzone\(wpisyQ\.data\?\.wpisy \?\? \[\], \[\], potwierdzone, wylaczone\)/, 'wpisy mapy, listy i tabeli');
  assert.match(strona, /tylkoPotwierdzone\(powiatyQ\.data\?\.wpisy \?\? \[\], \[\], potwierdzone, wylaczone\)/, 'wpisy „Mój powiat”');
  assert.match(strona, /tylkoPotwierdzone\(\[\], zdarzeniaQ\.data\?\.wyniki \?\? \[\], potwierdzone, wylaczone\)/, 'zdarzenia: karta i powiązania');
  assert.match(strona, /potwierdzoneWarstwy\(warstwyQ\.data, warstwyQ\.isSuccess\)/);
  assert.match(strona, /zbudujWidoki\(wpisyMapy, zdarzenia, polityka\)/); assert.match(strona, /zbudujWidoki\(wpisyPowiatow, zdarzenia, polityka\)/);
  assert.match(strona, /\(warstwyQ\.data \?\? \[\]\)\.filter\(dostepna\)/, 'panel: bez wyłączonych, także bez „w przygotowaniu”');
  assert.match(strona, /widoczne\.find\(v => v\.wpis\.id === wybranyId\)/, 'karta liczona z widocznych danych (bez wyłączonych i spoza filtrów)');
  assert.match(strona, /warstwy=\{warstwyDlaNazw\}/, 'nazwy źródeł z warstw bez wyłączonych');
  assert.ok(!/bezFiltraWarstw/.test(strona), 'bez listy warstw nie odsłaniamy wpisów z cache (P2-7)');
});

// ---------- P1-2: awaria / obcięcie / brak, walidacja ----------

test('statusy: bez zdarzeń „status niedostępny”, nie „Komunikat bez zdarzenia”; przy obcięciu nierozstrzygnięte powiązania też', () => {
  const mod = m();
  const wpisy = [wpisApi(1, { opublikowano_at: '2026-11-18T10:00:00Z' }), wpisApi(2, { opublikowano_at: '2026-11-18T08:00:00Z' }), wpisApi(3, { opublikowano_at: '2026-11-18T06:00:00Z' })];
  const zd = { id: 7, status: 'odwolane', tytul_roboczy: 'x', pierwszy_wpis_at: '2026-11-18T09:00:00Z', ostatni_wpis_at: '2026-11-18T09:00:00Z', przygotowane_automatycznie: true, zweryfikowal: null, zweryfikowano_at: null, wpisy: [wpisy[1]] };
  const status = (polityka, zdarzenia = [zd]) => Object.fromEntries(mod.zbudujWidoki(wpisy, zdarzenia, polityka).map(v => [v.wpis.id, v.status]));
  // pełne zdarzenia: wpis bez zdarzenia to „brak”
  assert.deepEqual(status(mod.politykaStatusu({ wyniki: [zd], uciete: false, pominiete: 0 })), { 1: 'brak', 2: 'odwolane', 3: 'brak' });
  // awaria albo wczytywanie zdarzeń (undefined): nieznany status wszystkich wpisów bez zdarzenia
  assert.deepEqual(status(mod.politykaStatusu(undefined), []), { 1: 'niedostepny', 2: 'niedostepny', 3: 'niedostepny' });
  // rekordy o złym formacie: też nie wiemy
  assert.equal(mod.politykaStatusu({ wyniki: [zd], uciete: false, pominiete: 2 }).wszystkie, true);
  // limit stron (P2-9): bez porównywania dwóch zegarów (oś czasu źródła w backendzie, czas publikacji wpisu) każdy wpis bez
  // pobranego zdarzenia ma „Status niedostępny”, także nowszy niż najstarsze pobrane zdarzenie
  const ucieta = mod.politykaStatusu({ wyniki: [zd], uciete: true, pominiete: 0 });
  assert.equal(ucieta.wszystkie, true);
  assert.equal(ucieta.nieWiekszeNiz, undefined);
  assert.deepEqual(status(ucieta), { 1: 'niedostepny', 2: 'odwolane', 3: 'niedostepny' });
  assert.equal(mod.politykaStatusu({ wyniki: [], uciete: true, pominiete: 0 }).wszystkie, true, 'ucięte bez żadnego zdarzenia: wszystko nieznane');
  // domyślnie (bez polityki) zachowanie jak dotąd
  assert.deepEqual(Object.fromEntries(mod.zbudujWidoki(wpisy, []).map(v => [v.wpis.id, v.status])), { 1: 'brak', 2: 'brak', 3: 'brak' });
  const wr = load(`${dir}/warstwy`);
  assert.equal(wr.metaStatusu('niedostepny').etykieta, 'Status niedostępny');
  assert.notEqual(wr.STATUSY.niedostepny.ksztalt, wr.STATUSY.brak.ksztalt, 'osobny kształt, nie tylko napis');
});

test('walidacja odpowiedzi: zła struktura to błąd, zły rekord jest pomijany i liczony, poprawne dane przechodzą', () => {
  const v = w();
  assert.equal(v.walidujWpis(wpisApi(1)).id, 1);
  for (const zly of [null, 'x', [], { id: 1 }, wpisApi(1, { tytul: 5 }), wpisApi(1, { opublikowano_at: 'nie data' }), wpisApi(1, { teryt: 'nie lista' }), wpisApi(1, { id: 'a' })]) assert.equal(v.walidujWpis(zly), null);
  const luzny = v.walidujWpis({ id: 5, warstwa: 'rcb', tytul: 'T', opublikowano_at: '2026-11-18T10:00:00Z', bbox: [1, 2, 3], szerokosc: 'x' });
  assert.deepEqual({ ...luzny, bbox: luzny.bbox }, { ...luzny }); assert.equal(luzny.bbox, null); assert.equal(luzny.szerokosc, null); assert.deepEqual([...luzny.teryt], []);
  assert.throws(() => v.walidujWarstwy({}), /nieznanym formacie/);
  assert.throws(() => v.walidujWarstwy([{ warstwa: 'rcb', nazwa: 'Alert RCB' }]), /nieznanym formacie/, 'bez pola wylaczona nie zgadujemy, że warstwa działa');
  const dobra = { warstwa: 'rcb', nazwa: 'Alert RCB', wylaczona: false, zrodla: [], ostatnie_pobranie_at: null, ostatni_sukces_at: null, liczba_wpisow_24h: 0, luka: false, blad: false };
  assert.equal(v.walidujWarstwy([dobra, { warstwa: 1 }]).length, 1);
  assert.deepEqual([], v.walidujWarstwy([]));
  assert.throws(() => v.walidujStan({ informacja: 'x' }), /nieznanym formacie/);
  assert.equal(v.walidujStan({ informacja: 'To nie jest strona urzędowa', warstwy: [{ warstwa: 'rcb', ostatnie_pobranie: 'a', komunikaty: 'b', komunikat: '' }, 5] }).warstwy.length, 1);
  assert.throws(() => v.walidujStrone({ results: 'x' }, v.walidujWpis), /nieznanym formacie/);
  assert.throws(() => v.walidujStrone(null, v.walidujWpis), /nieznanym formacie/);
  const strona = v.walidujStrone({ count: 2, next: 'http://x/?page=2', previous: null, results: [wpisApi(1), { smiec: true }] }, v.walidujWpis);
  assert.equal(strona.wyniki.length, 1); assert.equal(strona.pominiete, 1); assert.equal(strona.nastepna, true);
  assert.equal(v.walidujZdarzenie({ id: 1, status: 'nieznany', wpisy: [] }), null);
  const zd = v.walidujZdarzenie({ id: 1, status: 'odwolane', tytul_roboczy: 't', pierwszy_wpis_at: '2026-11-18T10:00:00Z', ostatni_wpis_at: '2026-11-18T10:00:00Z', wpisy: [wpisApi(1), 'smiec'] });
  assert.equal(zd.wpisy.length, 1); assert.equal(zd.przygotowane_automatycznie, true, 'brak pola liczymy jako przygotowane automatycznie');
  assert.equal(zd.odrzucone_wpisy, 1, 'odrzucone powiązanie jest liczone (P2-8)');
});

test('P2-8: brak `next` to błąd struktury; odrzucone wiersze stanu i powiązania są liczone i przekazane do widoku', async () => {
  const v = w();
  assert.throws(() => v.walidujStrone({ count: 1, previous: null, results: [wpisApi(1)] }, v.walidujWpis), /nieznanym formacie/, 'brak next nie kończy listy po cichu');
  assert.throws(() => v.walidujStrone({ count: 1, next: 5, previous: null, results: [] }, v.walidujWpis), /nieznanym formacie/);
  assert.equal(v.walidujStrone({ count: 0, next: null, previous: null, results: [] }, v.walidujWpis).nastepna, false, 'jawny null to koniec');
  const a = load(`${dir}/api`);
  stub.fetch = async () => odpowiedz({ count: 1, previous: null, results: [wpisApi(1)] });
  await assert.rejects(a.pobierzWpisy('24h', null), err => err.name === 'BladApi', 'uszkodzona strona to „dane niedostępne”, nie kompletna lista');
  // stan/: odrzucone wiersze → niepewność zamiast „brak aktywnych źródeł”
  const stan = v.walidujStan({ informacja: 'To nie jest strona urzędowa', warstwy: [{ warstwa: 'rcb' }, 5] });
  assert.equal(stan.pominiete, 2);
  const mod = m();
  const podsumowanie = mod.podsumujStan(stan, d().probneWarstwy());
  assert.equal(podsumowanie.niepelne, true);
  const { LiniaStanu } = load(`${dir}/LiniaStanu`);
  const tekst = tekstZHtml(renderToStaticMarkup(React.createElement(LiniaStanu, { probne: false, podsumowanie, online: true, blad: false, odswiezonoWpisy: null, odswiezonoStan: null, ladowanie: false })));
  assert.ok(!/brak aktywnych źródeł/.test(tekst), tekst);
  assert.match(tekst, /stan źródeł niepełny/);
  assert.match(tekst, /Stan części źródeł ma nieznany format/);
  // zdarzenia: odrzucony wpis wewnątrz zdarzenia trafia do `pominiete`, więc wpisy bez zdarzenia mają „Status niedostępny”
  const zdarzenie = { id: 7, status: 'odwolane', tytul_roboczy: 'x', pierwszy_wpis_at: '2026-11-18T09:00:00Z', ostatni_wpis_at: '2026-11-18T09:00:00Z', przygotowane_automatycznie: true, zweryfikowal: null, zweryfikowano_at: null, wpisy: [wpisApi(1), { zly: true }] };
  stub.fetch = async () => odpowiedz({ count: 1, next: null, previous: null, results: [zdarzenie] });
  const zdarzenia = await a.pobierzZdarzenia();
  assert.equal(zdarzenia.pominiete, 1);
  assert.equal(zdarzenia.uciete, false);
  assert.equal(mod.zbudujWidoki([v.walidujWpis(wpisApi(2))], zdarzenia.wyniki, mod.politykaStatusu(zdarzenia))[0].status, 'niedostepny', 'nie „Komunikat bez zdarzenia”');
});

test('API: błędny JSON o złej strukturze daje BladApi (stan niedostępności), nie pustą listę; obcięcie i pominięcia są zachowane', async () => {
  const a = load(`${dir}/api`);
  stub.fetch = async () => odpowiedz({ count: 1, next: null, previous: null, results: 'nie lista' });
  await assert.rejects(a.pobierzWpisy('24h', null), err => err.name === 'BladApi' && /formacie/.test(err.message));
  stub.fetch = async () => odpowiedz(['to nie jest strona']);
  await assert.rejects(a.pobierzWpisy('24h', null), err => err.name === 'BladApi');
  stub.fetch = async () => odpowiedz({ informacja: 5 });
  await assert.rejects(a.pobierz('stan', {}, undefined, w().walidujStan), err => err.name === 'BladApi' && /formacie/.test(err.message));
  stub.fetch = async () => odpowiedz([{ warstwa: 'rcb' }]);
  await assert.rejects(a.pobierz('warstwy', {}, undefined, w().walidujWarstwy), err => err.name === 'BladApi');
  // pominięte rekordy są liczone, a ucięcie zachowane
  stub.fetch = async () => odpowiedz({ count: 999, next: 'x', previous: null, results: [wpisApi(1), { zly: true }] });
  const wynik = await a.pobierzWpisy('24h', null);
  assert.equal(wynik.uciete, true); assert.equal(wynik.pominiete, 6, 'jeden zły rekord na stronę, sześć stron'); assert.equal(wynik.wpisy.length, 6, 'poprawny rekord z każdej strony');
});

test('KomunikatyDanych: awaria, obcięcie, nieaktualne dane i brak komunikatów to osobne stany; przy awarii nigdy „brak komunikatów”', () => {
  const { KomunikatyDanych } = load(`${dir}/KomunikatyDanych`);
  const draw = props => tekstZHtml(renderToStaticMarkup(React.createElement(KomunikatyDanych, { warstwy: { niedostepne: false }, zdarzenia: { niedostepne: false }, ...props })));
  const awaria = draw({ wpisy: { niedostepne: true } });
  assert.match(awaria, /Dane niedostępne\. Nie udało się pobrać komunikatów, więc nie wiemy, co się dzieje: nie mamy pewności, sprawdź Alert RCB i 112\./);
  assert.ok(!/Brak komunikatów/.test(awaria));
  assert.match(draw({ wpisy: { niedostepne: false, uciete: true } }), /Dane obcięte: pobraliśmy najnowsze komunikaty, starsze pominięto/);
  assert.match(draw({ wpisy: { niedostepne: false, uciete: true, pobrane: 300 } }), /Dane obcięte: pobraliśmy 300 komunikatów, najnowsze, starsze pominięto/, 'liczba pobranych (P1-3)');
  assert.match(draw({ warstwy: { niedostepne: false, niepotwierdzone: 4 } }), /ukrywamy komunikaty z warstw bez potwierdzenia \(4\)/, 'P2-7');
  assert.match(draw({ wpisy: { niedostepne: false, nieaktualne: true } }), /Pokazujemy ostatnio pobrane, mogą być nieaktualne/);
  assert.match(draw({ wpisy: { niedostepne: false, pominiete: 3 } }), /Pominięto komunikaty o nieznanym formacie: 3/);
  assert.match(draw({ zdarzenia: { niedostepne: true } }), /Statusy niedostępne\. Nie wiemy, które komunikaty są potwierdzone, a które odwołane/);
  assert.match(draw({ zdarzenia: { niedostepne: false, uciete: true } }), /Statusy sprawdziliśmy tylko dla najnowszych zdarzeń/);
  assert.match(draw({ warstwy: { niedostepne: true } }), /Lista warstw niedostępna/);
  assert.equal(draw({ wpisy: { niedostepne: false } }).trim(), '', 'sprawne dane: żadnego komunikatu');
  assert.match(draw({ brakWybranego: true }), /warstwa wyłączona/);
  const html = renderToStaticMarkup(React.createElement(KomunikatyDanych, { wpisy: { niedostepne: true }, warstwy: { niedostepne: false }, zdarzenia: { niedostepne: true } }));
  assert.match(html, /role="alert"/);
  const strona = read(`${dir}/TerazPage.tsx`);
  assert.match(strona, /udanaOdpowiedz = wpisyQ\.isSuccess && !wpisyQ\.isPlaceholderData/, 'odpowiedź dla bieżącego filtra');
  // P1-3: „brak komunikatów” tylko przy kompletnej odpowiedzi (wszystkie strony, nic odrzuconego, warstwy potwierdzone)
  assert.match(strona, /kompletneWpisy = udanaOdpowiedz && !!wpisyQ\.data && !wpisyQ\.data\.uciete && wpisyQ\.data\.pominiete === 0 && mapaPotw\.ukryte === 0 && warstwyQ\.isSuccess/);
  assert.match(strona, /kompletneWpisy && widoczne\.length === 0/);
  assert.match(strona, /udanaOdpowiedz && !kompletneWpisy && !warstwyQ\.isPending && widoczne\.length === 0 && <p className="tz-komunikat" role="status">\{tekstNiepelnych\}/);
  assert.match(strona, /Dane niepełne: pobraliśmy \$\{liczbaKomunikatow\(pobraneWpisy\)\}/, 'liczba pobranych także przy zerze');
  assert.match(strona, /wpisyNiedostepne\s*\?\s*`Dane niedostępne/, 'lista i tabela przy awarii mówią o niedostępności');
});

test('karta: odnośnik źródłowy tylko bezwzględny http(s); powiązane komunikaty z danych bez wyłączonych', () => {
  const { KartaWpisu } = load(`${dir}/KartaWpisu`);
  const mod = m();
  const wpis = wpisApi(1, { link: 'javascript:alert(1)' });
  const render = link => renderToStaticMarkup(React.createElement(KartaWpisu, {
    widok: { wpis: { ...wpis, link }, status: 'brak', zdarzenie: null }, warstwy: undefined, adres: () => 'x', onZamknij() {},
  }));
  for (const zly of ['javascript:alert(1)', 'data:text/html,x', '/wzgledny', '//obcy.pl/x', 'ftp://x.pl/', '', 'gov.pl/web']) {
    const html = render(zly);
    assert.ok(!/<a [^>]*href=/.test(html), `bez odnośnika dla: ${zly}`);
    assert.match(tekstZHtml(html), /Źródło nie podało poprawnego odnośnika do oryginału/);
  }
  const dobry = render('https://www.gov.pl/web/rcb');
  assert.match(dobry, /<a [^>]*href="https:\/\/www\.gov\.pl\/web\/rcb"[^>]*rel="noopener noreferrer"/);
  void mod;
});

// ---------- P2-2: region ----------

test('filtr regionu: przecięcie zasięgów zamiast środka, przybliżenie opisane w panelu', () => {
  const mod = m();
  const wpisBox = (bbox, teryt = []) => wpisApi(1, { bbox, teryt, szerokosc: null, dlugosc: null, dokladnosc: 'wojewodztwo' });
  // zasięg zaczyna się w lubuskim (15,0 do 16,5), a środek (17) leży poza nim, ale część wchodzi w dolnośląskie (14,82 do 17,78)
  const zakres = wpisBox([16.0, 51.0, 18.0, 51.5]);
  assert.equal(mod.zgodnyZRegionem(zakres, '02'), true);
  assert.equal(mod.zgodnyZRegionem(zakres, '16'), true, 'sięga opolskiego (16,9 do 18,7), choć środek (17) jest w dolnośląskim: zasięg obejmujący część regionu nie znika');
  assert.equal(mod.zgodnyZRegionem(zakres, '32'), false, 'zachodniopomorskie nie ma części wspólnej');
  assert.equal(mod.zgodnyZRegionem(wpisBox([19.0, 49.2, 21.2, 50.45]), '18'), true, 'prostokąt Małopolski dotyka podkarpackiego (przybliżenie)');
  assert.equal(mod.zgodnyZRegionem(wpisBox([30, 55, 31, 56]), '02'), false);
  assert.equal(mod.zgodnyZRegionem(wpisBox([16.0, 51.0, 18.0, 51.5], ['1263']), '02'), false, 'kod TERYT rozstrzyga, gdy jest');
  assert.equal(mod.przecinaSie([0, 0, 1, 1], [1, 1, 2, 2]), true, 'wspólny róg liczy się jak API (range)');
  assert.equal(mod.przecinaSie([0, 0, 1, 1], [1.01, 0, 2, 1]), false);
  const panel = read(`${dir}/PanelWarstw.tsx`);
  assert.match(panel, /Filtr przybliżony/); assert.match(panel, /aria-describedby="tz-woj-uwaga"/);
  assert.match(read(`${dir}/TerazPage.tsx`), /granice przybliżone/, 'przybliżenie także w opisie filtrów tabeli');
});

// ---------- P2-3: pamięć, adres, odnośniki ----------

test('pamięć i adres: wspólna walidacja kodów warstw, okresów i województw; null i śmieci w localStorage nie przerywają', () => {
  const pam = load(`${dir}/pamiec`);
  const par = load(`${dir}/parametry`);
  for (const surowy of [null, undefined, '', 'null', '[]', '"tekst"', '5', '{zle json', 'true']) assert.deepEqual({ ...pam.parsujPamiec(surowy) }, {}, `śmieci: ${surowy}`);
  const dobra = pam.parsujPamiec(JSON.stringify({ warstwy: ['rcb', 'x', '../../etc', 'rcb', 5], okres: '7d', woj: '14', powiaty: ['1813', '9999', 'abc', '0663'] }));
  assert.deepEqual([...dobra.warstwy], ['rcb']); assert.equal(dobra.okres, '7d'); assert.equal(dobra.woj, '14'); assert.deepEqual([...dobra.powiaty], ['1813', '0663']);
  assert.deepEqual({ ...pam.parsujPamiec(JSON.stringify({ warstwy: ['<script>', 'x'], okres: '1000d', woj: '99', powiaty: 'nie lista' })) }, {}, 'same nieprawidłowe pola są pomijane, lista samych śmieci nie wyłącza wszystkich warstw');
  assert.deepEqual([...pam.parsujPamiec(JSON.stringify({ warstwy: [] })).warstwy], [], 'jawny wybór „żadna” zostaje');
  assert.equal(pam.parsujPamiec(JSON.stringify({ warstwy: null, woj: null })).warstwy, null);
  assert.equal(pam.parsujPamiec(JSON.stringify({ woj: null })).woj, null);
  // ta sama walidacja w adresie
  assert.deepEqual([...par.parsuj({ warstwy: 'rcb,wymyslona,pozary,rcb, imgw_meteo ' }).warstwy], ['rcb', 'pozary', 'imgw_meteo']);
  assert.equal(par.parsuj({ okres: '9d' }).okres, '24h');
  assert.equal(par.parsuj({ woj: '07' }).woj, null);
  assert.deepEqual([...par.oczyscWarstwy(['rcb', ' pozary ', 7, 'xx'])], ['rcb', 'pozary']);
  assert.equal(par.oczyscWarstwy('rcb'), null);
  assert.equal(par.poprawnyOkres('7d'), true); assert.equal(par.poprawnyOkres('7D'), false);
  assert.equal(par.poprawneWojewodztwo('14'), true); assert.equal(par.poprawneWojewodztwo(14), false);
  const strona = read(`${dir}/TerazPage.tsx`);
  assert.ok(!/JSON\.parse\(window\.localStorage/.test(strona), 'strona nie parsuje pamięci sama');
  assert.match(strona, /czytajPamiec\(\)/);
});

test('link „kopiuj”: tylko parametry widoku z listy dozwolonych, bez obcych parametrów z adresu', () => {
  const mod = m();
  const adres = mod.adresWpisu('https://przeszlosc.today', '/teraz', { warstwy: ['rcb'], okres: '7d', woj: '14', wpis: null, widok: 'lista', probne: true }, 9001);
  assert.equal(adres, 'https://przeszlosc.today/teraz?warstwy=rcb&okres=7d&woj=14&wpis=9001&widok=lista&probne=1');
  assert.ok(!/utm_|fbclid|token|sesja/.test(adres));
  // P2-12: pełny zakres filtrów także dla wartości domyślnych (wszystkie warstwy, 24 godz., cała Polska)
  const domyslne = mod.adresWpisu('https://spin.clinic', '/przeszlosc/teraz', { warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'mapa', probne: false }, 5);
  assert.equal(domyslne, 'https://spin.clinic/przeszlosc/teraz?warstwy=wszystkie&okres=24h&woj=pl&wpis=5');
  const par = load(`${dir}/parametry`);
  const odebrany = par.parsuj(new URL(domyslne).searchParams);
  assert.equal(odebrany.warstwy, null); assert.equal(odebrany.okres, '24h'); assert.equal(odebrany.woj, null); assert.equal(odebrany.wpis, 5);
  const q = new URL(domyslne).searchParams;
  assert.ok(q.has('warstwy') && q.has('okres') && q.has('woj'), 'każdy filtr jawnie w adresie, więc pamięć odbiorcy go nie nadpisze');
  const strona = read(`${dir}/TerazPage.tsx`);
  assert.ok(!/window\.location\.search, wybranyId/.test(strona), 'adres wpisu nie przekazuje bieżącego zapytania');
  // zestaw powiatów też z listy dozwolonych (Z6b)
  const pow = load(`${dir}/powiaty`);
  assert.equal(pow.adresZestawu('https://x', '/teraz', ['1813'], '7d', false), 'https://x/teraz?widok=powiat&powiaty=1813&okres=7d');
});

test('odnośniki źródłowe: tylko bezwzględne http i https z hostem', () => {
  const { adresZrodla } = load(`${dir}/link`);
  assert.equal(adresZrodla('https://www.gov.pl/web/rcb'), 'https://www.gov.pl/web/rcb');
  assert.equal(adresZrodla('  http://example.org/a?b=1 '), 'http://example.org/a?b=1');
  for (const zly of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,x', 'vbscript:x', '/wzgledny', '//obcy.pl', 'ftp://x.pl', 'mailto:a@b.pl', '', 'gov.pl', 'https://', null, undefined, 5, {}]) assert.equal(adresZrodla(zly), null, String(zly));
  const czas = load(`${dir}/czas`);
  assert.equal(czas.host('javascript:alert(1)'), ''); assert.equal(czas.host('https://www.gov.pl/x'), 'gov.pl');
  for (const plik of ['KartaWpisu.tsx', 'MojPowiat.tsx', 'TabelaWpisow.tsx']) assert.ok(!/href=\{[a-z.]*link\}/.test(read(`${dir}/${plik}`)), `${plik}: href tylko przez adresZrodla`);
});

// ---------- P2-4: stałe ostrzeżenie, czasy odświeżenia ----------

test('stałe ostrzeżenie: zdanie nad przewijaną treścią, arkusze pod nim; osobne czasy odświeżenia stanu i wpisów', () => {
  const css = read(`${dir}/teraz.css`);
  assert.match(css, /grid-template-rows: auto auto minmax\(0, 1fr\)/, 'pasek, linia stanu ze zdaniem, dopiero potem przewijana treść');
  const telefon = css.slice(css.indexOf('/* ---------- Telefon: arkusze ---------- */'));
  assert.match(telefon, /\.tz-panel, \.tz-karta \{ position: absolute; left: 0; right: 0; bottom: 0;[^}]*max-height: min\(74dvh, 100%\)/, 'arkusze w obszarze głównym, pod linią stanu');
  assert.ok(!/\.tz-panel, \.tz-karta \{ position: fixed/.test(css), 'arkusze nie są przypięte do okna (mogłyby przykryć zdanie)');
  assert.match(telefon, /\.tz-karta \{ z-index: 31; max-height: min\(62dvh, 100%\); \}/);
  const { LiniaStanu } = load(`${dir}/LiniaStanu`);
  const mod = m(); const dane = d(); const teraz = Date.parse('2026-11-18T12:30:00+01:00');
  const podsumowanie = mod.podsumujStan(dane.probneStan(teraz), dane.probneWarstwy(teraz));
  const html = renderToStaticMarkup(React.createElement(LiniaStanu, { probne: false, podsumowanie, online: true, blad: false, odswiezonoWpisy: Date.parse('2026-11-18T12:29:00+01:00'), odswiezonoStan: Date.parse('2026-11-18T12:25:00+01:00'), ladowanie: false }));
  const tekst = tekstZHtml(html);
  assert.match(tekst, /Stan źródeł odświeżono: o godz\. 12:25\. Komunikaty odświeżono: o godz\. 12:29\./, 'dwa osobne czasy');
  const ZDANIE = load(`${dir}/warstwy`).ZDANIE_STALE;
  assert.ok(html.indexOf(ZDANIE) < html.indexOf('tz-stan__przelacznik') && html.indexOf(ZDANIE) < html.indexOf('id="tz-stan-szczegoly"'), 'zdanie przed zwijaną częścią');
  const bez = tekstZHtml(renderToStaticMarkup(React.createElement(LiniaStanu, { probne: false, podsumowanie, online: true, blad: false, odswiezonoWpisy: null, odswiezonoStan: null, ladowanie: false })));
  assert.match(bez, /Stan źródeł odświeżono: jeszcze nie\. Komunikaty odświeżono: jeszcze nie\./);
});

// ---------- P2-5: fokus i dotyk ----------

test('fokus i dotyk: scena nieaktywna pod arkuszem (inert), cele min. 44 px, miejsce na przycisk „Warstwy”', () => {
  const strona = read(`${dir}/TerazPage.tsx`);
  const css = read(`${dir}/teraz.css`);
  // P2-10: inert z faktycznie widocznego arkusza (panel jest tylko w widokach z mapą)
  assert.match(strona, /panelWidoczny = panel && wMapie/);
  assert.match(strona, /scenaNieaktywna = waski && \(panelWidoczny \|\| \(kartaOtwarta && widok !== 'mapa'\)\)/);
  assert.match(strona, /inert: '' as unknown as boolean/, 'atrybut inert przekazany tak, by React 18 go zapisał w DOM');
  assert.match(strona, /aria-label=\{NAZWY_WIDOKOW\[widok\]\} \{\.\.\.inert\}/);
  assert.match(strona, /window\.matchMedia\(WASKI_EKRAN\)/);
  assert.match(css, /max-width: 899\.98px/);
  // żaden interaktywny element nie ma jawnie mniejszej wysokości niż 44 px
  const male = css.split('\n').filter(l => /min-height:\s*(\d+)px/.test(l)).filter(l => /button|summary|przycisk|segmenty|opcja|sortuj|link|pole|podpowiedzi|przelacznik/.test(l)).filter(l => Number(/min-height:\s*(\d+)px/.exec(l)[1]) < 44);
  assert.deepEqual(male.map(l => l.trim().slice(0, 80)), [], 'cele dotykowe poniżej 44 px');
  assert.match(css, /\.tz-widok button \{ min-height: var\(--tz-tap\)/);
  assert.match(css, /\.tz-panel__akcje button \{ min-height: var\(--tz-tap\)/);
  assert.match(css, /\.maplibregl-ctrl-group button, \.tz \.maplibregl-ctrl-attrib-button \{ width: var\(--tz-tap\); height: var\(--tz-tap\)/);
  assert.match(css, /\.tz-lista-ramka \{[^}]*padding: 12px 12px calc\(84px \+ env\(safe-area-inset-bottom/, 'ostatni wiersz nie chowa się pod przyciskiem „Warstwy”');
  assert.match(css, /\.tz \.tz-fab \{ position: fixed; left: 12px; bottom: calc\(14px \+ env\(safe-area-inset-bottom/);
  // okres jako natywne radia z celem 44 px
  assert.match(css, /\.tz-okresy__opcja span \{[^}]*min-height: var\(--tz-tap\)/);
});

// ---------- P2-6: zapytania ----------

test('zapytania: start po odczycie preferencji, rzadsze odpytywanie warstw i zdarzeń, odświeżenie po powrocie do karty', () => {
  const api = read(`${dir}/api.ts`);
  const strona = read(`${dir}/TerazPage.tsx`);
  assert.match(strona, /useWpisy\(probne, okres, woj, wMapie && pamiecGotowa\)/, 'bez zapytania przed odczytem preferencji');
  assert.match(strona, /useWpisyPowiatow\(probne, okres, wojKody, !wMapie && pamiecGotowa\)/);
  assert.match(api, /ODSWIEZANIE_MS = 30_000/); assert.match(api, /ODSWIEZANIE_ZDARZEN_MS = 60_000/); assert.match(api, /ODSWIEZANIE_WARSTW_MS = 120_000/);
  assert.match(api, /refetchOnWindowFocus: true/, 'domyślny klient aplikacji wyłącza to odświeżanie, więc włączamy jawnie');
  assert.match(api, /refetchIntervalInBackground: false/);
  const a = load(`${dir}/api`);
  assert.ok(a.ODSWIEZANIE_WARSTW_MS > a.ODSWIEZANIE_ZDARZEN_MS && a.ODSWIEZANIE_ZDARZEN_MS > a.ODSWIEZANIE_MS);
  const adresy = [];
  stub.fetch = async adres => { adresy.push(adres); return odpowiedz({ count: 0, next: null, previous: null, results: [] }); };
  return a.pobierzWpisy('24h', '14').then(() => {
    assert.equal(adresy.length, 2, 'region: jedno zapytanie TERYT i jedno o prostokąt');
    const od = adresy.map(x => new URL(x, 'http://x').searchParams.get('od'));
    assert.equal(od[0], od[1]);
    assert.match(od[0], /:00\.000Z$/, 'parametr od zaokrąglony do minuty');
    assert.equal(a.odKiedy('1h', Date.parse('2026-11-18T12:00:59.999Z')), '2026-11-18T11:00:00.000Z');
  });
});

// ---------- P3 ----------

test('dane próbne zgodne z kontraktem stan/ i warstwy/ z backendu (teksty i pole wylaczona)', () => {
  const backend = fs.readFileSync(path.join(root, '..', 'backend', 'teraz', 'api.py'), 'utf8');
  assert.match(backend, /"brak w naszych danych"/); assert.match(backend, /komunikatów z 24 h: /); assert.match(backend, /"wylaczona": warstwa in wylaczone/);
  const stan = d().probneStan(Date.parse('2026-11-18T12:00:00+01:00'));
  for (const l of stan.warstwy) assert.match(l.komunikaty, /^komunikatów z 24 h: \d+$/);
  assert.ok(stan.warstwy.every(l => /^ostatnie pobranie: \d{2}:\d{2}$/.test(l.ostatnie_pobranie) || l.ostatnie_pobranie === 'brak w naszych danych'));
  const warstwy = d().probneWarstwy();
  assert.equal(warstwy.length, 18); assert.ok(warstwy.every(x => typeof x.wylaczona === 'boolean'));
  // przykładowa odpowiedź warstwy/ przechodzi walidację klienta bez pominięć
  assert.equal(w().walidujWarstwy(JSON.parse(JSON.stringify(warstwy))).length, 18);
  assert.equal(w().walidujStan(JSON.parse(JSON.stringify(stan))).warstwy.length, 18);
});

test('Node 20: jedyny pakiet z engines >= 22 w lockfile to parser JSON w przeglądarkowym kodzie MapLibre (pnpm tylko ostrzega)', () => {
  const lock = fs.readFileSync(path.join(root, '..', 'pnpm-lock.yaml'), 'utf8').split(String.fromCharCode(13)).join('');
  const pakiety = [...lock.matchAll(/^ {2}'?([^\s'][^\n]*?)'?:\n(?: {4}[^\n]*\n)*? {4}engines: \{node: '?([^}']+)'?\}/gm)];
  const wymagajace = pakiety.filter(([, , wymog]) => /(>=|>)\s*2[2-9]/.test(wymog)).map(([, nazwa]) => nazwa);
  assert.deepEqual([...new Set(wymagajace)], ['@mapbox/jsonlint-lines-primitives@2.0.3'], 'nowa zależność wymagająca Node 22 wymaga osobnej decyzji');
  // ten pakiet wchodzi tylko przez @maplibre/maplibre-gl-style-spec (maplibre-gl), ładowane dynamicznie w przeglądarce
  assert.match(lock, /'@maplibre\/maplibre-gl-style-spec@[^']+':\n {4}dependencies:\n {6}'@mapbox\/jsonlint-lines-primitives': 2\.0\.3/);
  assert.ok(!/engine-strict/.test(fs.existsSync(path.join(root, '..', '.npmrc')) ? fs.readFileSync(path.join(root, '..', '.npmrc'), 'utf8') : ''), 'engine-strict wyłączone: wymóg engines daje ostrzeżenie, nie błąd instalacji');
  assert.match(fs.readFileSync(path.join(root, '..', 'Dockerfile.frontend'), 'utf8'), /FROM node:20-alpine/);
  assert.match(fs.readFileSync(path.join(root, '..', '.github', 'workflows', 'ci.yml'), 'utf8'), /node-version: '20'/);
});

// „Teraz” (Z6b): słownik powiatów, wyszukiwarka z odmianą, dopasowanie komunikatów do powiatu po TERYT, parametry adresu
// i widok „Mój powiat” (render po stronie serwera, bez przeglądarki). node --test, bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const mocks = { '@tanstack/react-query': { useQuery: () => ({}), keepPreviousData: {} } };
const cache = new Map();
const stub = { fetch: () => { throw new Error('fetch nie jest podstawiony'); } };
/** Wczytuje moduł TS/TSX z katalogu teraz razem z jego względnymi importami (prawdziwy React, bez mapy). */
function load(file) {
  if (file.endsWith('.json')) return JSON.parse(read(file));
  const bez = file.replace(/\.tsx?$/, '');
  const kandydaci = [`${bez}.ts`, `${bez}.tsx`, `${bez}/index.ts`];
  const wzgledna = kandydaci.find(k => fs.existsSync(path.join(root, k)));
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
    return require(name); // react, react/jsx-runtime
  };
  new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} }, (...args) => stub.fetch(...args));
  return module.exports;
}

const kolator = new Intl.Collator('pl');
const slownik = () => load(`${dir}/slownik`);
const powiaty = () => load(`${dir}/powiaty`);

test('słownik: 380 powiatów i 16 województw, liczby jak w rejestrze, zakresy kodów ziemskich i miast', () => {
  const plik = load('public/teraz/teryt-powiaty.json');
  assert.equal(plik.wojewodztwa.length, 16);
  assert.equal(plik.powiaty.length, 380);
  const oczekiwane = { '02': 30, '04': 23, '06': 24, '08': 14, '10': 24, '12': 22, '14': 42, '16': 12, '18': 25, '20': 17, '22': 20, '24': 36, '26': 14, '28': 21, '30': 35, '32': 21 };
  const kodyWoj = new Set(plik.wojewodztwa.map(w => w.kod));
  assert.deepEqual([...kodyWoj].sort(), Object.keys(oczekiwane).sort());
  assert.equal(new Set(plik.powiaty.map(p => p.kod)).size, 380, 'kody są unikalne');
  assert.equal(plik.powiaty.filter(p => p.miasto).length, 66, '66 miast na prawach powiatu');
  assert.equal(plik.powiaty.filter(p => !p.miasto).length, 314, '314 powiatów ziemskich');
  for (const [woj, liczba] of Object.entries(oczekiwane)) {
    const swoje = plik.powiaty.filter(p => p.kod.startsWith(woj));
    assert.equal(swoje.length, liczba, `liczba powiatów w ${woj}`);
    const ziemskie = swoje.filter(p => !p.miasto);
    const miasta = swoje.filter(p => p.miasto);
    // powiaty ziemskie mają kody 01 do 60, miasta na prawach powiatu od 61; kolejność kodów rośnie, ale NIE jest alfabetyczna
    // (powiaty utworzone po 1999 roku dostały kody na końcu listy swojego województwa), a w numeracji bywają luki
    for (const p of ziemskie) assert.ok(Number(p.kod.slice(2)) >= 1 && Number(p.kod.slice(2)) <= 60, `kod powiatu ziemskiego ${p.kod} ${p.nazwa}`);
    for (const p of miasta) assert.ok(Number(p.kod.slice(2)) >= 61, `kod miasta ${p.kod} ${p.nazwa}`);
    assert.deepEqual(swoje.map(p => p.kod), [...swoje.map(p => p.kod)].sort(), `kody posortowane w ${woj}`);
    assert.ok(ziemskie.length > 0 && miasta.length > 0, `${woj}: są powiaty ziemskie i miasta`);
  }
  void kolator;
  for (const p of plik.powiaty) {
    assert.match(p.kod, /^[0-9]{4}$/);
    assert.ok(kodyWoj.has(p.kod.slice(0, 2)));
    assert.ok(p.nazwa.length >= 3 && p.nazwa === p.nazwa.trim());
    assert.ok(!/[–—]/.test(p.nazwa));
  }
});

test('słownik: znane pary kod i nazwa (m.in. z danych próbnych), źródło i data w pliku, zgodność z województwami w kodzie', () => {
  const s = slownik();
  const nazwa = kod => s.powiatOKodzie(kod)?.nazwa;
  const znane = {
    '0602': 'biłgorajski', '0604': 'hrubieszowski', '0620': 'zamojski', '0663': 'Lublin', '1261': 'Kraków', '1263': 'Tarnów',
    '1465': 'Warszawa', '1804': 'jarosławski', '1809': 'lubaczowski', '1813': 'przemyski', '1863': 'Rzeszów',
    '1061': 'Łódź', '2261': 'Gdańsk', '2469': 'Katowice', '3064': 'Poznań', '3262': 'Szczecin', '0264': 'Wrocław',
  };
  for (const [kod, n] of Object.entries(znane)) assert.equal(nazwa(kod), n, kod);
  // wyjątki od porządku alfabetycznego, wyłapane przy porównaniu z PRG GUGiK (każdy wyglądał wiarygodnie w liście z pamięci)
  const wyjatki = { '0206': 'karkonoski', '1814': 'przeworski', '1821': 'leski', '1021': 'brzeziński', '0812': 'wschowski', '2214': 'tczewski', '2216': 'sztumski', '2414': 'bieruńsko-lędziński', '2818': 'gołdapski', '3218': 'łobeski', '1432': 'warszawski zachodni', '0265': 'Wałbrzych' };
  for (const [kod, n] of Object.entries(wyjatki)) assert.equal(nazwa(kod), n, `wyjątek ${kod}`);
  assert.equal(s.powiatOKodzie('1431'), undefined, 'w numeracji mazowieckiego jest luka');
  assert.equal(s.powiatOKodzie('0263'), undefined, 'w numeracji miast dolnośląskiego jest luka');
  assert.equal(s.powiatOKodzie('1899'), undefined);
  const plik = load('public/teraz/teryt-powiaty.json');
  assert.ok(/TERYT/.test(plik.zrodlo) && /GUS|Główny Urząd Statystyczny/.test(plik.zrodlo), 'źródło wymienione w pliku');
  assert.match(plik.data, /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/);
  assert.equal(typeof plik.zweryfikowano_z_rejestrem, 'boolean', 'plik mówi, czy porównano go z oficjalnym plikiem');
  assert.equal(s.SLOWNIK_META.zweryfikowano, plik.zweryfikowano_z_rejestrem);
  const t = load(`${dir}/teryt`);
  assert.deepEqual(t.WOJEWODZTWA.map(w => [w.kod, w.nazwa]), plik.wojewodztwa.map(w => [w.kod, w.nazwa]), 'nazwy województw w kodzie i w słowniku są takie same');
  assert.ok(!/[–—]/.test(read('public/teraz/teryt-powiaty.json')), 'bez długich myślników także w pliku danych');
});

test('słownik: dopełniacz do zdań („dla powiatu przemyskiego”, „dla miasta Krakowa”)', () => {
  const s = slownik();
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('1813')), 'dla powiatu przemyskiego');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('1261')), 'dla miasta Krakowa');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('1006')), 'dla powiatu łódzkiego wschodniego');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('1815')), 'dla powiatu ropczycko-sędziszowskiego');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('0206')), 'dla powiatu karkonoskiego');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('2461')), 'dla miasta Bielska-Białej');
  assert.equal(s.dlaPowiatu(s.powiatOKodzie('0661')), 'dla miasta Białej Podlaskiej');
  for (const p of s.POWIATY) {
    assert.ok(p.dopelniacz.length >= 3);
    if (!p.miasto) assert.ok(/ego$/.test(p.dopelniacz), `dopełniacz powiatu ${p.nazwa}: ${p.dopelniacz}`);
    else assert.notEqual(p.dopelniacz, '', p.nazwa);
  }
  assert.equal(s.nazwaPowiatu(s.powiatOKodzie('1813')), 'powiat przemyski');
  assert.equal(s.nazwaPowiatu(s.powiatOKodzie('1261')), 'Kraków (miasto na prawach powiatu)');
  assert.equal(s.pelnaNazwaPowiatu(s.powiatOKodzie('1813')), 'powiat przemyski, podkarpackie');
  assert.equal(s.dopelniaczWojewodztwa('podkarpackie'), 'podkarpackiego');
  assert.equal(s.dopelniaczWojewodztwa('kujawsko-pomorskie'), 'kujawsko-pomorskiego');
});

test('nazwy w danych próbnych: żaden powiat nie jest już „o kodzie ...”', () => {
  const t = load(`${dir}/teryt`);
  const d = load(`${dir}/dane-probne/index`);
  const kody = new Set(d.probneWpisy().flatMap(w => w.teryt));
  assert.equal(kody.size, 7, 'kody z danych próbnych: 3 powiaty RCB, 1 powiat odwołania, województwo, 2 miasta IMGW');
  for (const k of kody) assert.ok(!/o kodzie/.test(t.nazwaObszaru(k)), `${k}: ${t.nazwaObszaru(k)}`);
  const w9001 = d.probneWpisy().find(w => w.id === 9001);
  assert.equal(t.opisMiejsca(w9001), 'dotyczy: powiat jarosławski (podkarpackie), powiat lubaczowski (podkarpackie), powiat przemyski (podkarpackie)');
  const w9004 = d.probneWpisy().find(w => w.id === 9004);
  assert.equal(t.opisMiejsca(w9004), 'dotyczy: miasto Kraków (małopolskie), miasto Tarnów (małopolskie)');
  assert.equal(t.nazwaObszaru('1899'), 'powiat o kodzie 1899 (podkarpackie)', 'kod spoza słownika: bez zgadywania nazwy');
});

test('wyszukiwarka: odmiana nazw, autouzupełnianie, kod TERYT, słowa pomijane', () => {
  const p = powiaty();
  const pierwszy = tekst => p.szukajPowiatow(tekst)[0]?.kod;
  assert.equal(pierwszy('przemyski'), '1813');
  assert.equal(pierwszy('powiat przemyskiego'), '1813', 'dopełniacz i słowo „powiat”');
  assert.equal(pierwszy('Przemyślu'), '1862', 'miejscownik miasta');
  assert.equal(pierwszy('w Krakowie'), '1261', 'miasto przed powiatem krakowskim');
  assert.deepEqual(p.szukajPowiatow('Krakowie').map(x => x.kod), ['1261'], 'odmienione „Krakowie” to miasto, nie powiat krakowski');
  assert.deepEqual(p.szukajPowiatow('Kraków').map(x => x.kod), ['1261', '1206'], 'wpisane „Kraków”: miasto i powiat krakowski, miasto pierwsze');
  assert.equal(pierwszy('Białej Podlaskiej'), '0661');
  assert.equal(pierwszy('Nowego Sącza'), '1262');
  assert.equal(pierwszy('Jastrzębiu-Zdroju'), '2467');
  assert.equal(pierwszy('Zielonej Górze'), '0862');
  assert.equal(pierwszy('Gorzowie Wielkopolskim'), '0861');
  assert.equal(pierwszy('Piotrkowie Trybunalskim'), '1062');
  assert.equal(pierwszy('Katowicach'), '2469');
  assert.equal(pierwszy('Warszawie'), '1465');
  assert.equal(pierwszy('Łodzi'), '1061');
  assert.equal(pierwszy('lodz'), '1061', 'bez polskich znaków');
  assert.equal(pierwszy('m. Tarnów'), '1263');
  assert.equal(pierwszy('KRAKÓW'), '1261', 'wielkość liter bez znaczenia');
  assert.equal(pierwszy('1813'), '1813', 'kod TERYT');
  assert.ok(p.szukajPowiatow('prz').map(x => x.kod).includes('1813'), 'autouzupełnianie po początku');
  assert.ok(p.szukajPowiatow('prz').length <= 8, 'domyślny limit podpowiedzi');
  assert.equal(p.szukajPowiatow('k', { limit: 3 }).length, 3);
  assert.deepEqual(p.szukajPowiatow('Przemyśl', { pomin: ['1862'] }).map(x => x.kod).includes('1862'), false, 'już wybrane nie wracają w podpowiedziach');
  assert.deepEqual(p.szukajPowiatow(''), []);
  assert.deepEqual(p.szukajPowiatow('powiat'), [], 'same słowa pomijane');
  assert.deepEqual(p.szukajPowiatow('xyzxyz'), []);
  assert.equal(p.normalizuj('Jastrzębie-Zdrój'), 'jastrzebie zdroj');
});

test('dopasowanie wpisów: powiat, gmina w powiecie i całe województwo (po kodach TERYT wpisu i potwierdzonym zasięgu)', () => {
  const p = powiaty();
  // kod województwa to „całe województwo” tylko przy potwierdzonym zasięgu (`zasieg: obszar`, recenzja PR #38, P1-2)
  const zakres = (teryt, kod) => p.zakresDlaPowiatu({ teryt, zasieg: 'obszar', miejsce: '' }, kod);
  assert.equal(zakres(['1813'], '1813'), 'powiat');
  assert.equal(zakres(['1813011'], '1813'), 'gmina');
  assert.equal(zakres(['18'], '1813'), 'wojewodztwo');
  assert.equal(zakres(['1809'], '1813'), null, 'inny powiat w tym samym województwie');
  assert.equal(zakres(['06'], '1813'), null, 'inne województwo');
  assert.equal(zakres(['1809', '1813'], '1813'), 'powiat');
  assert.equal(zakres(['18', '1813'], '1813'), 'powiat', 'najwęższy zakres wygrywa');
  assert.equal(zakres(['18', '1813011'], '1813'), 'gmina');
  assert.equal(zakres([], '1813'), null, 'wpis bez kodu nie dotyczy żadnego powiatu');
  assert.equal(p.zakresDlaPowiatu({ teryt: ['18'] }, '1813'), 'bezListy', 'brak informacji o zasięgu: nie poszerzamy do całego województwa');
  assert.equal(p.zakresDlaPowiatu({ teryt: ['18'], zasieg: 'przyblizony', miejsce: '' }, '1813'), 'bezListy');
  assert.equal(p.zakresTekstem('wojewodztwo', '1813'), 'dotyczy całego województwa podkarpackiego');
  assert.equal(p.zakresTekstem('gmina', '1813'), 'dotyczy gminy w tym powiecie');
  const d = load(`${dir}/dane-probne/index`);
  const wpisy = d.probneWpisy();
  const dla = kod => wpisy.filter(w => p.zakresDlaPowiatu(w, kod)).map(w => [w.id, p.zakresDlaPowiatu(w, kod)]);
  assert.deepEqual(dla('1813'), [[9001, 'powiat']]);
  assert.deepEqual(dla('0604').sort(), [[9002, 'powiat'], [9003, 'wojewodztwo'], [9006, 'pozaLista']].sort());
  assert.deepEqual(dla('0663').sort(), [[9003, 'wojewodztwo'], [9006, 'pozaLista']].sort(), 'Lublin: komunikat dla całego województwa i osobno alert, który Lublina nie wymienia');
  assert.deepEqual(dla('0662').sort(), [[9003, 'wojewodztwo'], [9006, 'wymieniony']].sort(), 'Chełm: wymieniony w alercie z 10.11');
  assert.deepEqual(dla('3064'), [], 'Poznań: nic w danych');
  assert.deepEqual(p.kodyWojewodztw(['1813', '0663', '1809', '0604']), ['06', '18']);
});

test('parametry adresu „Mój powiat”: walidacja, limit 5, zapis, link do zestawu', () => {
  const p = powiaty();
  assert.deepEqual(p.parsujPowiaty({}), []);
  assert.deepEqual(p.parsujPowiaty({ powiaty: '1813,0663,1813,9999,abc,<script>,0602,0604,0620,1263' }), ['1813', '0663', '0602', '0604', '0620'], 'bez powtórzeń i nieznanych, najwyżej 5');
  assert.deepEqual(p.parsujPowiaty(new URLSearchParams('powiaty=1261%2C1263')), ['1261', '1263']);
  assert.deepEqual(p.parsujPowiaty({ powiaty: ['1813', '0663'] }), ['1813'], 'pierwsza wartość parametru');
  assert.equal(p.MAKS_POWIATOW, 5);
  assert.deepEqual(p.oczyscKody(['1813', 1813, null, '18', '1813']), ['1813']);
  assert.equal(p.zapytanieZPowiatami('?okres=7d', ['1813', '0663']), '?okres=7d&powiaty=1813%2C0663');
  assert.equal(p.zapytanieZPowiatami('?okres=7d&powiaty=1813', []), '?okres=7d');
  assert.equal(p.zapytanieZPowiatami('', []), '');
  const adres = p.adresZestawu('https://przeszlosc.today', '/teraz', ['1813', '0663'], '24h', false);
  assert.equal(adres, 'https://przeszlosc.today/teraz?widok=powiat&powiaty=1813%2C0663&okres=24h', 'okres zawsze w linku, także domyślny (P2-12)');
  assert.equal(p.adresZestawu('https://x.pl', '/teraz', ['1813'], '7d', true), 'https://x.pl/teraz?widok=powiat&powiaty=1813&okres=7d&probne=1');
  const q = new URL(adres).searchParams;
  assert.deepEqual(p.parsujPowiaty(q), ['1813', '0663'], 'link odtwarza zestaw');
  const par = load(`${dir}/parametry`);
  assert.equal(par.parsuj(q).widok, 'powiat');
  assert.equal(par.parsuj({ widok: 'tabela' }).widok, 'tabela');
  assert.equal(par.parsuj({ widok: 'lista' }).widok, 'lista');
  assert.equal(par.parsuj({ widok: 'cokolwiek' }).widok, 'mapa');
  assert.ok(par.zbudujZapytanie({ warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'powiat', probne: false }, '?powiaty=1813').includes('widok=powiat'));
  assert.ok(par.zbudujZapytanie({ warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'tabela', probne: false }, '?powiaty=1813').includes('powiaty=1813'), 'parametr powiatów zostaje');
  assert.equal(p.liczbaKomunikatow(1), '1 komunikat');
  assert.equal(p.liczbaKomunikatow(3), '3 komunikaty');
  assert.equal(p.liczbaKomunikatow(5), '5 komunikatów');
  assert.equal(p.liczbaKomunikatow(12), '12 komunikatów');
  assert.equal(p.liczbaKomunikatow(22), '22 komunikaty');
  assert.equal(p.liczbaKomunikatow(0), '0 komunikatów');
});

test('API: wpisy do „Mój powiat” po województwach, bez filtra prostokąta, bez powtórzeń, z flagą ucięcia', async () => {
  const a = load(`${dir}/api`);
  const wpis = (id, minut) => ({ id, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', tytul: `Wpis ${id}`, tresc: '', link: 'https://www.gov.pl/', opublikowano_at: new Date(Date.now() - minut * 60_000).toISOString(), pobrano_at: new Date(Date.now() - minut * 60_000).toISOString(), klasa: 'zwykly', teryt: ['14'], szerokosc: null, dlugosc: null, bbox: null, dokladnosc: 'wojewodztwo', pewnosc_lokalizacji: 0 });
  const adresy = [];
  stub.fetch = async adres => {
    adresy.push(adres);
    const dane = adres.includes('teryt=14') ? [wpis(1, 30), wpis(2, 10)] : [wpis(2, 10), wpis(3, 5)];
    return { ok: true, status: 200, json: async () => ({ count: dane.length, next: null, previous: null, results: dane }) };
  };
  const wynik = await a.pobierzWpisyTeryt('24h', ['14', '18']);
  assert.deepEqual(wynik.wpisy.map(x => x.id), [3, 2, 1], 'najnowsze pierwsze, bez powtórzeń');
  assert.equal(wynik.uciete, false);
  assert.equal(adresy.length, 2, 'jedno zapytanie na województwo');
  assert.ok(adresy.every(x => !x.includes('bbox')), 'powiat dopasowujemy po kodzie, nie po prostokącie');
  assert.ok(adresy.some(x => x.includes('teryt=14')) && adresy.some(x => x.includes('teryt=18')));
  stub.fetch = async () => ({ ok: true, status: 200, json: async () => ({ count: 999, next: 'x', previous: null, results: [wpis(7, 1)] }) });
  const ucieta = await a.pobierzWpisyTeryt('7d', ['06']);
  assert.equal(ucieta.uciete, true, 'przy ucięciu „brak wpisu” nie jest pewny');
  stub.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(a.pobierzWpisyTeryt('24h', ['06']), err => err.name === 'BladApi' && err.status === 0);
  const zrodlo = read(`${dir}/api.ts`);
  const hak = zrodlo.slice(zrodlo.indexOf('export function useWpisyPowiatow'), zrodlo.indexOf('export function useZdarzenia'));
  assert.ok(!/placeholderData/.test(hak.replace(/\/\/.*$/gm, '')), 'bez keepPreviousData: stare dane nie mogą udawać kompletnych po zmianie zestawu');
});

// ---------- widok „Mój powiat” renderowany po stronie serwera ----------
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function renderuj(props) {
  const { MojPowiat } = load(`${dir}/MojPowiat`);
  const m = load(`${dir}/model`);
  const d = load(`${dir}/dane-probne/index`);
  const teraz = Date.now();
  const wpisy = props.probne === false ? [] : d.probneWpisy(teraz);
  const domyslne = {
    powiaty: ['1813'], onZmien() {}, okres: '7d', onOkres() {}, widoki: m.zbudujWidoki(wpisy, d.probneZdarzenia(teraz)), warstwy: d.probneWarstwy(teraz),
    ladowanie: false, blad: false, uciete: false, pominiete: 0, pobrane: wpisy.length, niepotwierdzone: 0, warstwyPotwierdzone: true, nieaktualne: false, lukaWDanych: false, poczatekOkresu: new Date(teraz - 7 * 86_400_000).toISOString(), adres: () => 'x',
  };
  const { probne, ...reszta } = props; void probne;
  return renderToStaticMarkup(React.createElement(MojPowiat, { ...domyslne, ...reszta }));
}
const bezZnacznikow = html => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ');

test('„Mój powiat”: powiat z komunikatem pokazuje te same godziny i status co karta, bez zdania o braku', () => {
  const tekst = bezZnacznikow(renderuj({ powiaty: ['1813'] }));
  assert.match(tekst, /powiat przemyski, podkarpackie/);
  assert.match(tekst, /Przykład: zagrożenie z powietrza w powiatach przemyskim/);
  assert.match(tekst, /Opublikowano u źródła/);
  assert.match(tekst, /Pobrano przez nas/);
  assert.match(tekst, /dziś o godz\. \d{2}:\d{2}/);
  assert.match(tekst, /Komunikat oficjalny/);
  assert.match(tekst, /Godzina pochodzi z publikacji na stronie gov\.pl/, 'uwaga o godzinie RCB jak na karcie');
  assert.match(tekst, /Otwórz oryginał u źródła \(gov\.pl\)/);
  assert.match(tekst, /1 komunikat w ostatnich 7 dniach/);
  assert.ok(!/Brak w naszych danych/.test(tekst));
});

test('„Mój powiat”: całe województwo (potwierdzony zasięg) jako „dotyczy całego województwa”, odwołanie z innym statusem', () => {
  const tekst = bezZnacznikow(renderuj({ powiaty: ['0604'] }));
  assert.match(tekst, /dotyczy całego województwa lubelskiego/);
  assert.match(tekst, /Inne komunikaty z województwa: 1/, 'alert do wybranych powiatów (9006) bez powiatu hrubieszowskiego stoi osobno');
  assert.match(tekst, /Odwołane/);
  assert.match(tekst, /2 komunikaty w ostatnich 7 dniach/);
  const html = renderuj({ powiaty: ['0604'] });
  assert.ok(html.indexOf('ostrzeżenie przed silnym wiatrem') < html.indexOf('odwołanie zagrożenia z powietrza'), 'od najnowszego (140 min) do starszego (ponad dobę)');
});

test('„Mój powiat”: brak komunikatów to „Brak w naszych danych dla powiatu X od godz. Y. Sprawdź Alert RCB i 112.”, nigdy „spokojnie”', () => {
  const poczatek = new Date().toISOString();
  const czas = load(`${dir}/czas`);
  const tekst = bezZnacznikow(renderuj({ powiaty: ['3064', '1813'], poczatekOkresu: poczatek, okres: '24h', widoki: [] }));
  assert.ok(tekst.includes(`Brak w naszych danych dla miasta Poznania od godz. ${czas.godzina(poczatek)}. Sprawdź Alert RCB i 112.`), tekst);
  assert.ok(tekst.includes(`Brak w naszych danych dla powiatu przemyskiego od godz. ${czas.godzina(poczatek)}. Sprawdź Alert RCB i 112.`));
  assert.ok(!/spokojn|bezpieczn/i.test(tekst));
  const stary = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], poczatekOkresu: new Date(Date.now() - 3 * 86_400_000).toISOString() }));
  assert.match(stary, /Brak w naszych danych dla powiatu przemyskiego od \d+ \p{L}+, godz\. \d{2}:\d{2}\./u, 'dłuższy okres: z datą');
});

test('„Mój powiat”: ładowanie i błąd nie udają braku komunikatów; przy ucięciu nie ma „Brak w naszych danych”, jest liczba pobranych', () => {
  const laduje = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], ladowanie: true }));
  assert.match(laduje, /Wczytujemy komunikaty/);
  assert.ok(!/Brak w naszych danych/.test(laduje));
  const blad = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], blad: true }));
  assert.match(blad, /Nie udało się pobrać komunikatów: nie mamy pewności, sprawdź Alert RCB i 112\./);
  assert.ok(!/Brak w naszych danych/.test(blad));
  // P1-3: przy danych częściowych zamiast „brak” liczba pobranych i ograniczenie, także przy zerze
  const ucieta = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], uciete: true, pobrane: 0, lukaWDanych: true }));
  assert.ok(!/Brak w naszych danych/.test(ucieta), ucieta);
  assert.match(ucieta, /Dane niepełne: pobraliśmy 0 komunikatów z województwa; pobraliśmy tylko najnowsze/);
  assert.match(ucieta, /mogło być więcej/);
  assert.match(ucieta, /lukę w danych/);
  const pominiete = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], pominiete: 2, pobrane: 300 }));
  assert.match(pominiete, /pobraliśmy 300 komunikatów z województwa; pominęliśmy komunikaty o nieznanym formacie \(2\)/);
  assert.ok(!/Brak w naszych danych/.test(pominiete));
  const niepotwierdzone = bezZnacznikow(renderuj({ powiaty: ['1813'], widoki: [], niepotwierdzone: 4 }));
  assert.match(niepotwierdzone, /ukrywamy komunikaty z warstw bez aktualnego potwierdzenia \(4\)/);
});

test('„Mój powiat”: ostrzeżenie o obcięciu nie znika przez jedno trafienie', () => {
  const tekst = bezZnacznikow(renderuj({ powiaty: ['1813'], uciete: true, pobrane: 300 }));
  assert.match(tekst, /Przykład: zagrożenie z powietrza w powiatach przemyskim/, 'trafienie jest pokazane');
  assert.match(tekst, /Dane niepełne: pobraliśmy 300 komunikatów/, 'a ostrzeżenie zostaje');
  assert.match(tekst, /1 komunikat w ostatnich 7 dniach, od najnowszego \(wśród pobranych\)/);
});

test('„Mój powiat”: alert RCB z 10.11 dla wybranych powiatów: Chełm wymieniony, Lublin osobno, bez „całego województwa”', () => {
  const { POWIATY_ALERTU_RCB_1011 } = load(`${dir}/dane-probne/index`);
  const p = powiaty();
  // `miejsce` dokładnie w formie z parsera RCB dla próbki backend/teraz/tests/fixtures/alert-rcb-2026-11-10-zagrozenie-z-powietrza.html
  const miejsce = ['lubelskiego', ...POWIATY_ALERTU_RCB_1011.map(nazwa => `lubelskie: ${nazwa}`)].join('\n');
  const miejsceStarsze = ['lubelskiego', ...POWIATY_ALERTU_RCB_1011].join('\n'); // wiersze sprzed podpisywania jednostek województwem
  const fs2 = require('node:fs');
  const html = fs2.readFileSync(path.join(root, '..', 'backend', 'teraz', 'tests', 'fixtures', 'alert-rcb-2026-11-10-zagrozenie-z-powietrza.html'), 'utf8');
  for (const nazwa of POWIATY_ALERTU_RCB_1011) assert.ok(html.includes(nazwa), `próbka wymienia: ${nazwa}`);
  const alert = { teryt: ['06'], zasieg: 'przyblizony', miejsce };
  for (const m of [miejsce, miejsceStarsze]) {
    assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: m }, '0662'), 'wymieniony', 'Chełm tak (oba formaty)');
    assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: m }, '0663'), 'pozaLista', 'Lublin nie (oba formaty)');
  }
  assert.equal(p.zakresDlaPowiatu(alert, '0662'), 'wymieniony', 'Chełm (miasto na prawach powiatu)');
  assert.equal(p.zakresDlaPowiatu(alert, '0603'), 'wymieniony', 'powiat chełmski');
  assert.equal(p.zakresDlaPowiatu(alert, '0661'), 'wymieniony', 'Biała Podlaska');
  assert.equal(p.zakresDlaPowiatu(alert, '0619'), 'wymieniony', 'powiat włodawski');
  assert.equal(p.zakresDlaPowiatu(alert, '0663'), 'pozaLista', 'Lublina nie ma na liście');
  assert.equal(p.zakresDlaPowiatu(alert, '0609'), 'pozaLista', 'powiatu lubelskiego nie ma na liście („lubelskiego” to województwo)');
  assert.equal(p.zakresDlaPowiatu(alert, '1813'), null, 'inne województwo');
  // niejednoznaczne: na liście tylko miasto Chełm, bez powiatu chełmskiego (i odwrotnie)
  assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: 'lubelskiego\nChełm' }, '0603'), 'mozliwy');
  assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: 'lubelskiego\nchełmski' }, '0662'), 'mozliwy');
  assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: 'lubelskiego\nChełm' }, '0662'), 'wymieniony');
  // odmiana: „w Chełmie”, „powiatu włodawskiego”
  assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: 'Chełmie\npowiatu włodawskiego' }, '0662'), 'wymieniony');
  assert.equal(p.zakresDlaPowiatu({ ...alert, miejsce: 'Chełmie\npowiatu włodawskiego' }, '0619'), 'wymieniony');
  assert.equal(p.zakresTekstem('wymieniony', '0662'), 'Twój powiat jest wymieniony w komunikacie');
  assert.equal(p.zakresTekstem('pozaLista', '0663'), 'Komunikat w Twoim województwie, Twojego powiatu nie ma na liście');
  assert.match(p.zakresTekstem('mozliwy', '0603'), /możliwe.*sprawdź treść komunikatu/);

  // render: Chełm ma alert na liście, Lublin tylko w osobnej grupie; nigdzie „całego województwa” dla tego alertu
  const m = load(`${dir}/model`);
  const d = load(`${dir}/dane-probne/index`);
  const tylkoAlert = d.probneWpisy().filter(w => w.id === 9006);
  assert.equal(tylkoAlert[0].miejsce, miejsce);
  const widoki = m.zbudujWidoki(tylkoAlert, []);
  const chelm = bezZnacznikow(renderuj({ powiaty: ['0662'], widoki }));
  assert.match(chelm, /Twój powiat jest wymieniony w komunikacie/);
  assert.match(chelm, /1 komunikat w ostatnich 7 dniach/);
  assert.ok(!/całego województwa/.test(chelm));
  const lublin = bezZnacznikow(renderuj({ powiaty: ['0663'], widoki }));
  assert.ok(!/Twój powiat jest wymieniony/.test(lublin));
  assert.ok(!/całego województwa/.test(lublin));
  assert.match(lublin, /Brak w naszych danych dla miasta Lublina/);
  assert.match(lublin, /Inne komunikaty z województwa: 1/);
  assert.match(lublin, /Komunikat w Twoim województwie, Twojego powiatu nie ma na liście/);
});

test('„Mój powiat”: pole wyboru ma wzorzec combobox, limit 5 blokuje dodawanie, chipy mają przyciski „Usuń” z nazwą', () => {
  const html = renderuj({ powiaty: ['1813'], widoki: [] });
  assert.match(html, /role="combobox"/);
  assert.match(html, /aria-autocomplete="list"/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /role="listbox"/);
  assert.match(html, /<label[^>]*>Dodaj powiat albo miasto na prawach powiatu<\/label>/);
  assert.match(html, /aria-label="Usuń: powiat przemyski, podkarpackie"/);
  assert.match(html, /Kopiuj link do tego zestawu/);
  assert.match(html, /zapisujemy tylko w tej przeglądarce/);
  assert.ok(!/<input[^>]*disabled/.test(html));
  const pelny = renderuj({ powiaty: ['0602', '0604', '0620', '0663', '1263'], widoki: [] });
  assert.match(pelny, /<input[^>]*disabled/);
  assert.match(pelny, /to maksimum/);
  const pusty = bezZnacznikow(renderuj({ powiaty: [], widoki: [] }));
  assert.match(pusty, /Nie wybrano jeszcze żadnego powiatu/);
});

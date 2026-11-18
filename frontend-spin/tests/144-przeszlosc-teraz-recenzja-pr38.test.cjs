// „Teraz”: poprawki po recenzji Codexa PR #38 (zlecenie Z6P2). Sprawdza na renderze strony i karty (nie tylko tekst kodu):
// P1-4 tabela w trakcie zmiany filtra, P1-5 precyzja czasu w karcie, P1-6 atrybucja, P1-2 opis miejsca przy zasięgu przybliżonym,
// P2-7 potwierdzenie warstw, P2-10 panel i inert, P2-11 filtr regionu i karta spoza filtrów, P2-12 link i pamięć, P2-13 mapa.
// node --test, bez nowych pakietów.
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

// stan zapytań podstawiany per klucz (queryKey[1]); zapamiętujemy opcje, żeby sprawdzić np. brak danych zastępczych
const zapytania = { stan: {}, warstwy: {}, wpisy: {}, 'wpisy-powiatow': {}, zdarzenia: {} };
const opcje = {};
const mocks = {
  '@tanstack/react-query': { useQuery: o => { opcje[o.queryKey[1]] = o; return zapytania[o.queryKey[1]] ?? {}; } },
  'next/dynamic': () => function MapaZastepcza() { return React.createElement('div', { 'data-mapa': '' }); },
  '../ui': { useStandalone() {} },
  './teraz.css': {},
};
const cache = new Map();
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
  new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} }, () => { throw new Error('bez sieci'); });
  return module.exports;
}

const tekst = html => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
const d = () => load(`${dir}/dane-probne/index`);
const m = () => load(`${dir}/model`);
const udane = data => ({ isSuccess: true, isPending: false, isError: false, isPlaceholderData: false, data, dataUpdatedAt: Date.now() });

function ustawDane({ wpisy, warstwy } = {}) {
  const teraz = Date.now();
  zapytania.stan = udane(d().probneStan(teraz));
  zapytania.warstwy = warstwy ?? udane(d().probneWarstwy(teraz));
  zapytania.zdarzenia = udane({ wyniki: d().probneZdarzenia(teraz), uciete: false, pominiete: 0 });
  zapytania.wpisy = wpisy ?? udane({ wpisy: d().probneWpisy(teraz), uciete: false, pominiete: 0 });
  zapytania['wpisy-powiatow'] = udane({ wpisy: d().probneWpisy(teraz), uciete: false, pominiete: 0 });
}

function strona(poczatkowy = {}, powiaty = []) {
  const { TerazPage } = load(`${dir}/TerazPage`);
  const p = { warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'tabela', probne: false, ...poczatkowy };
  return renderToStaticMarkup(React.createElement(TerazPage, { poczatkowy: p, poczatkowePowiaty: powiaty, podkladUrl: '', glifyUrl: '' }));
}

// ---------- P1-4 ----------

test('P1-4: zapytanie o wpisy bez danych zastępczych; przy zmianie okresu tabela czeka, CSV i podpis zablokowane', () => {
  ustawDane();
  const gotowa = strona();
  assert.ok(!('placeholderData' in opcje.wpisy), 'useWpisy bez keepPreviousData: stare wiersze nie udają nowego filtra');
  assert.deepEqual(opcje.wpisy.queryKey.slice(2), [false, '24h', null], 'klucz zapytania zawiera okres i region');
  assert.match(gotowa, /<table/);
  assert.match(gotowa, /<button type="button" class="tz-przycisk">Pobierz widok jako CSV \(\d+\)/);
  assert.match(gotowa, /<caption/);
  // przejście 7 dni → 1 godzina: nowy klucz bez odpowiedzi (TanStack bez placeholderData: isPending, brak danych)
  ustawDane({ wpisy: { isPending: true, isSuccess: false, isError: false, isPlaceholderData: false, data: undefined, dataUpdatedAt: 0 } });
  const przejscie = strona({ okres: '1h' });
  assert.ok(!/<table/.test(przejscie), 'bez wierszy z poprzedniego okresu');
  assert.ok(!/<caption/.test(przejscie), 'podpis tabeli z nowym filtrem dopiero po odpowiedzi');
  assert.match(przejscie, /<button[^>]*disabled[^>]*>Pobierz widok jako CSV \(0\)/);
  assert.match(tekst(przejscie), /Wczytujemy komunikaty dla filtrów: 1 godz\./);
  assert.ok(!/Brak komunikatów w wybranym czasie/.test(tekst(przejscie)), 'wczytywanie nie udaje braku');
  // nawet gdyby biblioteka oddała dane zastępcze (isPlaceholderData), tabela ich nie pokaże
  ustawDane({ wpisy: { ...udane({ wpisy: d().probneWpisy(), uciete: false, pominiete: 0 }), isPlaceholderData: true } });
  const zastepcze = strona({ okres: '1h' });
  assert.ok(!/<table/.test(zastepcze));
  assert.match(zastepcze, /<button[^>]*disabled[^>]*>Pobierz widok jako CSV/);
});

// ---------- P1-3 (render strony) ----------

test('P1-3: niepełna odpowiedź bez trafień to liczba pobranych i ograniczenie, nie „Brak komunikatów”', () => {
  ustawDane({ wpisy: udane({ wpisy: [], uciete: true, pominiete: 0 }) });
  const t = tekst(strona());
  assert.ok(!/Brak komunikatów w wybranym czasie/.test(t), t);
  assert.match(t, /Dane niepełne: pobraliśmy 0 komunikatów/);
  assert.match(t, /Dane obcięte: pobraliśmy 0 komunikatów, najnowsze/);
  ustawDane({ wpisy: udane({ wpisy: [], uciete: false, pominiete: 3 }) });
  const p = tekst(strona());
  assert.ok(!/Brak komunikatów w wybranym czasie/.test(p));
  assert.match(p, /Pominięto komunikaty o nieznanym formacie: 3/);
  ustawDane({ wpisy: udane({ wpisy: [], uciete: false, pominiete: 0 }) });
  assert.match(tekst(strona()), /Brak komunikatów w wybranym czasie i regionie/, 'kompletna pusta odpowiedź: dopiero wtedy „brak”');
});

// ---------- P2-7 ----------

test('P2-7: wpis z cache tylko dla warstw potwierdzonych w bieżącej, poprawnej odpowiedzi warstwy/', () => {
  const mod = m();
  const warstwy = d().probneWarstwy();
  const wpisy = d().probneWpisy();
  const pelne = mod.potwierdzoneWarstwy(warstwy, true);
  assert.ok(pelne.has('rcb') && !pelne.has('media'), 'wyłączona redakcyjnie nie jest potwierdzona');
  assert.equal(mod.potwierdzoneWarstwy(warstwy, false).size, 0, 'błąd ostatniego odświeżenia: brak potwierdzenia');
  assert.equal(mod.potwierdzoneWarstwy(undefined, true).size, 0);
  // walidator pominął rekord warstwy pożarów: jej wpisy i powiązania znikają, a liczba ukrytych trafia do ostrzeżenia
  const bezPozarow = mod.potwierdzoneWarstwy(warstwy.filter(w => w.warstwa !== 'pozary'), true);
  const wynik = mod.tylkoPotwierdzone(wpisy, d().probneZdarzenia(), bezPozarow, mod.kodyWylaczonych(warstwy));
  assert.ok(!wynik.wpisy.some(w => w.warstwa === 'pozary'));
  assert.ok(!wynik.zdarzenia.some(z => z.wpisy.some(w => w.warstwa === 'pozary')), 'powiązania w karcie też');
  assert.equal(wynik.ukryte, wpisy.filter(w => w.warstwa === 'pozary').length);
  // render: odświeżenie warstw nie powiodło się (dane z cache), więc wpisy są ukryte z ostrzeżeniem
  ustawDane({ warstwy: { isSuccess: false, isPending: false, isError: true, data: warstwy, dataUpdatedAt: 1 } });
  const t = tekst(strona());
  assert.match(t, /Warstwy niepotwierdzone\./);
  assert.ok(!/<table/.test(strona()), 'żaden wpis z cache bez potwierdzenia warstwy');
  assert.ok(!/Brak komunikatów w wybranym czasie/.test(t));
});

// ---------- P1-5 i P1-6: karta ----------

test('P1-5 i P1-6: karta pokazuje samą datę, „brak danych” przy nieznanym pobraniu i podpis źródła z API', () => {
  const { KartaWpisu } = load(`${dir}/KartaWpisu`);
  const v = load(`${dir}/walidacja`);
  const imgw = d().ATRYBUCJA_IMGW;
  const surowy = {
    id: 1, zrodlo: 'imgw_meteo', warstwa: 'imgw_meteo', tytul: 'Ostrzeżenie', tresc: '', link: 'https://meteo.imgw.pl/',
    opublikowano_at: '2026-11-09T23:00:00Z', dokladna_godzina_publikacji: false, pobrano_at: 'nie data', atrybucja: imgw,
    miejsce: '', klasa: 'zwykly', teryt: ['1261'], szerokosc: null, dlugosc: null, bbox: null, dokladnosc: 'powiat', pewnosc_lokalizacji: 1, zasieg: 'obszar',
  };
  const wpis = v.walidujWpis(surowy);
  assert.equal(wpis.atrybucja, imgw, 'walidator zachowuje atrybucję');
  assert.equal(wpis.pobrano_at, null, 'niepoprawny czas pobrania to brak danych, nie czas publikacji');
  assert.equal(wpis.dokladna_godzina_publikacji, false);
  assert.equal(v.walidujWpis({ ...surowy, dokladna_godzina_publikacji: undefined }).dokladna_godzina_publikacji, false, 'brak pola: bez godziny');
  const html = renderToStaticMarkup(React.createElement(KartaWpisu, { widok: { wpis, status: 'brak', zdarzenie: null }, warstwy: undefined, adres: () => 'x', onZamknij() {} }));
  const t = tekst(html);
  assert.match(t, /Opublikowano u źródła 10 listopada \(źródło podało tylko datę\)/);
  assert.ok(!/00:00/.test(t), 'bez fikcyjnej północy');
  assert.match(t, /Pobrano przez nas brak danych/);
  assert.match(t, /Podpis źródła Źródłem pochodzenia danych jest Instytut Meteorologii.*zostały przetworzone\./);
  const dokladny = renderToStaticMarkup(React.createElement(KartaWpisu, { widok: { wpis: { ...wpis, dokladna_godzina_publikacji: true, opublikowano_at: '2026-11-10T09:20:00Z', pobrano_at: '2026-11-10T09:21:00Z', atrybucja: '' }, status: 'brak', zdarzenie: null }, warstwy: undefined, adres: () => 'x', onZamknij() {} }));
  assert.match(tekst(dokladny), /10 listopada o godz\. 10:20/);
  assert.ok(!/Podpis źródła/.test(tekst(dokladny)), 'pusty podpis nie dodaje wiersza');
});

test('P1-2: opis miejsca przy zasięgu przybliżonym nie mówi „dotyczy: województwo”', () => {
  const t = load(`${dir}/teryt`);
  const alert = d().probneWpisy().find(w => w.id === 9006);
  const opis = t.opisMiejsca(alert);
  assert.ok(opis.startsWith('w obrębie: województwo lubelskie; źródło wymienia: włodawski'), opis);
  assert.ok(!opis.includes('lubelskiego'), 'nazwa województwa z listy nie jest jednostką');
  assert.ok(!/^dotyczy/.test(opis));
  assert.equal(t.opisMiejsca({ ...alert, zasieg: 'obszar' }), 'dotyczy: województwo lubelskie');
  assert.equal(t.opisMiejsca({ ...alert, miejsce: '' }), 'w obrębie: województwo lubelskie; dokładnego zasięgu źródło nie podaje');
});

// ---------- P2-10 ----------

test('P2-10: zmiana widoku zamyka panel; inert liczony z faktycznie widocznego arkusza', () => {
  const kod = read(`${dir}/TerazPage.tsx`);
  assert.match(kod, /const zmienWidok = useCallback\(\(v: Widok\) => \{ setWidok\(v\); setPanel\(false\); \}, \[\]\)/);
  for (const v of ['mapa', 'lista', 'tabela', 'powiat']) assert.match(kod, new RegExp(`onClick=\\{\\(\\) => zmienWidok\\('${v}'\\)\\}`), `przycisk ${v}`);
  assert.ok(!/onClick=\{\(\) => setWidok\(/.test(kod), 'żaden przełącznik nie omija zamknięcia panelu');
  assert.match(kod, /if \(widok === 'powiat'\) setPanel\(false\)/);
  ustawDane();
  const powiat = strona({ widok: 'powiat' }, ['1813']);
  assert.ok(!/ inert=""/.test(powiat), 'Mój powiat bez blokady sceny');
  assert.ok(!/data-panel=""/.test(powiat));
});

// ---------- P2-11 ----------

test('P2-11: filtr regionu sprawdza punkt i prostokąt jak Django; karta tylko dla widocznego wpisu', () => {
  const mod = m();
  const wpis = load(`${dir}/walidacja`).walidujWpis({
    id: 3, warstwa: 'imgw_meteo', tytul: 'T', opublikowano_at: '2026-11-18T10:00:00Z', teryt: [],
    szerokosc: 54.4, dlugosc: 18.6, bbox: [19.0, 49.2, 21.2, 50.45],
  });
  assert.equal(mod.zgodnyZRegionem(wpis, '12'), true, 'punkt w Gdańsku, ale prostokąt przecina Małopolskę');
  assert.equal(mod.zgodnyZRegionem(wpis, '22'), true, 'punkt w pomorskim');
  assert.equal(mod.zgodnyZRegionem(wpis, '32'), false);
  const kod = read(`${dir}/TerazPage.tsx`);
  assert.match(kod, /widoczne\.find\(v => v\.wpis\.id === wybranyId\)/);
  assert.match(kod, /if \(wybranyId !== null && !widoczne\.some\(v => v\.wpis\.id === wybranyId\)\) \{ setWybranyId\(null\); przywrocFokus\(\); \}/);
  // render: wpis z adresu spoza województwa nie otwiera karty
  ustawDane();
  const html = strona({ widok: 'lista', wpis: 9020, woj: '18' });
  assert.ok(!/class="tz-karta"/.test(html), 'wstrząs koło Lubina nie jest w podkarpackim');
  const wDolnoslaskim = strona({ widok: 'lista', wpis: 9020, woj: '02' });
  assert.match(wDolnoslaskim, /class="tz-karta"/);
});

// ---------- P2-12 ----------

test('P2-12: link ma pełny zakres filtrów; pusta lista warstw różni się od samych błędnych kodów', () => {
  const par = load(`${dir}/parametry`);
  assert.deepEqual({ ...par.warstwyZAdresu(undefined) }, { warstwy: null, bledne: false });
  assert.deepEqual({ ...par.warstwyZAdresu('') }, { warstwy: [], bledne: false }, 'jawnie żadna');
  assert.deepEqual({ ...par.warstwyZAdresu('wszystkie') }, { warstwy: null, bledne: false });
  assert.deepEqual({ ...par.warstwyZAdresu('xyz,abc') }, { warstwy: null, bledne: true }, 'same błędne kody: domyślne warstwy');
  assert.deepEqual([...par.warstwyZAdresu('rcb,xyz').warstwy], ['rcb']);
  assert.equal(par.parsuj({ warstwy: 'xyz' }).warstwy, null, 'nie „Żadna”');
  assert.deepEqual([...par.parsuj({ warstwy: '' }).warstwy], []);
  const pelny = par.zbudujZapytanie({ warstwy: [], okres: '24h', woj: null, wpis: 7, widok: 'mapa', probne: false }, '', true);
  assert.equal(pelny, '?warstwy=&okres=24h&woj=pl&wpis=7');
  assert.deepEqual([...par.parsuj(new URLSearchParams(pelny)).warstwy], [], 'pusta lista przechodzi przez link');
  assert.equal(par.zbudujZapytanie({ warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'mapa', probne: false }), '', 'pasek adresu bez wartości domyślnych');
  const kod = read(`${dir}/TerazPage.tsx`);
  assert.match(kod, /nieZapisujWarstw\.current = warstwyZAdresu\(q\.get\('warstwy'\) \?\? undefined\)\.bledne/);
  assert.match(kod, /zapiszPamiec\(nieZapisujWarstw\.current \? \{ okres, woj \} : \{ warstwy: wybor, okres, woj \}\)/, 'błędne kody nic nie zapisują w pamięci warstw');
});

// ---------- P2-13 ----------

test('P2-13: gotowość mapy należy do instancji, kamera czeka na jej load', () => {
  const kod = read(`${dir}/Mapa.tsx`);
  assert.match(kod, /const \[gotowa, setGotowa\] = useState\(false\)/, 'nowa instancja startuje jako niegotowa');
  assert.ok(!/gotowa: boolean;\n\s*podkladUrl/.test(kod) && !/p\.gotowa/.test(kod), 'bez dziedziczenia gotowości po poprzedniej mapie');
  assert.match(kod, /mapaGL\.on\('load', \(\) => \{ if \(anulowano\) return; setGotowa\(true\);/);
  assert.match(kod, /if \(!m \|\| !gotowa\) return;/);
  assert.match(kod, /\}, \[p\.wybrany, maPolozenie, gotowa\]\);/, 'po load efekt kamery stosuje bieżący wybór');
  assert.ok(!/gotowa=\{mapa\.gotowa\}/.test(read(`${dir}/TerazPage.tsx`)));
});

// ====================== R38b: ponowna recenzja PR #38 (zlecenie Z6P3) ======================

const powiatyMod = () => load(`${dir}/powiaty`);
const zakresWpisu = (wpis, kod) => powiatyMod().zakresDlaPowiatu(wpis, kod);
const KOD = { swidnickiLubelski: '0617', swidnickiDolnoslaski: '0219', walbrzyski: '0221', chelmski: '0603', chelm: '0662', lublin: '0663', wlodawski: '0619' };

test('R38b P1-1: jednostka liczy się tylko w województwie, pod które źródło ją podpisuje (próba recenzenta: świdnicki)', () => {
  // „woj. lubelskie: powiat świdnicki; woj. dolnośląskie: powiat wałbrzyski” w formie z parsera RCB
  const alert = { teryt: ['02', '06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\ndolnośląskiego\nlubelskie: świdnicki\ndolnośląskie: wałbrzyski' };
  assert.equal(zakresWpisu(alert, KOD.swidnickiLubelski), 'wymieniony');
  assert.equal(zakresWpisu(alert, KOD.walbrzyski), 'wymieniony');
  assert.notEqual(zakresWpisu(alert, KOD.swidnickiDolnoslaski), 'wymieniony', 'dolnośląski świdnicki nie jest na liście źródła');
  assert.equal(zakresWpisu(alert, KOD.swidnickiDolnoslaski), 'pozaLista');
  // starszy zapis bez województw przy dwóch województwach: niejednoznaczne, nigdy „wymieniony” (oba powiaty o tej nazwie)
  const starszy = { teryt: ['02', '06'], zasieg: 'przyblizony', miejsce: 'świdnicki\nwałbrzyski' };
  assert.equal(zakresWpisu(starszy, KOD.swidnickiLubelski), 'mozliwy');
  assert.equal(zakresWpisu(starszy, KOD.swidnickiDolnoslaski), 'mozliwy');
  assert.equal(zakresWpisu(starszy, KOD.walbrzyski), 'mozliwy');
  // jedno województwo: lista bez podpisów jest jednoznaczna
  assert.equal(zakresWpisu({ ...starszy, teryt: ['06'] }, KOD.swidnickiLubelski), 'wymieniony');
  // typ jednostki: gmina o nazwie miasta nie wymienia powiatu
  assert.equal(zakresWpisu({ teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskie: gmina Chełm' }, KOD.chelm), 'mozliwy');
  assert.equal(zakresWpisu({ teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskie: miasto Chełm' }, KOD.chelm), 'wymieniony');
});

test('R38b P1-1: „w powiatach chełmskim i włodawskim” bez dwukropka to lista wybranych powiatów, nie całe województwo', () => {
  const alert = { teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\nlubelskie: chełmskim\nlubelskie: włodawskim' };
  assert.equal(zakresWpisu(alert, KOD.chelmski), 'wymieniony');
  assert.equal(zakresWpisu(alert, KOD.wlodawski), 'wymieniony');
  assert.equal(zakresWpisu(alert, KOD.lublin), 'pozaLista');
  assert.equal(zakresWpisu(alert, KOD.chelm), 'mozliwy', 'miasto Chełm nie jest powiatem chełmskim');
  assert.notEqual(zakresWpisu(alert, KOD.lublin), 'wojewodztwo');
});

test('R38b P1-1: czterocyfrowy kod przy zasięgu przybliżonym nie jest potwierdzeniem bez zgodnej nazwy i województwa', () => {
  const wpis = (miejsce, zasieg = 'przyblizony') => ({ teryt: [KOD.chelm], zasieg, miejsce });
  assert.equal(zakresWpisu(wpis('', 'obszar'), KOD.chelm), 'powiat', 'zasięg ze źródła: kod wystarcza');
  assert.equal(zakresWpisu(wpis(''), KOD.chelm), 'mozliwy', 'przybliżony bez listy');
  assert.equal(zakresWpisu(wpis('lubelskie: Chełm'), KOD.chelm), 'wymieniony', 'nazwa i województwo zgodne');
  assert.equal(zakresWpisu(wpis('dolnośląskie: Chełm'), KOD.chelm), 'mozliwy', 'nazwa pod innym województwem');
  assert.equal(zakresWpisu(wpis('lubelskie: włodawski'), KOD.chelm), 'mozliwy', 'inna nazwa');
  assert.equal(zakresWpisu(wpis('lubelskie: gmina Chełm'), KOD.chelm), 'mozliwy', 'gmina to nie powiat');
});

test('R38b P1-1: opis miejsca przy kilku województwach podaje województwo przy jednostce', () => {
  const t = load(`${dir}/teryt`);
  const opis = t.opisMiejsca({ teryt: ['02', '06'], dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null, zasieg: 'przyblizony',
    miejsce: 'lubelskie: świdnicki\ndolnośląskie: wałbrzyski\ndolnośląskie: miasto Świdnica' });
  assert.match(opis, /źródło wymienia: świdnicki \(lubelskie\), wałbrzyski \(dolnośląskie\), miasto Świdnica \(dolnośląskie\)/);
  assert.deepEqual(t.rozbierzMiejsce('lubelskiego\nlubelskie: gmina Żarów\nChełm'), [
    { woj: '06', typ: 'gmina', nazwa: 'Żarów' }, { woj: null, typ: 'powiat', nazwa: 'Chełm' },
  ]);
});

test('R38b P1-2: „Mój powiat” przy awarii listy warstw i pustym wyniku pokazuje „dane niedostępne”, nie „brak”', () => {
  const warstwy503 = { isSuccess: false, isPending: false, isError: true, isPlaceholderData: false, data: undefined, dataUpdatedAt: 0 };
  const pusteWpisy = udane({ wpisy: [], uciete: false, pominiete: 0 });
  ustawDane();
  zapytania.warstwy = warstwy503;
  zapytania['wpisy-powiatow'] = pusteWpisy;
  const awaria = tekst(strona({ widok: 'powiat' }, ['1813']));
  assert.match(awaria, /Lista warstw niedostępna/);
  assert.match(awaria, /Dane niedostępne: nie mamy aktualnej listy warstw/);
  assert.ok(!/Brak w naszych danych/.test(awaria), awaria);
  // to samo przy nieudanym odświeżeniu (dane warstw z cache są, potwierdzenia nie ma)
  ustawDane();
  zapytania.warstwy = { ...warstwy503, data: d().probneWarstwy(), dataUpdatedAt: 1 };
  zapytania['wpisy-powiatow'] = pusteWpisy;
  const nieaktualne = tekst(strona({ widok: 'powiat' }, ['1813']));
  assert.match(nieaktualne, /Dane niedostępne: nie mamy aktualnej listy warstw/);
  assert.ok(!/Brak w naszych danych/.test(nieaktualne));
  // kontrola: potwierdzone warstwy i pusty, kompletny wynik to zwykły „brak”
  ustawDane();
  zapytania['wpisy-powiatow'] = pusteWpisy;
  const kompletne = tekst(strona({ widok: 'powiat' }, ['1813']));
  assert.match(kompletne, /Brak w naszych danych dla powiatu przemyskiego/);
  assert.ok(!/Dane niedostępne: nie mamy aktualnej listy warstw/.test(kompletne));
});

test('R38b P2-4: ostrzeżenie, gdy znikają same powiązania albo odświeżenie warstw zawiodło, a wpis główny nie został ukryty', () => {
  const mod = m();
  const warstwy = d().probneWarstwy();
  const zdarzenia = d().probneZdarzenia();
  assert.ok(zdarzenia.some(z => z.wpisy.some(w => w.warstwa === 'pozary')), 'próbka ma powiązanie z warstwą pożarów');
  const bezPozarow = mod.potwierdzoneWarstwy(warstwy.filter(w => w.warstwa !== 'pozary'), true);
  const wynik = mod.tylkoPotwierdzone([], zdarzenia, bezPozarow, mod.kodyWylaczonych(warstwy));
  assert.equal(wynik.ukryte, 0, 'żaden wpis główny nie został ukryty');
  assert.ok(wynik.ukrytePowiazane > 0, 'ale powiązania tak');
  // render strony: warstwa pożarów pominięta przez walidator, lista wpisów pusta
  ustawDane({ warstwy: udane(warstwy.filter(w => w.warstwa !== 'pozary')), wpisy: udane({ wpisy: [], uciete: false, pominiete: 0 }) });
  const powiazania = tekst(strona());
  assert.match(powiazania, /Warstwy niepotwierdzone\./, powiazania);
  assert.match(powiazania, new RegExp(`warstw bez potwierdzenia \\(${wynik.ukrytePowiazane}\\)`));
  // odświeżenie warstw zawiodło (dane z cache), wpisów głównych brak: ostrzeżenie o nieaktualnej liście
  ustawDane({ warstwy: { isSuccess: false, isPending: false, isError: true, data: warstwy, dataUpdatedAt: 1 }, wpisy: udane({ wpisy: [], uciete: false, pominiete: 0 }) });
  zapytania.zdarzenia = udane({ wyniki: [], uciete: false, pominiete: 0 });
  const zawiodlo = tekst(strona());
  assert.match(zawiodlo, /Lista warstw nieaktualna\./, zawiodlo);
  assert.ok(!/Brak komunikatów w wybranym czasie/.test(zawiodlo));
  // z powiązaniami w cache te same warunki dają ostrzeżenie o ukrytych komunikatach (też nie po cichu)
  ustawDane({ warstwy: { isSuccess: false, isPending: false, isError: true, data: warstwy, dataUpdatedAt: 1 }, wpisy: udane({ wpisy: [], uciete: false, pominiete: 0 }) });
  assert.match(tekst(strona()), /Warstwy niepotwierdzone\./);
  // kontrola: wszystko potwierdzone, bez ostrzeżeń o warstwach
  ustawDane({ wpisy: udane({ wpisy: [], uciete: false, pominiete: 0 }) });
  const dobrze = tekst(strona());
  assert.ok(!/Warstwy niepotwierdzone|Lista warstw nieaktualna|Lista warstw niedostępna/.test(dobrze));
});

test('R38b P2-5: awaryjna ścieżka kopiowania pokazuje pełny adres zestawu z okresem, nie odsyła do paska adresu', () => {
  const p = powiatyMod();
  const adres = p.adresZestawu('https://przeszlosc.today', '/przeszlosc/teraz', ['1813', '0662'], '24h', false);
  assert.match(adres, /widok=powiat/);
  assert.match(adres, /powiaty=1813%2C0662/);
  assert.match(adres, /okres=24h/, 'okres domyślny też jest jawny: odbiorca z zapisaną 1 godziną dostaje 24 godziny');
  const { PoleAdresuRecznego } = load(`${dir}/MojPowiat`);
  const html = renderToStaticMarkup(React.createElement(PoleAdresuRecznego, { adres }));
  assert.ok(html.includes('readOnly=""') || html.includes('readonly=""'), 'pole tylko do odczytu, do zaznaczenia');
  assert.ok(html.includes(adres.replace(/&/g, '&amp;')), 'pełny adres w polu');
  const zrodlo = read(`${dir}/MojPowiat.tsx`);
  assert.ok(!/z paska przeglądarki/.test(zrodlo), 'brak odesłania do paska adresu (nie zawiera okresu domyślnego)');
  assert.match(zrodlo, /setAdresReczny\(ok \? null : adres\)/, 'adres z chwili kliknięcia trafia do pola po nieudanym kopiowaniu');
  // adres z linku wygrywa z zapisaną preferencją odbiorcy: parametr okres jest w adresie, więc pamięć go nie nadpisuje
  assert.match(read(`${dir}/TerazPage.tsx`), /if \(!q\.has\('okres'\) && p\.okres\) setOkres\(p\.okres\)/);
  assert.equal(load(`${dir}/parametry`).parsuj(new URLSearchParams(adres.split('?')[1])).okres, '24h');
});

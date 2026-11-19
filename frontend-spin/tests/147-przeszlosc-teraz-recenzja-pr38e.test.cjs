// „Teraz”: poprawki po zamykającej recenzji PR #38 (R38d, zlecenie Z6P6).
// Zasady: (1) zasięg alertu jest zapisany osobno dla każdego województwa (`zakres: lubelskie: lista|czesc|cale`) i powiat
// dopasowujemy do zakresu swojego województwa; (2) fail-closed: „nie ma na liście” tylko przy kompletnej liście tego województwa,
// „wymieniony” tylko przy zgodnej nazwie, TYPIE jednostki i województwie; (3) zdanie bez czasownika odbiorców nie zmienia zasięgu.
// `miejsce` przypadków pochodzi z parsera (147-przeszlosc-teraz-zasieg-rcb.json); backend/teraz/tests/test_zasieg_rcb_r38e.py pilnuje,
// żeby plik zgadzał się z tym, co zwraca parser. node --test, bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

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
  const req = name => (name.startsWith('.')
    ? load(path.relative(root, path.resolve(path.dirname(abs), name)).split(path.sep).join('/'))
    : require(name));
  new Function('module', 'exports', 'require', 'process', source)(module, module.exports, req, { env: {} });
  return module.exports;
}

const powiatyMod = () => load(`${dir}/powiaty`);
const teryt = () => load(`${dir}/teryt`);
const slownik = () => load(`${dir}/slownik`);
const przypadki = load('tests/147-przeszlosc-teraz-zasieg-rcb.json').przypadki;
/** Wpis w formie, jaką zwraca API dla wpisu `indeks` przypadku `id` (miejsce, kody i zasięg z parsera). */
const wpis = (id, indeks = 0) => {
  const w = przypadki[id].wpisy[indeks];
  return { teryt: w.teryt, zasieg: w.zasieg, miejsce: w.miejsce };
};
const zakres = (w, k) => powiatyMod().zakresDlaPowiatu(w, k);
const kod = (woj, nazwa) => {
  const p = slownik().POWIATY.find(x => x.woj === woj && x.nazwa === nazwa);
  assert.ok(p, `brak ${nazwa} w województwie ${woj}`);
  return p.kod;
};
const kodyWoj = woj => slownik().POWIATY.filter(p => p.woj === woj).map(p => p.kod);

test('fixture z parsera ma wszystkie przypadki rundy', () => {
  for (const id of ['miasto-puck', 'czesc-lubelskiego', 'powiat-swidnicki-dolnoslaskie', 'trzy-zasiegi', 'poludnie-mazowieckie',
    'cale-i-punkt-pomocy', 'wylaczenie-w-osobnym-zdaniu', 'wylaczenie-i-drugie-wojewodztwo', 'odsylacz-w-nawiasie',
    'element-nieczytelny', 'zmiana-zasiegu-w-aktualizacji']) {
    assert.ok(przypadki[id], id);
  }
});

test('Z6P6 pkt 1: „…odbiorców w mieście Puck w woj. pomorskim” nie daje powiatowi puckiemu „wymieniony”', () => {
  const w = wpis('miasto-puck');
  const puck = teryt().rozbierzMiejsce(w.miejsce).find(j => j.nazwa === 'Puck');
  assert.deepEqual({ typ: puck.typ, woj: puck.woj }, { typ: 'miasto', woj: '22' }, 'miasto Puck w danych jako miasto');
  assert.equal(zakres(w, kod('22', 'pucki')), 'mozliwy');
  assert.equal(zakres(w, kod('22', 'wejherowski')), 'mozliwy', 'miasto na liście: lista otwarta, nie wolno powiedzieć „nie ma na liście” (Z6P7a)');
  assert.match(powiatyMod().zakresTekstem('mozliwy', kod('22', 'pucki')), /możliwe, że dotyczy Twojego powiatu: sprawdź treść komunikatu/);
});

test('Z6P6 pkt 1: typ jednostki rozstrzyga o dopasowaniu po rdzeniu nazwy', () => {
  const lista = (jednostka, extra = '') => ({ teryt: ['12'], zasieg: 'przyblizony', miejsce: `małopolskie\n${jednostka}\nzakres: małopolskie: lista${extra}` });
  assert.equal(zakres(lista('małopolskie: miasto Kraków'), kod('12', 'Kraków')), 'wymieniony');
  assert.equal(zakres(lista('małopolskie: miasto Kraków'), kod('12', 'krakowski')), 'mozliwy', 'powiat ziemski o nazwie miasta: najwyżej możliwe');
  assert.equal(zakres(lista('małopolskie: krakowski'), kod('12', 'krakowski')), 'wymieniony');
  assert.equal(zakres(lista('małopolskie: gmina Kraków'), kod('12', 'Kraków')), 'mozliwy', 'gmina nie jest powiatem');
  assert.equal(zakres(lista('małopolskie: Kraków'), kod('12', 'Kraków')), 'wymieniony', 'bez przedrostka typu: powiat albo miasto ze słownika');
});

test('Z6P6 pkt 2: „w części woj. lubelskiego” nigdy nie daje „całe”', () => {
  const w = wpis('czesc-lubelskiego');
  assert.equal(w.zasieg, 'przyblizony');
  for (const k of kodyWoj('06')) assert.equal(zakres(w, k), 'mozliwy', k);
  assert.match(teryt().opisMiejsca({ ...w, dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null }), /część: województwo lubelskie/);
});

test('Z6P6 pkt 2: „w powiecie świdnickim w woj. dolnośląskim” nie daje całego województwa', () => {
  const w = wpis('powiat-swidnicki-dolnoslaskie');
  assert.equal(zakres(w, kod('02', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(w, kod('02', 'Wrocław')), 'pozaLista');
  assert.notEqual(zakres(w, kod('02', 'Wrocław')), 'wojewodztwo');
});

test('Z6P6 pkt 2: całe + część + powiat z innego województwa w jednym zdaniu: każdy powiat według zakresu swojego województwa', () => {
  // „…w całym woj. lubelskim, w części woj. podkarpackiego i w powiecie świdnickim w woj. dolnośląskim.”
  const w = wpis('trzy-zasiegi');
  assert.deepEqual(w.teryt, ['02', '06', '18']);
  for (const k of kodyWoj('06')) assert.equal(zakres(w, k), 'wojewodztwo', `lubelskie ${k}`);
  assert.equal(zakres(w, kod('18', 'Rzeszów')), 'mozliwy', 'Rzeszów: część województwa, nie „nie ma na liście”');
  for (const k of kodyWoj('18')) assert.equal(zakres(w, k), 'mozliwy', `podkarpackie ${k}`);
  assert.equal(zakres(w, kod('02', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(w, kod('02', 'Wrocław')), 'pozaLista');
});

test('Z6P6 pkt 2: „wyłącznie na południu woj. mazowieckiego” to część, nie całe', () => {
  const w = wpis('poludnie-mazowieckie');
  assert.equal(w.zasieg, 'przyblizony');
  for (const k of kodyWoj('14')) assert.equal(zakres(w, k), 'mozliwy', k);
});

test('Z6P6 pkt 3: punkt pomocy w mieście nie zawęża zasięgu alertu „w całym woj. lubelskim”', () => {
  const w = wpis('cale-i-punkt-pomocy');
  assert.equal(w.zasieg, 'obszar');
  for (const k of kodyWoj('06')) assert.equal(zakres(w, k), 'wojewodztwo', k);
  assert.equal(zakres(w, kod('06', 'Lublin')), 'wojewodztwo');
});

test('Z6P6 pkt 4: „Komunikat nie obowiązuje w powiecie puckim” po alercie dla pomorskiego wyłącza powiat pucki', () => {
  const w = wpis('wylaczenie-w-osobnym-zdaniu');
  assert.equal(zakres(w, kod('22', 'pucki')), 'wylaczony');
  assert.notEqual(zakres(w, kod('22', 'pucki')), 'wymieniony');
  for (const k of kodyWoj('22')) {
    if (k !== kod('22', 'pucki')) assert.equal(zakres(w, k), 'mozliwy', `pozostałe powiaty: najwyżej możliwe (${k})`);
  }
});

test('Z6P6 pkt 4: wyłączenie nie ucina drugiego województwa („…z wyjątkiem powiatu puckiego, a także w woj. zachodniopomorskim”)', () => {
  const w = wpis('wylaczenie-i-drugie-wojewodztwo');
  assert.deepEqual(w.teryt, ['22', '32'], 'kod 32 zachowany');
  assert.equal(zakres(w, kod('32', 'Szczecin')), 'wojewodztwo');
  assert.equal(zakres(w, kod('22', 'pucki')), 'wylaczony');
  assert.equal(zakres(w, kod('22', 'wejherowski')), 'mozliwy');
});

test('Z6P6 pkt 5: odsyłacz „(1)” przy nazwie nie gubi powiatu włodawskiego', () => {
  const w = wpis('odsylacz-w-nawiasie');
  assert.equal(zakres(w, kod('06', 'włodawski')), 'wymieniony');
  assert.equal(zakres(w, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(w, kod('06', 'Lublin')), 'pozaLista');
});

test('Z6P6 pkt 5: element, którego parser nie umiał odczytać, daje „możliwe”, nigdy „nie ma na liście”', () => {
  const w = wpis('element-nieczytelny');
  assert.equal(zakres(w, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(w, kod('06', 'włodawski')), 'mozliwy');
  for (const k of kodyWoj('06')) assert.notEqual(zakres(w, k), 'pozaLista', k);
});

test('Z6P6 pkt 6: aktualizacja ze zmianą zasięgu nie dziedziczy wypadłego powiatu świdnickiego', () => {
  const pierwotny = wpis('zmiana-zasiegu-w-aktualizacji', 0);
  const aktualizacja = wpis('zmiana-zasiegu-w-aktualizacji', 1);
  assert.equal(zakres(pierwotny, kod('02', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(aktualizacja, kod('02', 'świdnicki')), null, 'karta aktualizacji nie dotyczy już tego powiatu');
  assert.equal(zakres(aktualizacja, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(aktualizacja, kod('06', 'Lublin')), 'pozaLista');
});

test('zakresyWojewodztw: kilka różnych linii dla jednego województwa daje „część”, brak linii daje pustą mapę', () => {
  const { zakresyWojewodztw } = teryt();
  assert.deepEqual([...zakresyWojewodztw('lubelskiego\nzakres: lubelskie: cale\nzakres: podlaskie: lista')], [['06', 'cale'], ['20', 'lista']]);
  assert.deepEqual([...zakresyWojewodztw('zakres: lubelskie: cale\nzakres: lubelskie: lista')], [['06', 'czesc']]);
  assert.equal(zakresyWojewodztw('lubelskiego\nlubelskie: chełmski').size, 0);
  assert.equal(zakresyWojewodztw(undefined).size, 0);
  assert.equal(zakresyWojewodztw('zakres: nieznane: cale').size, 0);
});

test('linie zakresu i znaczniki nie są jednostkami ani nazwami województw', () => {
  const { rozbierzMiejsce, jednostkiZMiejsca } = teryt();
  const miejsce = 'lubelskie\nlubelskie: chełmski\nzakres: lubelskie: lista\nnieustalone: lubelskie\nwyłączone: lubelskie: Lublin';
  assert.deepEqual(rozbierzMiejsce(miejsce).map(j => j.nazwa), ['chełmski']);
  assert.deepEqual(jednostkiZMiejsca(miejsce), ['chełmski']);
});

test('fail-closed: „nieustalone” dotyczy swojego województwa, bez nazwy województwa wszystkich', () => {
  const lista = extra => ({
    teryt: ['06', '18'], zasieg: 'przyblizony',
    miejsce: `lubelskie\npodkarpackie\nlubelskie: chełmski\npodkarpackie: Rzeszów\nzakres: lubelskie: lista\nzakres: podkarpackie: lista${extra}`,
  });
  const wLubelskim = lista('\nnieustalone: lubelskie');
  assert.equal(zakres(wLubelskim, kod('06', 'Lublin')), 'mozliwy', 'lista lubelskiego niepełna');
  assert.equal(zakres(wLubelskim, kod('18', 'przemyski')), 'pozaLista', 'lista podkarpackiego kompletna');
  assert.equal(zakres(wLubelskim, kod('18', 'Rzeszów')), 'wymieniony');
  const globalne = lista('\nnieustalone: nazwy jednostek');
  assert.equal(zakres(globalne, kod('06', 'Lublin')), 'mozliwy');
  assert.equal(zakres(globalne, kod('18', 'przemyski')), 'mozliwy');
});

test('fail-closed: „cale” z wyłączeniem w tym województwie nie jest „całe”, wyłączenie w innym nie przeszkadza', () => {
  const w = {
    teryt: ['14', '22'], zasieg: 'przyblizony',
    miejsce: 'mazowieckie\npomorskie\nzakres: mazowieckie: cale\nzakres: pomorskie: cale\nwyłączone: pomorskie: pucki',
  };
  assert.equal(zakres(w, kod('14', 'Warszawa')), 'wojewodztwo');
  assert.equal(zakres(w, kod('22', 'Gdańsk')), 'mozliwy');
  assert.equal(zakres(w, kod('22', 'pucki')), 'wylaczony');
});

test('wpisy starsze niż parser v6 (bez linii zakresu) zachowują dawną heurystykę', () => {
  const stary = { teryt: ['06', '02'], zasieg: 'przyblizony', miejsce: 'lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim' };
  assert.equal(zakres(stary, kod('06', 'Lublin')), 'wojewodztwo', 'R38c: województwo bez jednostek obok jednostek z innego');
  assert.equal(zakres(stary, kod('02', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(stary, kod('02', 'Wrocław')), 'pozaLista');
});

// Z6P7a: „nie ma na liście” tylko dla zamkniętej listy powiatów ziemskich (R38e, bloker 1 i 2).
const bezPojedynczego = (miejsce, rodzaj, woj = '06') => ({ teryt: [woj], zasieg: 'przyblizony', miejsce: `${miejsce}
zakres: lubelskie: ${rodzaj}` });
test('Z6P7a: lista powiatów ziemskich zostaje zamknięta: „nie ma na liście” dla powiatu spoza listy', () => {
  const w = bezPojedynczego('lubelskie
lubelskie: chełmski
lubelskie: włodawski', 'lista');
  assert.equal(zakres(w, kod('06', 'bialski')), 'pozaLista');
  assert.equal(zakres(w, kod('06', 'chełmski')), 'wymieniony');
});
test('Z6P7a: lista z miastem albo gminą jest otwarta: „możliwe” zamiast „nie ma na liście”', () => {
  for (const jednostka of ['miasto Rumia', 'gmina Żarów']) {
    const w = bezPojedynczego(`lubelskie
lubelskie: ${jednostka}`, 'lista');
    assert.equal(zakres(w, kod('06', 'bialski')), 'mozliwy', jednostka);
  }
});
test('Z6P7a: lista_otwarta z parsera nigdy nie daje „nie ma na liście” ani „całe województwo”', () => {
  const w = bezPojedynczego('lubelskie
lubelskie: chełmski', 'lista_otwarta');
  assert.equal(zakres(w, kod('06', 'bialski')), 'mozliwy');
  assert.equal(zakres(w, kod('06', 'chełmski')), 'wymieniony');
});

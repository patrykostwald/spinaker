// „Teraz”: poprawki po czwartej recenzji PR #38 (zlecenie Z6P5, recenzja Z6R5).
// Zasada strukturalna: parser RCB jest zachowawczy. Wyłączenie, zalecenie albo niejasni odbiorcy nie dopisują jednostek,
// a front daje wtedy najwyżej „możliwe” (nigdy „wymieniony” ani „nie ma na liście” dla jednostek wyłączonych lub nieznanych).
// Parser sprawdza backend/teraz/tests/test_zasieg_rcb_r38d.py; tu `miejsce` jest w formie, jaką on zwraca dla zdań z recenzji
// (zdanie przy każdym przypadku). node --test, bez nowych pakietów.
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
const zakres = (wpis, kod) => powiatyMod().zakresDlaPowiatu(wpis, kod);
/** Kod TERYT powiatu o nazwie `nazwa` w województwie `woj` (ze słownika, nie z pamięci). */
const kod = (woj, nazwa) => {
  const p = slownik().POWIATY.find(x => x.woj === woj && x.nazwa === nazwa);
  assert.ok(p, `brak ${nazwa} w województwie ${woj}`);
  return p.kod;
};
const wpis = (teryty, miejsce, zasieg = 'przyblizony') => ({ teryt: teryty, zasieg, miejsce });
const wszystkieKodyWoj = woj => slownik().POWIATY.filter(p => p.woj === woj).map(p => p.kod);
const NIE_POWIEDZIEC = ['wymieniony', 'pozaLista', 'bezListy', 'wojewodztwo'];

test('R38d P1-1: „z wyłączeniem powiatu białostockiego”: wyłączony nie jest „wymieniony”, reszta najwyżej „możliwe”', () => {
  // „…na terenie województwa podlaskiego z wyłączeniem powiatu białostockiego.”
  const w = wpis(['20'], 'podlaskiego\nwyłączone: podlaskie: białostockiego');
  assert.equal(zakres(w, kod('20', 'białostocki')), 'mozliwy');
  assert.equal(zakres(w, kod('20', 'Białystok')), 'mozliwy', 'miasto o tej samej nazwie co powiat: nie wiadomo, czy wyłączone');
  for (const k of wszystkieKodyWoj('20')) {
    if (k === kod('20', 'białostocki')) continue;
    assert.ok(['mozliwy'].includes(zakres(w, k)), `${k}: ${zakres(w, k)}`);
  }
});

test('R38d P1-1: „z wyjątkiem miasta Lublin” i „z wyłączeniem powiatów: chełmskiego i włodawskiego”', () => {
  const lublin = wpis(['06'], 'lubelskiego\nwyłączone: lubelskie: miasto Lublin');
  assert.equal(zakres(lublin, kod('06', 'Lublin')), 'mozliwy');
  assert.equal(zakres(lublin, kod('06', 'Chełm')), 'mozliwy');
  assert.equal(zakres(lublin, kod('06', 'lubelski')), 'mozliwy', 'powiat lubelski to nie miasto Lublin, ale „możliwe”, nie „wyłączony”');
  const dwa = wpis(['06'], 'lubelskiego\nwyłączone: lubelskie: chełmskiego\nwyłączone: lubelskie: włodawskiego');
  assert.equal(zakres(dwa, kod('06', 'chełmski')), 'mozliwy');
  assert.equal(zakres(dwa, kod('06', 'włodawski')), 'mozliwy');
  assert.equal(zakres(dwa, kod('06', 'Chełm')), 'mozliwy');
  assert.equal(zakres(dwa, kod('06', 'świdnicki')), 'mozliwy');
  for (const w of [lublin, dwa]) {
    for (const k of wszystkieKodyWoj('06')) {
      const z = zakres(w, k);
      assert.ok(!NIE_POWIEDZIEC.includes(z), `${k}: ${z}`);
    }
  }
});

test('R38d P1-1: wyłączenie ogólne i niepełna lista cofają „nie ma na liście”; wyłączone nie dopisują województwa', () => {
  const ogolne = wpis(['06'], 'lubelskiego\nwyłączone: nieokreślone');
  for (const k of wszystkieKodyWoj('06')) assert.equal(zakres(ogolne, k), 'mozliwy');
  // lista z nierozpoznanym elementem: „wymieniony” zostaje, „nie ma na liście” zamienia się w „możliwe”
  const niepelna = wpis(['06'], 'lubelskiego\nlubelskie: chełmski\nnieustalone: nazwy jednostek');
  assert.equal(zakres(niepelna, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(niepelna, kod('06', 'Lublin')), 'mozliwy');
  // wyłączenie obok wymienionego powiatu: wymieniony schodzi do „możliwe”
  const oba = wpis(['06'], 'lubelskiego\nlubelskie: chełmski\nwyłączone: lubelskie: gmina Żarów');
  assert.equal(zakres(oba, kod('06', 'chełmski')), 'mozliwy');
  assert.equal(zakres(oba, kod('06', 'Lublin')), 'mozliwy');
  // wyłączenie z innego województwa nie zastrzega tego
  const inne = wpis(['06'], 'lubelskiego\nlubelskie: chełmski\nwyłączone: dolnośląskie: miasto Świdnica');
  assert.equal(zakres(inne, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(inne, kod('06', 'Lublin')), 'mozliwy');
  // bez znaczników nic się nie zmienia (R38c)
  const czysta = wpis(['06'], 'lubelskiego\nlubelskie: chełmski');
  assert.equal(zakres(czysta, kod('06', 'chełmski')), 'wymieniony');
  assert.equal(zakres(czysta, kod('06', 'Lublin')), 'mozliwy');
});

test('R38d P1-1: wyłączenie cofa „całe województwo” (także przy zasięgu „obszar” i przy powiecie z innego województwa)', () => {
  const t = teryt();
  const miejsce = 'lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim\nwyłączone: lubelskie: miasto Lublin';
  assert.equal(t.calyRegionZMiejsca(miejsce, '06'), false);
  assert.equal(t.calyRegionZMiejsca('lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim', '06'), true, 'kontrola: bez wyłączenia całe');
  assert.equal(zakres(wpis(['02', '06'], miejsce), kod('06', 'Lublin')), 'mozliwy');
  assert.equal(zakres(wpis(['02', '06'], miejsce), kod('06', 'Chełm')), 'mozliwy');
  assert.equal(zakres(wpis(['06'], 'lubelskiego\nwyłączone: lubelskie: miasto Lublin', 'obszar'), kod('06', 'Chełm')), 'mozliwy');
  assert.equal(zakres(wpis(['06'], 'lubelskiego', 'obszar'), kod('06', 'Chełm')), 'wojewodztwo', 'kontrola: obszar bez znaczników');
});

test('R38d P1-1: znaczniki nie są jednostkami objętymi alertem (rozbierzMiejsce) i są w opisie karty', () => {
  const t = teryt();
  const miejsce = 'podlaskiego\nwyłączone: podlaskie: białostockiego\nwyłączone: nieokreślone\nnieustalone: nazwy jednostek';
  assert.deepEqual(t.rozbierzMiejsce(miejsce), []);
  assert.deepEqual(t.jednostkiZMiejsca(miejsce), []);
  const z = t.znacznikiMiejsca(miejsce);
  assert.deepEqual(z.wylaczone, [{ woj: '20', typ: 'powiat', nazwa: 'białostockiego' }]);
  assert.equal(z.ogolne, true);
  assert.equal(z.nieustalone, true);
  const opis = t.opisMiejsca({ teryt: ['20'], dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null, zasieg: 'przyblizony', miejsce });
  assert.match(opis, /^w obrębie: województwo podlaskie; dokładnego zasięgu źródło nie podaje; komunikat zawiera wyłączenia: sprawdź jego treść/);
  assert.doesNotMatch(opis, /białostockiego/, 'Z6P8: wyłączonych jednostek nie wymieniamy z nazwy');
  assert.match(opis, /komunikat zawiera wyłączenia: sprawdź jego treść; lista jednostek może być niepełna$/);
  // bez znaczników opis jak dotąd
  assert.equal(t.opisMiejsca({ teryt: ['20'], dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null, zasieg: 'przyblizony', miejsce: 'podlaskiego\npodlaskie: Białystok' }),
    'w obrębie: województwo podlaskie; źródło wymienia: Białystok');
});

test('R38d: etykieta „wyłączony” i miejsce na liście powiatu', () => {
  const p = powiatyMod();
  // Z6P8: nie ma etykiety „komunikat wyłącza Twój powiat”: nigdy nie twierdzimy, że powiat nie jest objęty
  assert.ok(!p.ZAKRESY_POWIATU.has('wylaczony'));
  assert.doesNotMatch(p.zakresTekstem('mozliwy', '0661'), /wyłącza|nie ma na liście|nie dotyczy/);
  // „wylaczony” przegrywa z „możliwe”, gdy ten sam wpis ma kilka kodów
  const wielokod = wpis(['06', '0663'], 'lubelskiego\nwyłączone: lubelskie: miasto Lublin');
  assert.equal(zakres(wielokod, '0663'), 'mozliwy', 'kod powiatu przy zasięgu przybliżonym też rozstrzyga lista');
});

test('R38d P1-2: drugie województwo w miejscowniku: oba całe', () => {
  // „w woj. lubelskim i podkarpackim” → miejsce „lubelskie\npodkarpackie”, teryt 06 i 18, zasięg obszar
  const w = wpis(['06', '18'], 'lubelskie\npodkarpackie', 'obszar');
  assert.equal(zakres(w, kod('06', 'Chełm')), 'wojewodztwo');
  assert.equal(zakres(w, kod('18', 'Przemyśl')), 'wojewodztwo');
  assert.equal(teryt().opisMiejsca({ ...w, dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null }), 'dotyczy: województwo lubelskie, województwo podkarpackie');
  // „w woj. pomorskim i zachodniopomorskim oraz w powiecie świdnickim w woj. lubelskim”
  const mieszane = wpis(['06', '22', '32'], 'pomorskie\nzachodniopomorskie\nlubelskie\nlubelskie: świdnickim');
  assert.equal(zakres(mieszane, kod('06', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(mieszane, kod('06', 'Chełm')), 'mozliwy');
});

test('R38d P1-3: zalecenie nie zawęża i nie dopisuje: całe lubelskie, Chełm „całe województwo”', () => {
  // „…w woj. lubelskim. Dla mieszkańców miasta Chełm zalecamy pozostanie w domach.” → miejsce „lubelskie”, pewność 1, obszar
  const w = wpis(['06'], 'lubelskie', 'obszar');
  assert.equal(zakres(w, kod('06', 'Chełm')), 'wojewodztwo');
  assert.equal(powiatyMod().zakresTekstem('wojewodztwo', kod('06', 'Chełm')), 'dotyczy całego województwa lubelskiego');
  assert.equal(teryt().opisMiejsca({ ...w, dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null }), 'dotyczy: województwo lubelskie');
  // „W powiecie chełmskim zalecamy pozostanie w domach.” samo: brak jednostek i brak kodu (backend: miejsce puste), nie „chełmskim zalecamy…”
  assert.deepEqual(teryt().jednostkiZMiejsca(''), []);
});

test('R38d P2: województwo w nawiasie po liście i „woj. X (powiat Y)”', () => {
  // „powiatach: bielski, cieszyński, żywiecki (woj. śląskie)”
  const slask = wpis(['24'], 'śląskie\nśląskie: bielski\nśląskie: cieszyński\nśląskie: żywiecki');
  assert.equal(zakres(slask, kod('24', 'żywiecki')), 'wymieniony');
  assert.equal(zakres(slask, kod('24', 'bielski')), 'wymieniony');
  assert.equal(zakres(slask, kod('24', 'cieszyński')), 'wymieniony');
  assert.equal(zakres(slask, kod('24', 'pszczyński')), 'mozliwy');
  // „woj. lubelskim (powiat świdnicki) oraz woj. lubelskim (powiat włodawski)”
  const lubelskie = wpis(['06'], 'lubelskie\nlubelskie: świdnicki\nlubelskie: włodawski');
  assert.equal(zakres(lubelskie, kod('06', 'świdnicki')), 'wymieniony');
  assert.equal(zakres(lubelskie, kod('06', 'włodawski')), 'wymieniony');
});

test('R38d P3: „w mieście Kraków” rozpoznane, nazwy bez „LUBELSKie”', () => {
  const krakow = wpis(['12'], 'małopolskie\nmałopolskie: miasto Kraków');
  assert.equal(zakres(krakow, kod('12', 'Kraków')), 'wymieniony');
  assert.equal(zakres(krakow, kod('12', 'Tarnów')), 'mozliwy');
  // zdanie wielkimi literami: backend zapisuje „lubelskiego”, „lubelskie: Chełm”, „lubelskie: włodawski”
  const wielkie = wpis(['06'], 'lubelskiego\nlubelskie: Chełm\nlubelskie: włodawski');
  assert.equal(zakres(wielkie, kod('06', 'Chełm')), 'wymieniony');
  assert.equal(zakres(wielkie, kod('06', 'włodawski')), 'wymieniony');
  assert.equal(zakres(wielkie, kod('06', 'Lublin')), 'mozliwy');
  assert.ok(!/[A-ZŁŚŻŹĆŃÓĘĄ]{3}/.test(teryt().jednostkiZMiejsca('lubelskiego\nlubelskie: Chełm').join(' ')));
});

test('R38d: wszystkie dopasowania ze znacznikami nie dają „wymieniony” ani „nie ma na liście” dla jednostek wyłączonych lub nieznanych', () => {
  const miejsca = [
    'lubelskiego\nwyłączone: lubelskie: miasto Lublin',
    'lubelskiego\nwyłączone: lubelskie: chełmskiego',
    'lubelskiego\nwyłączone: nieokreślone',
    'lubelskiego\nlubelskie: Chełm\nwyłączone: lubelskie: gmina Żarów',
    'lubelskiego\nlubelskie: Chełm\nnieustalone: nazwy jednostek',
  ];
  for (const miejsce of miejsca) {
    const w = wpis(['06'], miejsce);
    for (const k of wszystkieKodyWoj('06')) {
      const z = zakres(w, k);
      const wylaczona = teryt().znacznikiMiejsca(miejsce).wylaczone.length > 0 || miejsce.includes('nieokreślone');
      if (wylaczona) assert.ok(['mozliwy', 'wylaczony'].includes(z), `${miejsce.replace(/\n/g, ' | ')} → ${k}: ${z}`);
      else assert.ok(['mozliwy', 'wymieniony'].includes(z), `${miejsce.replace(/\n/g, ' | ')} → ${k}: ${z}`);
    }
  }
});

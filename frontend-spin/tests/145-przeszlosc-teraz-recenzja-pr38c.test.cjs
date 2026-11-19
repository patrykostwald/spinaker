// „Teraz”: poprawki po trzeciej recenzji Codexa PR #38 (zlecenie Z6P4, R38c).
// P1 zasięg alertu RCB w „Moim powiecie” (obie strony: parser zapisuje miejsce, front je czyta), P2 licznik ukrytych komunikatów.
// Parser i serializer sprawdza backend/teraz/tests/test_zasieg_rcb.py; tu `miejsce` jest w formie, jaką on zwraca.
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

const zapytania = { stan: {}, warstwy: {}, wpisy: {}, 'wpisy-powiatow': {}, zdarzenia: {} };
const mocks = {
  '@tanstack/react-query': { useQuery: o => zapytania[o.queryKey[1]] ?? {} },
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
const powiatyMod = () => load(`${dir}/powiaty`);
const zakresWpisu = (wpis, kod) => powiatyMod().zakresDlaPowiatu(wpis, kod);
const KOD = { swidnickiLubelski: '0617', swidnickiDolnoslaski: '0219', walbrzyski: '0221', chelmski: '0603', chelm: '0662', lublin: '0663', wlodawski: '0619' };

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

test('R38c P1: trzy zdania recenzenta w „Moim powiecie” (miejsce w formie z parsera RCB)', () => {
  // 1) „w powiecie włodawskim w woj. lubelskim oraz w powiecie świdnickim w woj. dolnośląskim”
  const dwaPowiaty = { teryt: ['02', '06'], zasieg: 'przyblizony', miejsce: 'lubelskie\ndolnośląskie\nlubelskie: włodawskim\ndolnośląskie: świdnickim' };
  assert.equal(zakresWpisu(dwaPowiaty, KOD.swidnickiDolnoslaski), 'wymieniony', 'dolnośląski świdnicki jest na liście');
  assert.equal(zakresWpisu(dwaPowiaty, KOD.swidnickiLubelski), 'mozliwy', 'lubelski świdnicki nie dostaje „Twój powiat jest wymieniony”');
  assert.equal(zakresWpisu(dwaPowiaty, KOD.wlodawski), 'wymieniony');
  // 2) „… w powiecie włodawskim w woj. lubelskim. Omijaj miasto Chełm.”: Chełm nie wchodzi do zasięgu
  const zalecenie = { teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskie\nlubelskie: włodawskim' };
  assert.equal(zakresWpisu(zalecenie, KOD.wlodawski), 'wymieniony');
  assert.equal(zakresWpisu(zalecenie, KOD.chelm), 'mozliwy');
  assert.equal(zakresWpisu(zalecenie, KOD.chelmski), 'mozliwy');
  // 3) całe lubelskie i jeden powiat dolnośląski: oba zasięgi osobno, Lublin zostaje
  const caleIPowiat = { teryt: ['02', '06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim' };
  assert.equal(zakresWpisu(caleIPowiat, KOD.lublin), 'wojewodztwo', 'Lublin w całym województwie');
  assert.equal(zakresWpisu(caleIPowiat, KOD.chelm), 'wojewodztwo');
  assert.equal(zakresWpisu(caleIPowiat, KOD.swidnickiLubelski), 'wojewodztwo', 'lubelski świdnicki należy do całego lubelskiego');
  assert.equal(zakresWpisu(caleIPowiat, KOD.swidnickiDolnoslaski), 'wymieniony');
  assert.equal(zakresWpisu(caleIPowiat, KOD.walbrzyski), 'mozliwy', 'dolnośląski powiat spoza listy');
});

test('R38c P1: całe województwo tylko przy dowodzie w miejsce; reszta zostaje przybliżona (Chełm tak, Lublin nie)', () => {
  const t = load(`${dir}/teryt`);
  // próbka RCB z 10.11: lista powiatów lubelskich, bez Lublina
  const listopad10 = { teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\nlubelskie: włodawski\nlubelskie: Chełm\nlubelskie: chełmski' };
  assert.equal(zakresWpisu(listopad10, KOD.chelm), 'wymieniony');
  assert.equal(zakresWpisu(listopad10, KOD.lublin), 'mozliwy');
  // brak jednostek, jednostka bez województwa, „część województwa” i brak nazwy województwa nie dowodzą całości
  assert.equal(t.calyRegionZMiejsca('lubelskiego', '06'), false);
  assert.equal(t.calyRegionZMiejsca('lubelskiego\nChełm', '06'), false);
  assert.equal(t.calyRegionZMiejsca('lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim\nlubelskie: część województwa', '06'), false);
  assert.equal(t.calyRegionZMiejsca('dolnośląskie\ndolnośląskie: świdnickim', '06'), false);
  assert.equal(t.calyRegionZMiejsca('lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim', '06'), true);
  assert.equal(t.calyRegionZMiejsca('lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim', '0663'), true, 'kod powiatu sprowadza się do województwa');
  assert.equal(t.calyRegionZMiejsca('lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim', '02'), false);
  assert.equal(t.calyRegionZMiejsca(undefined, '06'), false);
  const bezDowodu = { teryt: ['02', '06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim\nlubelskie: część województwa' };
  assert.notEqual(zakresWpisu(bezDowodu, KOD.lublin), 'wojewodztwo', '„część województwa” obok powiatu z innego województwa nie jest całością');
  const starszy = { teryt: ['06'], zasieg: 'przyblizony', miejsce: 'lubelskiego\nChełm' };
  assert.notEqual(zakresWpisu(starszy, KOD.lublin), 'wojewodztwo', 'starszy zapis bez województwa przy jednostce: bez zmian');
  // opis na karcie: jednostki z dopiskiem województwa
  const opis = t.opisMiejsca({ teryt: ['02', '06'], dokladnosc: 'wojewodztwo', szerokosc: null, dlugosc: null, bbox: null, zasieg: 'przyblizony',
    miejsce: 'lubelskiego\ndolnośląskie\ndolnośląskie: świdnickim' });
  assert.match(opis, /całe: województwo lubelskie; źródło wymienia: świdnickim \(dolnośląskie\)/);
});

test('R38c P2: ten sam ukryty wpis w wykazie i w zdarzeniu to jeden komunikat w ostrzeżeniu', () => {
  const mod = m();
  const warstwy = d().probneWarstwy();
  const wpisy = d().probneWpisy();
  const zdarzenia = d().probneZdarzenia();
  const bezPozarow = mod.potwierdzoneWarstwy(warstwy.filter(w => w.warstwa !== 'pozary'), true);
  const wynik = mod.tylkoPotwierdzone(wpisy, zdarzenia, bezPozarow, mod.kodyWylaczonych(warstwy));
  const naLiscie = new Set(wpisy.filter(w => w.warstwa === 'pozary').map(w => w.id));
  const wZdarzeniach = new Set(zdarzenia.flatMap(z => z.wpisy.filter(w => w.warstwa === 'pozary').map(w => w.id)));
  const wspolne = [...naLiscie].filter(id => wZdarzeniach.has(id));
  assert.ok(wspolne.length > 0, 'próbka ma ukryty wpis i na liście, i w zdarzeniu (inaczej test niczego nie dowodzi)');
  assert.equal(wynik.ukryteId.size, new Set([...naLiscie, ...wZdarzeniach]).size);
  assert.ok(wynik.ukryte + wynik.ukrytePowiazane > wynik.ukryteId.size, 'suma obu liczników dubluje wspólne wpisy');
  // jeden wpis obecny w obu listach: licznik 1
  const jeden = wpisy.find(w => w.warstwa === 'pozary');
  const zdarzenie = { ...zdarzenia[0], wpisy: [jeden] };
  const wJednym = mod.tylkoPotwierdzone([jeden], [zdarzenie], bezPozarow, mod.kodyWylaczonych(warstwy));
  assert.equal(wJednym.ukryteId.size, 1);
  assert.equal(wJednym.ukryte, 1);
  assert.equal(wJednym.ukrytePowiazane, 1);
  // render strony: w ostrzeżeniu liczba różnych komunikatów, nie suma
  ustawDane({ warstwy: udane(warstwy.filter(w => w.warstwa !== 'pozary')) });
  const html = tekst(strona());
  assert.match(html, new RegExp(`warstw bez potwierdzenia \\(${wynik.ukryteId.size}\\)`), html);
  assert.ok(!new RegExp(`warstw bez potwierdzenia \\(${wynik.ukryte + wynik.ukrytePowiazane}\\)`).test(html), 'bez podwójnego liczenia');
  // ten sam warunek w widoku „Mój powiat”
  const powiat = tekst(strona({ widok: 'powiat' }, ['1813']));
  assert.ok(!/warstw bez potwierdzenia/.test(powiat) || new RegExp(`\\(${wynik.ukryteId.size}\\)`).test(powiat), powiat);
});

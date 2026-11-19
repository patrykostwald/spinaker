// „Teraz”, Z6P8 (decyzja koordynatora): „Mój powiat” NIGDY nie twierdzi, że powiat nie jest objęty komunikatem.
// Etykiety zaprzeczające („nie ma na liście”, „komunikat wyłącza Twój powiat”) nie istnieją; dozwolone: „wymieniony”,
// „całe województwo”, „możliwe: sprawdź treść komunikatu” oraz neutralne „źródło nie podaje powiatów”.
// Zbiór tekstów: wszystkie przypadki z parsera (147-przeszlosc-teraz-zasieg-rcb.json: zdania z recenzji R38d, R38e i R38f)
// razy każdy powiat w Polsce razy każda wersja wpisu. node --test.
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
const powiaty = () => load(`${dir}/powiaty`);
const slownik = () => load(`${dir}/slownik`);
const przypadki = load('tests/147-przeszlosc-teraz-zasieg-rcb.json').przypadki;
const ZAKAZANE = /nie ma na liście|wyłącza|nie dotyczy|nie obejmuje|nie jest objęt/i;
const DOZWOLONE = new Set(['powiat', 'gmina', 'wymieniony', 'wojewodztwo', 'mozliwy', 'bezListy']);

test('Z6P8: zbiór tekstów z R38d, R38e i R38f jest kompletny', () => {
  for (const id of ['r38f-drugie-lubelskiego', 'r38f-rumia-bez-czasownika', 'r38f-godz', 'r38f-prosimy',
    'r38f-rozszerzenie-w-aktualizacji', 'r38f-gmina-zarow-i-powiat', 'miasto-rumia', 'gmina-zarow', 'czesc-w-tym-powiat',
    'wylaczenie-w-osobnym-zdaniu', 'wylaczenie-i-drugie-wojewodztwo', 'odsylacz-nr', 'element-nieczytelny']) {
    assert.ok(przypadki[id], id);
  }
});

test('Z6P8: żaden tekst i żaden powiat nie dają zakresu ani etykiety zaprzeczającej', () => {
  const p = powiaty();
  let sprawdzone = 0;
  for (const [id, przypadek] of Object.entries(przypadki)) {
    for (const [i, w] of przypadek.wpisy.entries()) {
      const wpis = { teryt: w.teryt, zasieg: w.zasieg, miejsce: w.miejsce };
      for (const powiat of slownik().POWIATY) {
        const z = p.zakresDlaPowiatu(wpis, powiat.kod);
        sprawdzone++;
        if (z === null) continue;
        assert.ok(DOZWOLONE.has(z), `${id}#${i} ${powiat.kod}: zakres „${z}” nie jest dozwolony`);
        assert.doesNotMatch(p.zakresTekstem(z, powiat.kod), ZAKAZANE, `${id}#${i} ${powiat.kod}`);
      }
    }
  }
  assert.ok(sprawdzone > 5000, `sprawdzono ${sprawdzone} par wpis-powiat`);
});

test('Z6P8: typ Zakres nie zawiera zakresów zaprzeczających i wszystkie teksty są neutralne', () => {
  const p = powiaty();
  for (const z of DOZWOLONE) assert.doesNotMatch(p.zakresTekstem(z, '0661'), ZAKAZANE, z);
  assert.ok(!p.ZAKRESY_POWIATU.has('pozaLista') && !p.ZAKRESY_POWIATU.has('wylaczony'));
  for (const z of ['pozaLista', 'wylaczony']) assert.doesNotMatch(p.zakresTekstem(z, '0661'), ZAKAZANE, `${z}: nieznany zakres też bez zaprzeczenia`);
});

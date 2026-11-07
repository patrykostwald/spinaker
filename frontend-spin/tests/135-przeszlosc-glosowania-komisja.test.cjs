// przeszłość.today: filtr „według komisji” i etykieta tematu w ogólnym widoku głosowań (glosowania-lista.ts, GlosowaniaPage.tsx), 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
function load(file) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: () => ({}), URLSearchParams, Date, Math, Number, Boolean, String, Array, Object, Intl }, { filename: file });
  return exports;
}
const L = load('app/przeszlosc/glosowania-lista.ts');

test('zapytanie do API zawiera komisję tylko dla Sejmu i obcina długość', () => {
  const q = new URLSearchParams(L.buildVotesQuery({ ...L.EMPTY_FILTERS, komisja: 'Komisja Zdrowia' }));
  assert.equal(q.get('komisja'), 'Komisja Zdrowia');
  assert.equal(new URLSearchParams(L.buildVotesQuery({ ...L.EMPTY_FILTERS, rodzaj: 'pe', komisja: 'Komisja Zdrowia' })).get('komisja'), null);
  assert.equal(new URLSearchParams(L.buildVotesQuery({ ...L.EMPTY_FILTERS, komisja: 'x'.repeat(300) })).get('komisja').length, 120);
});

test('adres strony przenosi komisję w obie strony; filtr liczy się jako aktywny', () => {
  const f = L.parseFilters('?komisja=Komisja%20Zdrowia&klub=KO');
  assert.equal(f.komisja, 'Komisja Zdrowia');
  assert.equal(L.filtersToSearch(f), '?klub=KO&komisja=Komisja+Zdrowia');
  assert.equal(L.hasFilters({ ...L.EMPTY_FILTERS, komisja: 'Komisja Zdrowia' }), true);
  assert.equal(L.hasFilters(L.EMPTY_FILTERS), false);
  assert.equal(L.parseFilters('').komisja, '');
});

test('strona: lista komisji z liczbą głosowań i temat w jednej linii pod tytułem', () => {
  const page = read('app/przeszlosc/glosowania/GlosowaniaPage.tsx');
  assert.match(page, /htmlFor="gl-kom"/);
  assert.match(page, /meta\?\.committees\?\.length/);
  assert.match(page, /apply\(\{ komisja: e\.target\.value \}\)/);
  assert.match(page, /druk \$\{v\.topic\.druk\}/);
  assert.match(page, /komisje\.slice\(0, 2\)/);
  assert.match(read('app/przeszlosc/glosowania-lista.css'), /\.gl-sel \{[^}]*min-height: 44px/);
});

// przeszłość.today: opis okna „90 dni” w Odstępstwach od klubu (app/przeszlosc/odstepstwa-okno.ts), runda person 1.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
function load(file) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: () => ({}), Date, Math }, { filename: file });
  return exports;
}
const W = load('app/przeszlosc/odstepstwa-okno.ts');
const fmt = iso => iso.slice(0, 10);

test('zakres 5-21.10 przy oknie 90 dni: komunikat z granicami okna i brakiem wcześniejszych danych', () => {
  const note = W.windowNote('90d', '2026-10-05', '2026-10-21', fmt);
  assert.match(note, /Okno 90 dni sięga 2026-07-23/);
  assert.match(note, /dopiero od 2026-10-05/);
  assert.match(note, /brak w naszych danych/);
});

test('zakres pokrywa okno (różnica do tygodnia): bez komunikatu', () => {
  assert.equal(W.windowNote('90d', '2026-07-25', '2026-10-21', fmt), null);
  assert.equal(W.windowNote('90d', '2026-07-30', '2026-10-21', fmt), null); // 7 dni zapasu
  assert.notEqual(W.windowNote('90d', '2026-07-31', '2026-10-21', fmt), null); // 8 dni: komunikat
});

test('cała kadencja i brak dat: bez komunikatu', () => {
  assert.equal(W.windowNote('term', '2026-10-05', '2026-10-21', fmt), null);
  assert.equal(W.windowNote('90d', null, '2026-10-21', fmt), null);
  assert.equal(W.windowNote('90d', '2026-10-05', undefined, fmt), null);
});

test('komponent korzysta z funkcji, pokazuje „Pokaż więcej” i podpisuje liczniki', () => {
  const c = read('app/przeszlosc/Odstepstwa.tsx');
  assert.match(c, /from '\.\/odstepstwa-okno'/);
  assert.match(c, /Pokaż więcej \(/);
  assert.match(c, /wszystkie kluby razem/);
  assert.match(c, /pokazujemy \$\{current\.rebellions\.length\} z \$\{current\.rebellions_total\}/);
});

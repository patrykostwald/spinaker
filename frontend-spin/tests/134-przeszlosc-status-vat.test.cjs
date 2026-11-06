// przeszłość.today: status VAT z Białej listy MF na stronie spółki (DrzewoPieniedzy.tsx, vatLine), pozycja „źródła” 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const src = fs.readFileSync(path.join(__dirname, '..', 'app/przeszlosc/DrzewoPieniedzy.tsx'), 'utf8');
const m = src.match(/export function vatLine[\s\S]*?\n\}\n/);
assert.ok(m, 'funkcja vatLine istnieje');
const js = ts.transpileModule(m[0].replace('export function', 'function'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const ctx = {};
vm.runInNewContext(js + '\nthis.vatLine = vatLine;', ctx);
const base = { found: true, status: 'Czynny', registration_date: '2010-07-27', removal_date: null, removal_basis: null, restoration_date: null,
  denial_date: null, virtual_accounts: false, accounts: 3, changes: [], checked_at: '2026-11-06T02:33', source: 'x', url: 'https://x', note: '' };

test('brak sprawdzenia: nic nie pokazujemy', () => { assert.equal(ctx.vatLine(null), ''); assert.equal(ctx.vatLine(undefined), ''); });
test('czynny podatnik z datą rejestracji i stanem na dzień', () => {
  assert.equal(ctx.vatLine(base), 'Status VAT: czynny, zarejestrowany 2010-07-27 (stan na 2026-11-06).');
});
test('wykreślenie, podstawa i zmiana statusu', () => {
  const line = ctx.vatLine({ ...base, status: 'Wykreślony', removal_date: '2026-11-01', removal_basis: 'art. 96 ust. 9', changes: [{ date: '2026-11-02', from: 'Czynny', to: 'Wykreślony' }] });
  assert.match(line, /wykreślony 2026-11-01 \(art\. 96 ust\. 9\)/);
  assert.match(line, /zmiana statusu 2026-11-02: Czynny → Wykreślony/);
});
test('podmiot spoza wykazu: komunikat „brak w wykazie”, nie „nie jest podatnikiem”', () => {
  assert.equal(ctx.vatLine({ ...base, found: false, status: null }), 'Status VAT: brak w wykazie podatników VAT (stan na 2026-11-06).');
});
test('komponent pokazuje wiersz tylko gdy jest status i podaje źródło', () => {
  assert.match(src, /\{data\.vat && <p className="px-note px-mt__vat">\{vatLine\(data\.vat\)\}/);
  assert.match(src, /Wykaz MF ↗/);
});

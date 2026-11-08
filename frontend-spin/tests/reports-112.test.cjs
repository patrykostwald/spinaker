const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync(path.join(__dirname, '../app/dla-redakcji/InstitutionReports.tsx'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
const mod = { exports: {} };
new Function('require', 'module', 'exports', code)(name => {
  if (name.endsWith('.css')) return {};
  if (name === 'next/link') return ({ href, children }) => React.createElement('a', { href }, children);
  if (name === '@spin-clinic/ui') return { glueShortWords: s => s };
  if (name === '@spin-clinic/ui/kit') return {};
  return require(name);
}, mod, mod.exports);
const render = props => renderToStaticMarkup(React.createElement(mod.exports.ReportSampleContent, props));
test('brak próbki ma uczciwy komunikat i planowaną datę', () => {
  const html = render({ sample: { available: false, next_report_at: '2026-10-12T06:40:00+02:00' } });
  assert.match(html, /Próbka raportu pojawi się po najbliższym raporcie tygodniowym/);
  assert.match(html, /12 października 2026/);
  assert.match(html, /06:40/);
  assert.doesNotMatch(html, /<table|sc-rep-box__nums/);
});
test('loading i błąd nie udają braku raportu', () => {
  assert.match(render({ sample: null }), /aria-busy="true"/);
  const error = render({ sample: null, error: true });
  assert.match(error, /Nie udało się wczytać/);
  assert.doesNotMatch(error, /pojawi się po najbliższym/);
});
test('próbka ma oba obozy, null nie zamienia się w zero, prywatne tabele nie są renderowane', () => {
  const camp = { count: 0, weighted_spin_percent: null, average_intensity: null };
  const html = render({ sample: { available: true, start: '2026-10-05', week_end: '2026-10-11', total: 4,
    camps: { government: { ...camp, count: 4, weighted_spin_percent: 0, average_intensity: 10 }, opposition: camp },
    clubs: [{ club: 'POUFNE' }], summary: ['POUFNE'], scope: 'Tylko liczby zbiorcze.' } });
  assert.match(html, /Rządzący/); assert.match(html, /Opozycja/);
  assert.match(html, /Brak danych/); assert.match(html, /0%/);
  assert.doesNotMatch(html, /POUFNE|<table|null\/100/);
});

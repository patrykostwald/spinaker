const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../app/przeszlosc/Paski.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function load(env = {}) {
  const exports = {};
  vm.runInNewContext(code, { exports, require, URL, process: { env } });
  return exports;
}

const { MetadataStrip, safeOriginal } = load();
const item = { id: 'film-1', title: 'Posiedzenie komisji - pełny zapis', date: '2026-10-09T12:00:00Z',
  source: 'Sejm RP', url: 'https://www.youtube.com/watch?v=abcdefghijk', category: 'sejm', category_label: 'Sejm',
  image_url: 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg' };
function render(props = {}) {
  return renderToStaticMarkup(React.createElement(MetadataStrip, { name: 'youtube', title: 'YouTube', items: [item],
    categories: [{ id: 'sejm', label: 'Sejm' }], state: 'ready', retry: () => {}, ...props }));
}

test('adresy oryginałów dopuszczają tylko bezwzględne HTTP i HTTPS', () => {
  assert.equal(safeOriginal('https://www.sejm.gov.pl/dokument'), 'https://www.sejm.gov.pl/dokument');
  assert.equal(safeOriginal('http://example.org/'), 'http://example.org/');
  for (const url of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,test', 'file:///tmp/test', '//example.org', '/wpis', '']) {
    assert.equal(safeOriginal(url), undefined, url);
  }
});

test('karta SSR ma pełne metadane, bezpieczny link i dostępną klawiaturze listę', () => {
  const html = render();
  assert.match(html, /Posiedzenie komisji - pełny zapis/);
  assert.match(html, /Sejm RP/);
  assert.match(html, /target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /otwiera nową kartę/);
  assert.match(html, /<time dateTime="2026-10-09T12:00:00Z">9\.10\.2026<\/time>/);
  assert.match(html, /tabindex="0" role="region"/);
  assert.match(html, /alt=""/);
  assert.equal((html.match(/aria-pressed="true"/g) || []).length, 1);
  assert.match(html, /aria-pressed="true">Wszystko/);
});

test('stany ładowania, błędu i pusty są nazwane oraz wyłączają przewijanie', () => {
  for (const [props, message] of [
    [{ state: 'loading', items: [] }, 'Ładowanie materiałów…'],
    [{ state: 'error', items: [] }, 'Nie udało się pobrać materiałów.'],
    [{ items: [] }, 'Brak materiałów w tej kategorii.'],
  ]) {
    const html = render(props);
    assert.ok(html.includes(message));
    assert.match(html, /role="status"/);
    assert.equal((html.match(/disabled=""/g) || []).length, 2);
    assert.doesNotMatch(html, /class="px-strip__card"/);
  }
  assert.match(render({ state: 'loading', items: [] }), /aria-busy="true"/);
  assert.match(render({ state: 'error', items: [] }), /Spróbuj ponownie/);
});

test('obce miniatury i niebezpieczne adresy nie tworzą odnośników ani obrazów', () => {
  const html = render({ items: [{ ...item, image_url: 'https://other.example/image.jpg' }, { ...item, id: 'bad', title: 'Niebezpieczny wpis', url: 'javascript:alert(1)' }] });
  assert.doesNotMatch(html, /other\.example|Niebezpieczny wpis|javascript:/);
  assert.match(html, /Film na YouTube/);
});

test('pasek publiczny pokazuje typ i brak daty bez diagnoz z dodatkowych pól', () => {
  const html = render({ name: 'publiczne', title: 'Źródła publiczne', items: [{ ...item, date: null,
    category_label: 'Interpelacja', diagnosis: 'Diagnoza Dr. Spina', spin_score: 95, intensity: 95 }] });
  assert.match(html, /Interpelacja/);
  assert.match(html, /Bez daty/);
  assert.doesNotMatch(html, /Diagnoza|Dr\. Spina|spin_score|intensity|<img/);
});

test('media domyślnie wyłączone, jawne 1 włącza trzeci pasek', () => {
  for (const value of [undefined, '0', 'true', '1']) {
    const mod = load(value === undefined ? {} : { NEXT_PUBLIC_PRZESZLOSC_PASEK_MEDIA: value });
    assert.equal(mod.MEDIA_ENABLED, value === '1');
    const html = renderToStaticMarkup(React.createElement(mod.Paski));
    assert.match(html, /data-strip="youtube"/);
    assert.match(html, /data-strip="publiczne"/);
    assert.equal(html.includes('data-strip="media"'), value === '1');
  }
});

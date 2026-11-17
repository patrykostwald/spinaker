// przeszłość.today, poprawki po recenzji Fable (13.10.2026): kontrola kształtu plików (logika w komponentach, pomiary w gust/spin/port/fable-pt-check.cjs).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const tree = read('app/przeszlosc/TopicTree.tsx');
const css = read('app/przeszlosc/v3.css');
const dev = read('app/przeszlosc/Odstepstwa.tsx');
const profile = read('app/przeszlosc/PersonProfile.tsx');

test('strona główna: karta tematu dnia zamiast całego widoku, odnośnik do pełnego tematu', () => {
  assert.match(tree, /daily \? <DailyTopic /);
  assert.match(tree, /Zobacz cały temat/);
  assert.match(tree, /\.slice\(0, narrow \? 5 : 6\)/);
  assert.match(tree, /<Odstepstwa compact \/>/);
  assert.match(dev, /compact = false/);
});

test('etykiety źródeł po polsku, bez surowych kluczy; linki t.co skracane; identyczne węzły drzewa łączone z licznikiem', () => {
  assert.match(tree, /questions: 'Pytania poselskie'/); assert.match(tree, /howtheyvote: 'Głosy w PE'/);
  assert.match(tree, /\[a-z0-9_\]\+/); // nieznany klucz bez polskiej nazwy nie jest pokazywany
  assert.match(read('app/przeszlosc/ui.tsx'), /\[link w X\]/); assert.match(tree, /tidyGraph\(/); assert.match(profile, /tidyLinks\(p\.text\)/);
  assert.match(tree, /dups\.set\(/); assert.match(tree, /data-cols=\{model\.right\.length \? 3 : 2\}/);
  assert.match(tree, /model\.right\.length > 0 && <div className="px-tree__col">/);
});

test('"Kto występuje": nazwisko i funkcja w jednym celu, brak nachodzenia; cele 44 px; fokus summary', () => {
  assert.match(tree, /className="px-name pt-person"/);
  assert.match(css, /\.px-people__body > \.pt-person \{[^}]*min-height: 44px/);
  assert.match(css, /summary, details > summary\):focus-visible \{ outline: 2px solid var\(--sc-focus\) !important/);
  assert.match(css, /\.pt-tile__x a \{ display: flex; width: fit-content; min-height: 44px/);
});

test('rodzina: dni i rodzaje bez wersalików, menu 14 px, pasek 64/56, serie wykresu neutralne, jedna akcja Pobierz, głosy jako liczby', () => {
  assert.match(css, /\.px-day, \.px-path b\) \{ font-size: 13px; font-weight: 600; letter-spacing: \.01em; text-transform: none; \}/);
  assert.match(css, /font-size: 14px; letter-spacing: \.02em/);
  assert.match(css, /\.pt-top \{ padding-block: 10px; \}/);
  assert.doesNotMatch(css.slice(css.indexOf('Aktywność": serie w tonach neutralnych')), /\[data-s="posts"\] \{ --k: var\(--sc-accent\)/);
  assert.match(tree, /className="pt-dl"/); assert.match(profile, /className="pt-dl"/);
  assert.doesNotMatch(profile, /px-pp__votebar/); assert.match(profile, /className="pt-votes"/);
});

test('teksty: bez długiego myślnika i bez uszkodzonych znaków w zmienionych plikach', () => {
  for (const f of ['app/przeszlosc/TopicTree.tsx', 'app/przeszlosc/Odstepstwa.tsx', 'app/przeszlosc/PersonProfile.tsx']) {
    const s = read(f);
    assert.equal(/[–—]/.test(s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')), false, `${f}: długi myślnik`);
    assert.equal(s.includes('�'), false, `${f}: uszkodzone znaki`);
  }
});

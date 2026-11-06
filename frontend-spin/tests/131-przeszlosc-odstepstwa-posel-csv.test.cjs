// przeszłość.today: filtr po pośle i eksport CSV w Odstępstwach (app/przeszlosc/Odstepstwa.tsx), pozycja 2 planu 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const c = read('app/przeszlosc/Odstepstwa.tsx');
const css = read('app/przeszlosc/odstepstwa.css');

test('komponent pobiera pełną listę z parametrami klub, poseł i zdarzenia, a bez niej zostaje skrót', () => {
  assert.match(c, /zdarzenia: '1'/);
  assert.match(c, /q\.set\('posel', String\(mp\)\)/);
  assert.match(c, /full\?\.events \?\? current\?\.rebellions/);
});

test('wybór posła: lista z liczbą głosów, wraca do „wszyscy” przy zmianie klubu lub okresu', () => {
  assert.match(c, /Poseł z klubu/);
  assert.match(c, /wszyscy \(\$\{current\.rebellions_total\} głosów\)|wszyscy \(\{current\.rebellions_total\} głosów\)/);
  assert.match(c, /setMore\(false\); setMp\(null\)/);
});

test('CSV: odnośnik z eksport=csv i atrybutem download, widoczny tylko przy pełnej liście', () => {
  assert.match(c, /eksport: 'csv'/);
  assert.match(c, /\{full && <> · <a className="px-link" href=\{`\$\{API\}\?\$\{csvQuery\}`\} download>Pobierz CSV/);
});

test('lista po „Pokaż więcej” ma limit, reszta w CSV; pasek filtra nie zmienia wysokości boksów', () => {
  assert.match(c, /SHOWN_MAX = 100/);
  assert.match(c, /resztę znajdziesz w pliku CSV/);
  assert.match(css, /\.px-dev__tools \{[^}]*min-height: 44px/);
  assert.match(css, /\.px-dev__pick select \{[^}]*min-height: 44px/);
});

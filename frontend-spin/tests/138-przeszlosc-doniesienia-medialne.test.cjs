// przeszłość.today: okno „Podmioty z doniesień medialnych” (app/przeszlosc/PodmiotyZMediow.tsx) w profilu osoby, 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const c = read('app/przeszlosc/PodmiotyZMediow.tsx');

test('okno: znika bez doniesień, stała notka o braku dowodu, kategoria i oznaczenie „niepotwierdzone”', () => {
  assert.match(c, /if \(!data \|\| !data\.count\) return null/);
  assert.match(c, /data\.notice/);
  assert.match(c, /m\.category_label/); assert.match(c, /niepotwierdzone/);
  assert.match(c, /Podmioty z doniesień medialnych/);
});

test('okno: podmiot prowadzi do strony spółki, źródło otwiera się w nowej karcie, bez opisu charakteru powiązania', () => {
  assert.match(c, /href=\{m\.organisation\.url\}/);
  assert.match(c, /href=\{m\.source\.url\} target="_blank" rel="noopener noreferrer"/);
  assert.doesNotMatch(c, /powiązan[a-z]* z|związek|współpracuje/i);
});

test('profil osoby: okno po wzmiankach, dane z org_mentions', () => {
  const p = read('app/przeszlosc/PersonProfile.tsx');
  assert.match(p, /org_mentions\?: OrgMentions/);
  assert.match(p, /<PodmiotyZMediow data=\{data\.org_mentions\} \/>/);
  assert.ok(p.indexOf('id="pp-mentions-h"') < p.indexOf('<PodmiotyZMediow'));
});

test('układ: wiersze o stałej wysokości, tytuły w jednej linii, cele 44 px przez chipy wspólne', () => {
  const css = read('app/przeszlosc/podmioty-media.css');
  assert.match(css, /--om-row: 96px/); assert.match(css, /text-overflow: ellipsis/);
  assert.match(css, /-webkit-line-clamp: 1/);
});

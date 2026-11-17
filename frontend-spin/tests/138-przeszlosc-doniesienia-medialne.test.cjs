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

test('profil osoby: okno wysoko, przed „W mediach”, dane z org_mentions', () => {
  const p = read('app/przeszlosc/PersonProfile.tsx');
  assert.match(p, /org_mentions\?: OrgMentions/);
  assert.match(p, /<PodmiotyZMediow data=\{data\.org_mentions\} \/>/);
  assert.ok(p.indexOf('<PodmiotyZMediow') < p.indexOf('id="pp-media"'));
  assert.ok(p.indexOf('<PodmiotyZMediow') < p.indexOf('id="pp-os"'), 'okno doniesień stoi przed osią czasu (8.11)');
});

test('układ: wiersze o stałej wysokości, tytuły w jednej linii, cele 44 px przez chipy wspólne', () => {
  const css = read('app/przeszlosc/podmioty-media.css');
  assert.match(css, /--om-row: 120px/); assert.match(css, /text-overflow: ellipsis/);
  assert.match(css, /-webkit-line-clamp: 1/);
});

test('podmiot ma link do urzędowego odpisu KRS i do rejestr.io w nowej karcie', () => {
  assert.match(c, /register_url\?: string; extra_url\?: string/);
  assert.match(c, /href=\{m\.organisation\.register_url\} target="_blank" rel="noopener noreferrer"/);
  assert.match(c, /href=\{m\.organisation\.extra_url\} target="_blank" rel="noopener noreferrer"/);
  assert.match(c, /Urzędowy odpis z KRS/); assert.match(c, />odpis ↗</);
});

test('podmiot bez KRS: bez strony spółki i rejestr.io, z identyfikatorem i linkiem do właściwego rejestru (8.11)', () => {
  for (const key of ['no_krs', 'Bez wpisu w KRS', 'identifier', 'Rejestr urzędowy:']) assert.ok(c.includes(key), key);
  assert.match(c, /m\.organisation\.no_krs\s*\?\s*<span className="px-om__org"/);
});

test('odesłanie z kafla KRS do okna doniesień: tylko gdy są pozycje, kotwica z marginesem pod paskiem (8.11)', () => {
  const n = read('app/przeszlosc/Najwazniejsze.tsx'), p = read('app/przeszlosc/PersonProfile.tsx');
  assert.match(n, /wide && mentions > 0 &&[\s\S]*href="#pp-doniesienia"/);
  assert.match(p, /mentions=\{data\.org_mentions\?\.count \?\? 0\}/);
  assert.ok(c.includes('id="pp-doniesienia"'));
});

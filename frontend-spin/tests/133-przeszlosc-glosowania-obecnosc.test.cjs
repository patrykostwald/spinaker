// przeszłość.today: podsumowanie oddanych głosów posła w profilu (GlosowaniaOsoby.tsx, pole attendance z API), pozycja 2 planu 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const c = fs.readFileSync(path.join(__dirname, '..', 'app/przeszlosc/GlosowaniaOsoby.tsx'), 'utf8');

test('komponent czyta attendance i pokazuje oddane głosy bez oceny powodu', () => {
  assert.match(c, /type Attendance = \{ total: number; voted: number; absent: number; other: number; share: number \| null \}/);
  assert.match(c, /Oddane głosy: \$\{data\.attendance\.voted\} z \$\{data\.attendance\.total\} głosowań/);
  assert.match(c, /Brak głosu to nieobecność albo niegłosowanie; powodu nie oceniamy/);
});

test('wiersz tylko gdy są głosowania (Sejm), nie dla PE ani pustej listy', () => {
  assert.match(c, /data\.attendance && data\.attendance\.total > 0/);
});

test('etykieta tematu z procesu legislacyjnego: druk i komisje, tylko gdy jest powiązanie', () => {
  assert.match(c, /topic\?: \{ druk: string; tytul: string; rodzaj: string; komisje: string\[\] \} \| null/);
  assert.match(c, /r\.topic \? `druk \$\{r\.topic\.druk\}/);
  assert.match(c, /komisje\.slice\(0, 2\)/);
  assert.match(c, /title=\{r\.topic\?\.tytul \|\| undefined\}/);
});

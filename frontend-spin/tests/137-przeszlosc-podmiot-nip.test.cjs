// przeszłość.today: „Podmiot po NIP” (app/przeszlosc/PodmiotNip.tsx, strona /przeszlosc/podmiot/<NIP>) i wskazówka w wyszukiwarce spółek, 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const c = read('app/przeszlosc/PodmiotNip.tsx');

test('strona: tylko 10 cyfr w adresie, bez indeksowania, wspólny pasek i stopka', () => {
  const page = read('app/przeszlosc/podmiot/[nip]/page.tsx');
  assert.match(page, /\/\^\\d\{10\}\$\/\.test\(params\.nip\)\) notFound\(\)/);
  assert.match(page, /robots: \{ index: false, follow: false \}/);
  assert.match(read('app/przeszlosc/podmiot/PodmiotNipPage.tsx'), /<Bar \/>[\s\S]*<PodmiotNip nip=\{nip\} \/>[\s\S]*<Foot \/>/);
});

test('komponent: dane z API po NIP, listy zamówień i dotacji, źródła i zasada łączenia, kwoty wątpliwe oznaczone', () => {
  assert.match(c, /\/api\/przeszlosc\/podmiot\/\$\{nip\}\//);
  assert.match(c, /Zamówienia publiczne/); assert.match(c, /Dotacje UE \(FTS\)/);
  assert.match(c, /kwota wątpliwa \(poza sumą\)/); assert.match(c, /data\.rules/);
  assert.match(c, /data\?\.status === 'krs' && data\.url/);
  assert.match(c, /Brak ogłoszeń w naszych danych/);
});

test('wyszukiwarka spółek: przy braku podmiotu z KRS pokazuje link do widoku po NIP', () => {
  const t = read('app/przeszlosc/TopicTree.tsx');
  assert.match(t, /nip_page\?: \{ url: string; has_data: boolean \}/);
  assert.match(t, /firms\.nip_page\.has_data \? 'Zobacz ogłoszenia i dotacje po NIP →'/);
});

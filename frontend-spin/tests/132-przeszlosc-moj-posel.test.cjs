// przeszłość.today: „Mój poseł” (app/przeszlosc/MojPosel.tsx, strona /przeszlosc/moj-posel), pozycja 2 planu 6.11.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const c = read('app/przeszlosc/MojPosel.tsx');
const css = read('app/przeszlosc/moj-posel.css');

test('strona istnieje, nie jest indeksowana i używa wspólnego paska i stopki', () => {
  const page = read('app/przeszlosc/moj-posel/page.tsx');
  assert.match(page, /robots: \{ index: false, follow: false \}/);
  assert.match(read('app/przeszlosc/moj-posel/MojPoselPage.tsx'), /<Bar \/>[\s\S]*<MojPosel \/>[\s\S]*<Foot \/>/);
});

test('komponent: lista okręgów, posłowie okręgu, profil po slugu, a bez profilu odnośnik do Sejmu', () => {
  assert.match(c, /\/api\/przeszlosc\/moj-posel\//);
  assert.match(c, /okreg=\$\{encodeURIComponent\(chosen\)\}/);
  assert.match(c, /\/przeszlosc\/osoba\/\$\{m\.slug\}/);
  assert.match(c, /m\.sejm_url/);
  assert.match(c, /rel: 'noopener noreferrer'/);
  assert.match(c, /brak w naszych danych/);
});

test('styl: cele 44 px i stała wysokość wiersza', () => {
  assert.match(css, /\.px-mp__pick select \{[^}]*min-height: 44px/);
  assert.match(css, /--mp-row: 64px/);
  assert.match(css, /\.px-mp__list a \{[^}]*min-height: var\(--mp-row\)/);
});

test('przy pośle: skrót odstępstw od klubu z 90 dni, gdy nocne przeliczenie go zna', () => {
  assert.match(c, /odstępstwa od klubu \(90 dni\)/);
  assert.match(c, /deviation_share/);
  assert.match(c, /sejm_id/);
});

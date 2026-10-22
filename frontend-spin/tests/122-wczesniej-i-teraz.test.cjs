// „Wcześniej i teraz” (13.10.2026): kontrola kształtu plików i zasady naczelnej "ta sama miara dla każdej strony, zawsze".
// Logika i render komponentu: packages/ui/src/lib/position-pair.test.mjs. Tu: wpięcia w aplikacji i flaga. Bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const ui = path.join(root, '..', 'packages', 'ui', 'src');
const read = (...p) => fs.readFileSync(path.join(...p), 'utf8');

test('flaga NEXT_PUBLIC_POSITION_PAIRS jest domyślnie wyłączona (tylko === "true" włącza), podgląd właściciela jak pozostałe flagi', () => {
  const features = read(ui, 'lib', 'features.ts');
  assert.match(features, /POSITION_PAIRS_ENABLED: process\.env\.NEXT_PUBLIC_POSITION_PAIRS === 'true'/);
  assert.match(features, /return publicFeatures\[name\] \|\| preview;/);
});

test('strona /klinika/stanowiska/[id]: bez flagi 404, kanoniczny adres, Open Graph, noindex do decyzji prawnika, neutralny opis', () => {
  const page = read(root, 'app', 'klinika', 'stanowiska', '[id]', 'page.tsx');
  assert.match(page, /NEXT_PUBLIC_POSITION_PAIRS === 'true' \|\| cookies\(\)\.get\('sc_preview'\)\?\.value === '1'/);
  assert.match(page, /if \(!id \|\| !enabled\(\)\) notFound\(\)/);
  assert.match(page, /alternates: \{ canonical: `\/klinika\/stanowiska\/\$\{id\}` \}/);
  assert.match(page, /openGraph: \{ title, description, type: 'article'/);
  assert.match(page, /robots: \{ index: false, follow: true \}/);
  assert.match(page, /\/api\/przeszlosc\/osoba\/\$\{encodeURIComponent\(osoba\)\}\/stanowiska\//);
  // identyfikator osoby z adresu walidowany (bez wstrzyknięć do ścieżki API)
  assert.match(page, /\^\[1-9\]\\d\{0,9\}\$/);
});

test('wpięcia: karta diagnozy (jedna linia), profil osoby spin.clinic, spinka; wszystkie przez flagę', () => {
  const spin = read(ui, 'components', 'clinic', 'SpinDetailV3.tsx');
  assert.match(spin, /<DiagnosisPairs block=\{spin\.position_pairs\} figureId=\{spin\.author\.figure_id\} \/>/);
  const diag = read(ui, 'components', 'clinic', 'DiagnosisPairs.tsx');
  assert.match(diag, /useFeature\("POSITION_PAIRS_ENABLED"\)/);
  assert.match(diag, /parsed\.paused \|\| !parsed\.items\.length\) return null/);
  const fig = read(ui, 'components', 'PublicFigureDirectory.tsx');
  assert.match(fig, /<PublicFigurePairs figureId=\{id\} \/>/);
  assert.match(read(ui, 'components', 'PublicFigurePairs.tsx'), /enabled, staleTime/);
  const steps = read(ui, 'components', 'community', 'ThreadSteps.tsx');
  assert.match(steps, /const pairsOn = useFeature\('POSITION_PAIRS_ENABLED'\)/);
  assert.match(steps, /item\.link_kind === 'przeczy'/);
});

test('przeszłość: sekcja i kafel za flagą, bez licznika; kafel używa klas landingu (bez własnego CSS)', () => {
  const src = read(root, 'app', 'przeszlosc', 'WczesniejITeraz.tsx');
  assert.match(src, /useFeature\('POSITION_PAIRS_ENABLED'\)/);
  assert.match(src, /block\.paused \|\| !block\.items\.length\) return null/);
  assert.doesNotMatch(src, /\.length\s*}|\{block\.items\.length|items\.length\} /, 'brak licznika par w interfejsie');
  assert.doesNotMatch(src, /import ['"].*\.css['"]/);
});

test('zasada naczelna: ten sam kod dla każdej osoby (brak gałęzi po osobie, partii, obozie), neutralne nazwy, bez kolorów ostrzegawczych', () => {
  const files = [
    read(ui, 'kit', 'PositionPair.tsx'), read(ui, 'kit', 'PositionPairReport.tsx'), read(ui, 'lib', 'positionPairs.ts'),
    read(ui, 'components', 'clinic', 'PositionPairPage.tsx'), read(ui, 'components', 'clinic', 'DiagnosisPairs.tsx'), read(root, 'app', 'przeszlosc', 'WczesniejITeraz.tsx'),
  ].join('\n').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  assert.doesNotMatch(files, /\bcamp\b|camp_label|\bparty\b|government|opposition|(?<!typeof )\w+\.(slug|name|figure_id) ===/i, 'żadnej gałęzi po osobie ani obozie');
  assert.doesNotMatch(files, /hipokryt|kłamst|zdrad|sprzeczn|zmienił zdanie|ostrzeż/i, 'bez słów oceniających w interfejsie');
  const css = read(ui, 'kit', 'position-pair.css');
  assert.doesNotMatch(css, /--sc-(negative|warning|positive|live|spin-|fam-)|#[0-9a-fA-F]{3,8}\b/, 'tylko tony tekstu, tła i akcent marki; zero kolorów na sztywno');
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /min-height: 44px/);
});

test('przeszłość: odnośnik z hosta przeszłości prowadzi do profilu (ścieżka /przeszlosc/osoba/<slug>#wczesniej-i-teraz), nie do /klinika/*', () => {
  const lib = read(ui, 'lib', 'positionPairs.ts');
  assert.match(lib, /`\/przeszlosc\/osoba\/\$\{encodeURIComponent\(String\(slugOrId\)\)\}#\$\{pairId \? `stanowiska-\$\{pairId\}` : POSITION_PAIRS_ANCHOR\}`/);
  const middleware = read(root, 'middleware.ts');
  assert.match(middleware, /OWN = \['\/przeszlosc'/);
});

test('profil przeszłości: wpięcie sekcji nad osią czasu, kafla w landingu i wpisu w spisie (tylko gdy API zwraca pary, za flagą)', () => {
  const profile = read(root, 'app', 'przeszlosc', 'PersonProfile.tsx');
  assert.match(profile, /position_pairs\?: unknown;/);
  assert.match(profile, /const pairs = usePairsBlock\(data\.position_pairs\);/);
  assert.ok(profile.indexOf('<PairsSection block={pairs} />') > 0 && profile.indexOf('<PairsSection block={pairs} />') < profile.indexOf('id="pp-os"'), 'sekcja tuż nad osią czasu');
  assert.match(profile, /extra=\{<PairsTile block=\{pairs\}/);
  assert.match(profile, /hasPairs: Boolean\(pairsIndexed\)/);
  assert.match(read(root, 'app', 'przeszlosc', 'Najwazniejsze.tsx'), /\{extra\}/);
  const data = read(root, 'app', 'przeszlosc', 'najwazniejsze-dane.ts');
  assert.match(data, /\['wczesniej-i-teraz', 'Wcześniej'\]/);
});

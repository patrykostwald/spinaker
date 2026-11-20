// „Teraz”, W4: montaż osi czasu na stronie (sprawdzenie źródeł, bez przeglądarki). Oś jest zamontowana raz i tylko w widokach
// z mapą; mapa, lista i tabela biorą wpisy z useWpisyWTrybie (TODAY = useWpisy, PRZESZŁOŚĆ = wpisy/?na=); „brak komunikatów”
// nie pojawia się przy niepełnym stanie archiwum; odtwarzanie znika przy prefers-reduced-motion; luki mają kreskowanie z podpisem.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '..', 'app/przeszlosc/teraz');
const czytaj = plik => fs.readFileSync(path.join(dir, plik), 'utf8');

test('161: TerazPage montuje oś raz, w widokach z mapą; mapa, lista i tabela biorą wpisy z useWpisyWTrybie', () => {
  const s = czytaj('TerazPage.tsx');
  assert.equal((s.match(/<Os /g) ?? []).length, 1);
  assert.match(s, /\{wMapie && <Os historia=\{historia\}/);
  assert.match(s, /const wpisyNaZywo = useWpisy\(probne, okres, woj, wMapie && pamiecGotowa\);/);
  assert.match(s, /const wpisyQ = useWpisyWTrybie\(historia, wpisyNaZywo, probne, okres, woj, wMapie && pamiecGotowa\);/);
  assert.equal((s.match(/\buseWpisy\(/g) ?? []).length, 1);
  // archiwum startuje dopiero po odczycie adresu; następna klatka odtwarzania pobierana z wyprzedzeniem
  const h = czytaj('useHistoria.ts');
  assert.match(h, /enabled: aktywne && gotowa && archiwum \}/);
  assert.match(h, /enabled: aktywne && gotowa && archiwum && odtwarzanie && nastepna !== na/);
  // style osi ładuje trasa (page.tsx), bo testy renderujące TerazPage nie znają arkuszy CSS
  assert.match(czytaj('page.tsx'), /import '\.\/os\.css';/);
  assert.match(s, /kompletneWpisy = [^\n]*!wpisyQ\.data\.niepelne/);
  // oś stoi między linią stanu a głównym obszarem (stała strefa nad mapą)
  assert.ok(s.indexOf('<LiniaStanu') < s.indexOf('<Os ') && s.indexOf('<Os ') < s.indexOf('className="tz-glowna"'));
});

test('161: odtwarzanie wyłączone przy prefers-reduced-motion, krok ręczny zostaje', () => {
  const h = czytaj('useHistoria.ts');
  const o = czytaj('Os.tsx');
  assert.match(h, /matchMedia\('\(prefers-reduced-motion: reduce\)'\)/);
  // przycisk zostaje na swoim miejscu (stała strefa), ale jest wyłączony; tempo zastępuje napis „Bez animacji”
  assert.match(o, /className="tz-os__odtworz" onClick=\{odtworz\} disabled=\{!gotowa \|\| ograniczonyRuch\}/);
  assert.match(o, /Bez animacji/);
  assert.doesNotMatch(o, /tz-os__odtworz[^>]*aria-pressed/, 'nazwa przycisku się zmienia, więc bez aria-pressed');
  assert.match(o, /if \(ograniczonyRuch && odtwarzanie\) ustawOdtwarzanie\(false\)/);
  assert.match(o, /aria-label=\{stan\.krok === 'dzien' \? 'Poprzedni dzień' : 'Poprzednia godzina'\}/);
  assert.match(o, /type="range"/);
  assert.match(o, /onKeyDown=\{klawisz\}/);
});

test('161: przełącznik TODAY (lang=en) / PRZESZŁOŚĆ, baner archiwum i etykieta stanu zawsze w DOM', () => {
  const o = czytaj('Os.tsx');
  assert.match(o, /<span lang="en">TODAY<\/span>/);
  assert.match(o, /PRZESZŁOŚĆ/);
  assert.match(o, /Archiwum, nie bieżące dane/);
  assert.match(o, /className="tz-os__moment"/);
  assert.match(o, /aria-live="polite"/);
});

test('161: style: kreskowanie luk, pas jako wiersz siatki, ramka sceny w archiwum, cele 44 px', () => {
  const c = fs.readFileSync(path.join(dir, 'os.css'), 'utf8');
  assert.match(c, /\.tz:has\(> \.tz-os\) \{ grid-template-rows: auto auto auto minmax\(0, 1fr\); \}/);
  assert.match(c, /--tz-os-kreski: repeating-linear-gradient/);
  assert.match(c, /\.tz-os__kreski \{[^}]*var\(--tz-os-kreski\)/);
  assert.match(c, /\.tz:has\(> \.tz-os\[data-tryb="przeszlosc"\]\) \.tz-scena::after/);
  assert.match(c, /min-height: var\(--tz-tap\)/);
  assert.match(c, /width: var\(--tz-tap\); height: var\(--tz-tap\)/);
});

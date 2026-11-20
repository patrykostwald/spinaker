// „Teraz” (W2): wygląd i dostępność łącza i zdrowia źródeł, sprawdzone na kodzie i tokenach (bez przeglądarki):
//  - kontrast tekstu i znaków stanu co najmniej 4,5:1 na każdej powierzchni w trzech motywach (ciemny, jasny/pastel) i w wyższym kontraście,
//    liczony z prawdziwych tokenów (packages/ui/src/kit/v3.css, teraz.css, zrodla.css),
//  - prefers-reduced-motion: arkusz źródeł nie ma żadnego ruchu, klawiatura: natywne <details>/<summary>, cele 44 px,
//  - zasady tekstu produktu: bez długich myślników, bez „spokojnie”/„bezpiecznie”, bez „bez komunikatów”. node --test.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { read, dir } = require('./150-zrodla-loader.cjs');

const CSS = read(`${dir}/zrodla.css`);
const TERAZ_CSS = read(`${dir}/teraz.css`);
const V3 = read('../packages/ui/src/kit/v3.css');

// ---------- kontrast WCAG ----------

const hex = h => { const n = parseInt(h.replace('#', ''), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const lin = c => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const kontrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const nakladka = (rgba, tlo) => rgba.slice(0, 3).map((c, i) => Math.round(c * rgba[3] + tlo[i] * (1 - rgba[3])));

/** Wartości zmiennej CSS z bloku zaczynającego się od `selektor {`. */
function blok(zrodlo, selektor) {
  const start = zrodlo.indexOf(`${selektor} {`);
  assert.ok(start >= 0, `brak bloku ${selektor}`);
  return zrodlo.slice(start, zrodlo.indexOf('}', start));
}
const zmienna = (b, nazwa) => { const m = new RegExp(`${nazwa}:\\s*(#[0-9a-fA-F]{6})`).exec(b); assert.ok(m, `brak ${nazwa}`); return hex(m[1]); };
const powierzchnie = b => ['--sc-bg', '--sc-surface', '--sc-surface-2', '--sc-surface-3'].map(n => [n, zmienna(b, n)]);

const ciemne = blok(V3, ':root:not([data-theme="light"]):not([data-theme="pastel"])');
const jasne = blok(V3, ':root[data-theme="light"], :root[data-theme="pastel"]');
const rgba = (b, nazwa) => { const m = new RegExp(`${nazwa}:\\s*rgba\\((\\d+), (\\d+), (\\d+), ([.\\d]+)\\)`).exec(b); assert.ok(m, nazwa); return [+m[1], +m[2], +m[3], +m[4]]; };

const MOTYWY = {
  ciemny: {
    tokeny: ciemne, ostrz_tlo: rgba(blok(TERAZ_CSS, '.tz'), '--tz-ostrz-tlo'),
    znaki: blok(CSS, '.tz'),
  },
  jasny: {
    tokeny: jasne, ostrz_tlo: rgba(blok(TERAZ_CSS, 'html[data-theme="light"] .tz'), '--tz-ostrz-tlo'),
    znaki: blok(CSS, 'html[data-theme="light"] .tz, html[data-theme="pastel"] .tz'),
  },
};
const wiecejKontrastu = CSS.slice(CSS.indexOf('@media (prefers-contrast: more)'));
const MOTYWY_WIECEJ = {
  ciemny: { tokeny: ciemne, znaki: blok(wiecejKontrastu, 'html:not([data-theme="light"]):not([data-theme="pastel"]) .tz'), text2: hex('#dfe2e6') },
  jasny: { tokeny: jasne, znaki: blok(wiecejKontrastu, 'html[data-theme="light"] .tz, html[data-theme="pastel"] .tz'), text2: hex('#1f2328') },
};

test('kontrast 4,5:1: tekst, tekst pomocniczy i znaki stanu na każdej powierzchni (ciemny, jasny, pastel)', () => {
  for (const [motyw, { tokeny, znaki }] of Object.entries(MOTYWY)) {
    for (const [nazwaTla, tlo] of powierzchnie(tokeny)) {
      for (const nazwa of ['--sc-text', '--sc-text-2']) {
        const k = kontrast(zmienna(tokeny, nazwa), tlo);
        assert.ok(k >= 4.5, `${motyw}: ${nazwa} na ${nazwaTla}: ${k.toFixed(2)}`);
      }
      for (const nazwa of ['--tz-dziala', '--tz-blad', '--tz-luka']) {
        const k = kontrast(zmienna(znaki, nazwa), tlo);
        assert.ok(k >= 4.5, `${motyw}: ${nazwa} na ${nazwaTla}: ${k.toFixed(2)}`);
      }
    }
  }
});

test('kontrast 4,5:1: tekst zdania „brak w naszych danych” na podkładzie ostrzeżenia (nakładka na powierzchni)', () => {
  for (const [motyw, { tokeny, ostrz_tlo }] of Object.entries(MOTYWY)) {
    for (const [nazwaTla, tlo] of powierzchnie(tokeny)) {
      const podklad = nakladka(ostrz_tlo, tlo);
      const k = kontrast(zmienna(tokeny, '--sc-text'), podklad);
      assert.ok(k >= 4.5, `${motyw}: tekst na ostrzeżeniu nad ${nazwaTla}: ${k.toFixed(2)}`);
    }
  }
});

test('kontrast 4,5:1: wyższy kontrast (prefers-contrast: more) w obu motywach', () => {
  for (const [motyw, { tokeny, znaki, text2 }] of Object.entries(MOTYWY_WIECEJ)) {
    for (const [nazwaTla, tlo] of powierzchnie(tokeny)) {
      assert.ok(kontrast(text2, tlo) >= 4.5, `${motyw}: tekst pomocniczy na ${nazwaTla}`);
      for (const nazwa of ['--tz-dziala', '--tz-blad', '--tz-luka']) {
        const k = kontrast(zmienna(znaki, nazwa), tlo);
        assert.ok(k >= 4.5, `${motyw} (więcej kontrastu): ${nazwa} na ${nazwaTla}: ${k.toFixed(2)}`);
      }
    }
  }
});

test('znaki stanu różnią się kształtem i słowem, nie tylko barwą', () => {
  const z = require('typescript').transpileModule(read(`${dir}/zrodla.ts`), { compilerOptions: { module: 1 } }).outputText;
  for (const znak of ['●', '◐', '✕', '‖']) assert.ok(z.includes(znak), znak);
  const komponent = read(`${dir}/ZdrowieZrodla.tsx`);
  assert.match(komponent, /tz-zdrowie__znak" aria-hidden="true"/, 'znak jest dekoracją');
  assert.match(komponent, /tz-zdrowie__slowo/, 'słowo niesie znaczenie');
  assert.match(read(`${dir}/ZrodloBadge.tsx`), /<svg[^>]*aria-hidden="true"/, 'etykieta łącza ma ikonę');
  assert.match(read(`${dir}/ZrodloBadge.tsx`), /<span className="tz-sr">Łącze: <\/span>/, 'czytnik ekranu czyta, czym jest etykieta');
});

// ---------- ruch, klawiatura, cele dotykowe ----------

test('prefers-reduced-motion: arkusz źródeł nie ma animacji, przejść ani przewijania płynnego', () => {
  assert.ok(!/animation|transition|@keyframes|scroll-behavior|(?<!text-)transform\s*:/i.test(CSS), 'zrodla.css nie rusza niczego');
  // a globalne wyłączenie ruchu z teraz.css nadal obowiązuje cały zakres .tz
  assert.match(TERAZ_CSS, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.tz \*/);
});

test('klawiatura: panel źródeł to natywne details/summary o wysokości celu 44 px, etykiety nie są interaktywne', () => {
  const panel = read(`${dir}/PanelZrodel.tsx`);
  assert.match(panel, /<details className="tz-zrodla__szczegoly">\s*<summary>/);
  assert.match(CSS, /\.tz-zrodla__szczegoly > summary \{[^}]*min-height: var\(--tz-tap\)/);
  assert.match(TERAZ_CSS, /--tz-tap: 44px/);
  for (const plik of ['ZrodloBadge.tsx', 'ZdrowieZrodla.tsx']) {
    const kod = read(`${dir}/${plik}`);
    assert.ok(!/tabIndex|onClick|role="button"/.test(kod), `${plik}: informacja, nie sterowanie (nie zabiera fokusu)`);
  }
  assert.ok(!/outline:\s*none/.test(CSS), 'nie zdejmujemy wskaźnika fokusu');
  // fokus summary pokrywa istniejąca reguła .tz :is(a, button, input, select, summary):focus-visible
  assert.match(TERAZ_CSS, /\.tz :is\(a, button, input, select, summary\):focus-visible/);
});

test('rozmiary: nic poniżej 12 px, etykieta łącza ma stałą wysokość, tryb wymuszonych kolorów ma obrys', () => {
  for (const m of CSS.matchAll(/font(?:-size)?:\s*(?:[0-9]+\s+)?([0-9.]+)px/g)) assert.ok(+m[1] >= 12, `font ${m[0]}`);
  assert.match(CSS, /\.tz-lacze \{[^}]*min-height: 22px/);
  assert.match(CSS, /@media \(forced-colors: active\)[\s\S]*\.tz-lacze \{ border-color: ButtonText/);
});

test('arkusz jest dołączony jednym @import na początku teraz.css (strona ma jeden arkusz, testy 144-147 bez zmian)', () => {
  const bezKomentarzy = TERAZ_CSS.replace(/\/\*[\s\S]*?\*\//g, '').trim();
  assert.ok(bezKomentarzy.startsWith("@import './zrodla.css';"), '@import przed wszystkimi regułami');
  assert.ok(!/zrodla\.css/.test(read(`${dir}/TerazPage.tsx`)), 'TerazPage nie importuje drugiego arkusza');
});

// ---------- zasady tekstu produktu ----------

const NOWE = ['zrodla.ts', 'zrodla-api.ts', 'ZrodloBadge.tsx', 'ZdrowieZrodla.tsx', 'PanelZrodel.tsx', 'dane-probne/zrodla.ts', 'zrodla.css'];
const bezKomentarzy = kod => kod.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '').replace(/\s\/\/ .*$/gm, '');

test('nowe pliki: bez długich myślników, bez „spokojnie”, „bezpiecznie” i „bez komunikatów” (komentarze cytujące zasadę pomijamy)', () => {
  for (const plik of NOWE) {
    const kod = read(`${dir}/${plik}`);
    assert.ok(!/[–—]/.test(kod), `długi myślnik w ${plik}`);
    const czysty = bezKomentarzy(kod);
    assert.ok(!/spokojn|bezpieczn/i.test(czysty), `zakazane słowo w ${plik}`);
    assert.ok(!/bez komunikat/i.test(czysty), `„bez komunikatów” w ${plik}`);
  }
});

test('nowe pliki nie dotykają Osi czasu ani Timeline (to W4)', () => {
  for (const plik of NOWE) assert.ok(!/Timeline|OsCzasu|os_czasu/.test(read(`${dir}/${plik}`)), `${plik}: bez Osi`);
});

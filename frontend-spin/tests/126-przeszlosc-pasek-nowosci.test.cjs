// przeszłość.today (13.10.2026): pasek "Ostatnio w bazie" pod menu strony głównej - funkcje czyste (pasek-nowosci-dane.ts)
// i render komponentu (PasekNowosci.tsx) z fikstur w kształcie /api/przeszlosc/start/ (latest[]). Bez nowych pakietów:
// TS przez typescript.transpileModule, render react-dom/server (jak test 125). Zachowanie w przeglądarce: tests/126-pasek-nowosci.browser.cjs.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.join(__dirname, '..');
const cache = new Map();
function load(file) {
  const abs = path.resolve(file);
  if (cache.has(abs)) return cache.get(abs).exports;
  const out = ts.transpileModule(fs.readFileSync(abs, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  cache.set(abs, module);
  const req = name => {
    if (name.endsWith('.css')) return {};
    if (name === 'react' || name === 'react/jsx-runtime') return require(name);
    if (name.startsWith('.')) {
      const base = path.resolve(path.dirname(abs), name);
      const hit = ['.tsx', '.ts'].map(x => base + x).find(f => fs.existsSync(f));
      if (hit) return load(hit);
    }
    return {};
  };
  vm.runInNewContext(out, { module, exports: module.exports, require: req, console, URL, Number, String, Math, Set, Map, Date, RegExp, JSON, setTimeout, clearTimeout, setInterval, clearInterval });
  return module.exports;
}
const P = f => path.join(root, 'app/przeszlosc', f);
const D = load(P('pasek-nowosci-dane.ts'));
const { PasekNowosci } = load(P('PasekNowosci.tsx'));
const html = props => renderToStaticMarkup(React.createElement(PasekNowosci, props));

const LATEST = [
  { title: 'Głosowanie nr 12 nad projektem ustawy o zmianie ustawy o VAT', date: '2026-10-12', kind: 'Głosowanie', url: 'https://www.sejm.gov.pl/Sejm10.nsf/agent.xsp?symbol=glosowania&NrKadencji=10&NrPosiedzenia=40&NrGlosowania=12' },
  { title: 'Druk nr 1234: rządowy projekt ustawy o CPK', date: '2026-10-13', kind: 'Druk', url: 'https://orka.sejm.gov.pl/Druki10ka.nsf/0/1234' },
  { title: 'Interpelacja nr 777 w sprawie cen energii', date: '2026-10-13', kind: 'Interpelacja', url: 'https://api.sejm.gov.pl/sejm/term10/interpellations/777' },
  { title: '   druk nr 1234: RZĄDOWY projekt ustawy o CPK ', date: '2026-10-11', kind: 'Druk', url: 'https://orka.sejm.gov.pl/dup' },
  { title: 'Posiedzenie komisji finansów publicznych', date: null, kind: 'Komisja', url: 'javascript:alert(1)' },
  { title: '', date: '2026-10-13', kind: 'Druk', url: 'https://sejm.gov.pl/x' },
  { title: 'Uchwała Senatu w sprawie ustawy o KPO', date: '2026-10-10', kind: 'Senat', url: 'https://www.senat.gov.pl/prace/uchwaly/1' },
  { title: 'Projekt rozporządzenia w RCL', date: '2026-10-09', kind: 'Projekt rządowy', url: 'https://legislacja.rcl.gov.pl/projekt/1' },
  { title: 'Siódma pozycja poza zakresem paska', date: '2026-10-08', kind: 'Dokument', url: 'https://sejm.gov.pl/7' },
];

test('dane: sortowanie po czasie malejąco (stabilne), bez duplikatów tytułu, pusty tytuł odpada, najwyżej 6 pozycji', () => {
  const items = D.tickItems(LATEST);
  assert.equal(items.length, 6);
  // tablice z innego kontekstu vm mają inny prototyp: porównanie przez JSON (jak w teście 121)
  assert.equal(JSON.stringify(items.map(i => i.date)), JSON.stringify(['2026-10-13', '2026-10-13', '2026-10-12', '2026-10-10', '2026-10-09', '2026-10-08']));
  assert.equal(items[0].kind, 'Druk', 'przy tej samej dacie zostaje kolejność z API');
  assert.equal(items[1].kind, 'Interpelacja');
  assert.ok(!items.some(i => /komisji/.test(i.title)), 'wiersz bez daty sortuje się na koniec i wypada poza 6');
  assert.ok(items.some(i => /Siódma/.test(i.title)), 'po odrzuceniu duplikatu zwalnia się miejsce dla kolejnej pozycji z datą');
  assert.equal(items.filter(i => /CPK/.test(i.title)).length, 1, 'duplikat tytułu (inna wielkość liter i spacje) odpada');
  assert.equal(items[0].title, 'Druk nr 1234: rządowy projekt ustawy o CPK');
  assert.equal(D.tickItems(null).length, 0); assert.equal(D.tickItems(undefined).length, 0);
});

test('dane: data i godzina tylko z danych, domena źródła, bezpieczny adres', () => {
  assert.equal(D.tickDate('2026-10-13'), '13.10.2026'); assert.equal(D.tickDate('2026-10-13T06:29+00:00'), '13.10.2026'); assert.equal(D.tickDate(null), '');
  assert.equal(D.tickTime('2026-10-13'), '', 'sama data = bez godziny (nie zmyślamy)'); assert.equal(D.tickTime('2026-10-13T06:29:00Z'), '06:29');
  assert.equal(D.tickHost('https://www.sejm.gov.pl/x'), 'sejm.gov.pl'); assert.equal(D.tickHost('https://api.sejm.gov.pl/x'), 'sejm.gov.pl'); assert.equal(D.tickHost('/lokalny'), '');
  assert.equal(D.tickUrl('javascript:alert(1)'), null); assert.equal(D.tickUrl('//evil.example'), null); assert.equal(D.tickUrl('https://sejm.gov.pl/x'), 'https://sejm.gov.pl/x');
  const bad = D.tickItems([{ title: 'A', date: '2026-01-01', kind: 'Druk', url: 'javascript:alert(1)' }]);
  assert.equal(bad[0].url, null); assert.equal(bad[0].host, '');
});

test('dane: zakres 3-6, krok w pętli, stany paska, czas z tokenów CSS', () => {
  assert.equal(D.TICK_MIN, 3); assert.equal(D.TICK_MAX, 6);
  assert.equal(D.tickVisible(D.tickItems(LATEST.slice(0, 2))), false, 'mniej niż 3 pozycje = pasek ukryty');
  assert.equal(D.tickVisible(D.tickItems(LATEST.slice(0, 3))), true);
  assert.equal(D.stepIndex(5, 6), 0); assert.equal(D.stepIndex(0, 6, -1), 5); assert.equal(D.stepIndex(0, 0), 0);
  const base = { reduced: false, paused: false, hovered: false, focused: false, hidden: false, n: 6 };
  assert.equal(D.tickState(base), 'running');
  assert.equal(D.tickState({ ...base, paused: true }), 'paused');
  assert.equal(D.tickState({ ...base, hovered: true }), 'paused');
  assert.equal(D.tickState({ ...base, focused: true }), 'paused');
  assert.equal(D.tickState({ ...base, hidden: true }), 'paused', 'karta w tle = bez zegara');
  assert.equal(D.tickState({ ...base, reduced: true }), 'static');
  assert.equal(D.tickState({ ...base, n: 1 }), 'static');
  assert.equal(D.readMs('6s', 1), 6000); assert.equal(D.readMs(' 320ms ', 1), 320); assert.equal(D.readMs('6000', 1), 6000);
  assert.equal(D.readMs('', 7), 7); assert.equal(D.readMs(undefined, 7), 7); assert.equal(D.readMs('abc', 7), 7); assert.equal(D.readMs('-5ms', 7), 7);
});

test('dane: skrót tytułu po całym słowie z pomiarem (nigdy w pół słowa), null gdy się mieści, po znakach gdy nie mieści się pierwsze słowo', () => {
  const m = s => s.length * 10; // 10 px na znak
  assert.equal(D.fitWords('Druk nr 1234: rządowy projekt', 1000, m), null);
  assert.equal(D.fitWords('Druk nr 1234: rządowy projekt', 160, m), 'Druk nr 1234…', 'po "1234" odpada dwukropek, wielokropek mieści się w 16 znakach');
  assert.equal(D.fitWords('Druk nr 1234: rządowy projekt', 220, m), 'Druk nr 1234: rządowy…');
  assert.equal(D.fitWords('Druk nr 1234: rządowy projekt', 80, m), 'Druk nr…');
  assert.equal(D.fitWords('Niepodzielnesłowo dalej', 60, m), 'Niepo…', 'pierwsze słowo za długie: po znakach');
  assert.equal(D.fitWords('abc', 0, m), null, 'brak szerokości (przed układem) = bez skrótu');
});

test('render: region z etykietą, aria-live="off", pierwsza pozycja z rodzajem, datą, tytułem w jednej linii (title) i źródłem; Pauza (aria-pressed=false); odnośnik do #najnowsze', () => {
  const h = html({ latest: LATEST });
  assert.match(h, /<section class="pt-tick" role="region" aria-label="Ostatnio w bazie" data-state="running"/);
  assert.match(h, /aria-live="off"/);
  assert.doesNotMatch(h, /aria-live="(polite|assertive)"/);
  assert.match(h, /class="pt-tick__kind">Druk</);
  assert.match(h, /<time class="pt-tick__time" date[Tt]ime="2026-10-13"><span class="pt-tick__d-full">13\.10\.2026<\/span><span class="pt-tick__d-short" aria-hidden="true">13\.10<\/span><\/time>/);
  assert.match(h, /class="pt-tick__title" title="Druk nr 1234: rządowy projekt ustawy o CPK"><span class="pt-tick__t">Druk nr 1234: rządowy projekt ustawy o CPK<\/span><\/span>/, 'przed pomiarem pełny tytuł, bez atrybutu data-cut');
  // domena źródła jak w danych (bez www/api), reszta subdomen zostaje
  assert.match(h, /<a class="pt-tick__src" href="https:\/\/orka\.sejm\.gov\.pl\/Druki10ka\.nsf\/0\/1234" target="_blank" rel="noopener noreferrer"[^>]*><span class="pt-tick__srcname">orka\.sejm\.gov\.pl<\/span>/);
  // Pauza jako sama ikona: nazwa w aria-label i title (uwaga właściciela 13.10: jedna linia bazowa wiersza)
  assert.match(h, /<button type="button" class="px-tool pt-tick__btn" aria-pressed="false" aria-label="Zatrzymaj zmianę pozycji" title="Pauza">/);
  assert.doesNotMatch(h, /Następna/);
  assert.doesNotMatch(h, /pt-tick__n|1\/6/, 'bez licznika pozycji (panel 13.10: za dużo elementów w jednej linii)');
  assert.match(h, /<a class="px-link pt-tick__all" href="#najnowsze"><span class="pt-tick__txt">Wszystkie nowości<\/span><i aria-hidden="true">→<\/i><\/a>/);
  assert.match(h, /class="pt-tick__lab"><span class="pt-tick__lab-t">Ostatnio w bazie<\/span> <i aria-hidden="true">&gt;<\/i>/, '">" jako zwykły tekst w etykiecie');
  // bez ocen i słów zależności: tylko to, co w danych
  assert.doesNotMatch(h, /najważniejsz|alarm|ważne|zależn|związan/i);
});

test('render: brak danych i błąd = brak paska (nie "zero"); mniej niż 3 pozycje = brak paska; ładowanie = szkielet tej samej klasy wysokości', () => {
  assert.equal(html({ latest: [] }), '');
  assert.equal(html({ latest: null }), '');
  assert.equal(html({ latest: undefined }), '');
  assert.equal(html({ latest: LATEST.slice(0, 2) }), '');
  const sk = html({ latest: undefined, loading: true });
  assert.match(sk, /<section class="pt-tick" role="region" aria-label="Ostatnio w bazie" aria-busy="true" data-state="loading">/);
  assert.match(sk, /class="pt-tick__sk" aria-hidden="true"/);
  assert.doesNotMatch(sk, /<button|pt-tick__all/, 'szkielet bez przycisków');
  assert.equal(html({ latest: [], loading: false }), '', 'po odpowiedzi bez pozycji pasek znika');
});

test('render: prefers-reduced-motion = pozycja statyczna i przycisk "Następna" zamiast Pauzy', () => {
  const h = html({ latest: LATEST, reduced: true });
  assert.match(h, /data-state="static"/);
  assert.match(h, /aria-label="Następna pozycja" title="Następna pozycja"/); assert.doesNotMatch(h, /Pauza|aria-pressed/);
  assert.match(h, /class="pt-tick__kind">Druk</, 'pierwsza pozycja');
});

test('pliki: tokeny czasu w CSS, tylko transform/opacity w animacji, reduced motion, wysokość stała, sekcja #najnowsze i pasek w TopicTree', () => {
  const css = fs.readFileSync(P('pasek-nowosci.css'), 'utf8');
  for (const tok of ['--fx-ticker-interval: 6000ms', '--fx-ticker-fade: 320ms', '--fx-ticker-shift: 4px', '--pt-tick-h: 40px', '--pt-tick-lh: 1.3']) assert.ok(css.includes(tok), tok);
  assert.match(css, /height: var\(--pt-tick-h\)/);
  assert.match(css, /\.pt-tick \{[^}]*align-items: baseline/, 'wiersz po linii bazowej (uwaga właściciela 13.10)');
  assert.match(css, /\.pt-tick__title \{[^}]*flex: 1 1 0px; min-width: 0/, 'tytuł bierze całą wolną szerokość');
  assert.match(css, /max-width: 1099\.98px\) \{ \.pt-v3 \.px \.pt-tick__src \{ display: none; \}/, 'domena znika poniżej 1100 px');
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /scrollbar|overflow: hidden/, 'ucięcie bez paska przewijania');
  const anim = css.match(/@keyframes pt-tick-in \{[^}]*\}[^}]*\}/)[0];
  assert.doesNotMatch(anim, /width|height|margin|left|top:/, 'animacja tylko opacity + transform');
  const tree = fs.readFileSync(P('TopicTree.tsx'), 'utf8');
  assert.match(tree, /<PasekNowosci latest=\{start\?\.latest\} loading=\{!start && !startFailed\} \/>/);
  assert.match(tree, /id="najnowsze"/);
  assert.match(tree, /Najnowsze w&nbsp;bazie/);
  assert.match(tree, /catch\(\(\) => setStartFailed\(true\)\)/, 'błąd API = pasek znika');
});

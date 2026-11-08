// Seria 2 (13.10.2026): kontrakt API v3 na froncie i nowe komponenty v3.
// Uruchom: node --test src/lib/*.test.mjs (z katalogu packages/ui). Transpilacja TS/TSX typescriptem z frontend-spin, render react-dom/server.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const require = createRequire(new URL('../../../../frontend-spin/package.json', import.meta.url));
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

/** Ładuje moduł TS/TSX jako CommonJS; importy spoza listy dostają pusty obiekt (testujemy tylko funkcje bez zależności). */
function load(rel, mocks = {}, env = {}) {
  const src = readFileSync(new URL(rel, import.meta.url), 'utf8');
  const out = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  const req = name => mocks[name] ?? (name === 'react' || name === 'react/jsx-runtime' ? require(name) : {});
  vm.runInNewContext(out, { module, exports: module.exports, require: req, process: { env }, URL, Intl, console });
  return module.exports;
}

test('messageSpinStrength: brak klucza, null i n < 3 = nic; poprawna wartość przechodzi', () => {
  const { messageSpinStrength } = load('./clinic.ts');
  assert.equal(messageSpinStrength(null), null);
  assert.equal(messageSpinStrength({}), null);
  assert.equal(messageSpinStrength({ spin_strength: null }), null);
  assert.equal(messageSpinStrength({ spin_strength: { value: 50, n: 2, method: 'm' } }), null);
  assert.equal(messageSpinStrength({ spin_strength: { value: Number.NaN, n: 5, method: 'm' } }), null);
  assert.deepEqual(messageSpinStrength({ spin_strength: { value: 62, n: 7, method: 'm' } }), { value: 62, n: 7, method: 'm' });
});

const STEPS = [
  { kind: 'fakt', text: 'Ministerstwo opublikowało projekt.', source: { name: '@ministerstwo na X', url: 'https://x.com/m/status/1', date: '2026-10-12' } },
  { kind: 'interpretacja', text: 'Wpisy przedstawiają projekt jako przesądzony.' },
  { kind: 'interpretacja', text: 'Krok bez źródła.', degraded: true },
  { kind: 'spin', text: 'Pomija się konsultacje.', technique: 'Pominięcie kontekstu' },
  { kind: 'wniosek', text: 'Odbiorca dostaje obraz decyzji, której nie ma.' },
];

test('approvedChainSteps: tylko zatwierdzony, 3-5 kroków, fakt ze źródłem', () => {
  const { approvedChainSteps, isCausalChainValid } = load('../kit/CausalChain.tsx');
  assert.equal(approvedChainSteps(undefined), null);
  assert.equal(approvedChainSteps(null), null);
  assert.equal(approvedChainSteps({ approved_at: null, steps: STEPS }), null, 'niezatwierdzony');
  assert.equal(approvedChainSteps({ approved_at: '2026-10-13T09:41:00+02:00', steps: STEPS.slice(0, 2) }), null, 'za mało kroków');
  assert.equal(approvedChainSteps({ approved_at: 'x', steps: [...STEPS, STEPS[1]] }), null, 'więcej niż 5');
  assert.equal(isCausalChainValid([{ kind: 'fakt', text: 'bez źródła' }, STEPS[1], STEPS[4]]), false, 'fakt bez źródła');
  assert.equal(isCausalChainValid([{ kind: 'opinia', text: 'zły rodzaj' }, STEPS[1], STEPS[4]]), false, 'nieznany rodzaj');
  assert.equal(approvedChainSteps({ approved_at: 'x', steps: STEPS }).length, 5);
});

test('CausalChain: bez flagi nic; z flagą kroki, źródło faktu jako odnośnik http(s), krok zdegradowany opisany', () => {
  const off = load('../kit/CausalChain.tsx', {}, {});
  assert.equal(renderToStaticMarkup(React.createElement(off.CausalChain, { steps: STEPS })), '');
  const on = load('../kit/CausalChain.tsx', {}, { NEXT_PUBLIC_CAUSAL_CHAIN: 'true' });
  const html = renderToStaticMarkup(React.createElement(on.CausalChain, { steps: STEPS }));
  assert.match(html, /<ol class="sc-v3-steps"/);
  assert.equal((html.match(/<li /g) || []).length, 5);
  assert.match(html, /href="https:\/\/x\.com\/m\/status\/1"[^>]*target="_blank"[^>]*rel="noopener noreferrer"/);
  assert.match(html, /brak źródła w materiałach/);
  const unsafe = renderToStaticMarkup(React.createElement(on.CausalChain, { steps: [{ ...STEPS[0], source: { name: 'x', url: 'javascript:alert(1)' } }, STEPS[1], STEPS[4]] }));
  assert.doesNotMatch(unsafe, /javascript:/);
});

test('SpinMeter: liczba w strefie, title i aria-label z objaśnieniem, bez linii w trybie bare', () => {
  const scale = load('./spinScale.ts');
  const { SpinMeter } = load('../kit/SpinMeter.tsx', { '../lib/spinScale': scale });
  const html = renderToStaticMarkup(React.createElement(SpinMeter, { value: 72, bare: true, label: 'Siła spinu dnia', title: 'Siła spinu dnia: 72/100 - mediana z 7 diagnoz' }));
  assert.match(html, /data-zone="hi"/);
  assert.match(html, /title="Siła spinu dnia: 72\/100 - mediana z 7 diagnoz"/);
  assert.match(html, /aria-label="Siła spinu dnia: 72\/100 - mediana z 7 diagnoz"/);
  assert.doesNotMatch(html, /sc-v3-meter__line/);
  assert.match(renderToStaticMarkup(React.createElement(SpinMeter, { value: 20, bare: true })), /data-zone="lo"/);
});

test('SideLegend: słowo strony zawsze obok koloru, dopisek "nie siłę spinu"', () => {
  const clinic = { CAMPS: ['government', 'opposition'], CAMP_LABELS: { government: 'Rządzący', opposition: 'Opozycja' } };
  const { SideLegend } = load('../kit/SideLegend.tsx', { '../lib/clinic': clinic });
  const html = renderToStaticMarkup(React.createElement(SideLegend));
  assert.match(html, /data-side="government"[^>]*>.*Rządzący/);
  assert.match(html, /data-side="opposition"[^>]*>.*Opozycja/);
  assert.match(html, /kolor oznacza stronę, nie siłę spinu/);
});

test('wywiady: interviewScore pomija niepewną skalę 0-10 i brak wyniku', () => {
  const { interviewScore, suspectScale } = load('../components/clinic/InterviewsV3.tsx');
  assert.equal(interviewScore({ verdict: 'spin', intensity: 75 }), 75);
  assert.equal(interviewScore({ verdict: 'spin', intensity: 8 }), null);
  assert.equal(suspectScale({ verdict: 'no_spin', intensity: 8 }), false);
  assert.equal(interviewScore({ verdict: 'no_spin', intensity: 8 }), 8);
  assert.equal(interviewScore({ verdict: undefined, intensity: undefined }), null);
});

test('numChars: najdłuższa liczba ze spacjami tysięcy, minimum 4', () => {
  const { numChars } = load('../kit/home/HomeV3.tsx');
  assert.equal(numChars([9037, 191, 165]), 4); // pl-PL: spacja tysięcy dopiero od 10 000 ("9037")
  assert.equal(numChars([12345]), 6);
  assert.equal(numChars([1387695]), '1 387 695'.length);
  assert.equal(numChars([]), 4);
  assert.equal(numChars([undefined, 12]), 4);
});

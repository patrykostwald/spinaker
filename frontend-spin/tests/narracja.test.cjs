const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../app/przeszlosc/narracja.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const mod = { exports: {} };
new Function('module', 'exports', 'require', code)(mod, mod.exports, require);
const { resolveNarrative, narrativeSearch, stripDiagnoses, createNarrativeStore } = mod.exports;

const env = (search = '', stored = null) => {
  const log = { stored, url: search, writes: [] };
  return { log, env: { search: () => log.url, read: () => log.stored, write: v => { log.stored = v; log.writes.push(v); }, replaceSearch: s => { log.url = s; } } };
};

test('warstwa narracji jest domyślnie wyłączona', () => {
  assert.equal(resolveNarrative('', null), false);
  assert.equal(resolveNarrative('?q=CPK', '0'), false);
  assert.equal(createNarrativeStore(env().env).get(), false);
});

test('parametr ?narracja ma pierwszeństwo przed zapamiętanym wyborem', () => {
  assert.equal(resolveNarrative('?narracja=1', null), true);
  assert.equal(resolveNarrative('?q=a&narracja=1', '0'), true);
  assert.equal(resolveNarrative('?narracja=0', '1'), false);
  assert.equal(resolveNarrative('', '1'), true);
});

test('adres po przełączeniu zachowuje resztę parametrów', () => {
  assert.equal(narrativeSearch('?q=CPK', true), '?q=CPK&narracja=1');
  assert.equal(narrativeSearch('?q=CPK&narracja=1', false), '?q=CPK');
  assert.equal(narrativeSearch('?narracja=1', false), '');
});

test('sklep zapamiętuje wybór, zmienia adres i powiadamia słuchaczy', () => {
  const { log, env: e } = env('?q=CPK');
  const store = createNarrativeStore(e);
  let calls = 0; const un = store.subscribe(() => { calls += 1; });
  store.set(true);
  assert.equal(store.get(), true); assert.equal(log.stored, '1'); assert.equal(log.url, '?q=CPK&narracja=1'); assert.equal(calls, 1);
  store.set(true); assert.equal(calls, 1);
  store.set(false);
  assert.equal(log.stored, '0'); assert.equal(log.url, '?q=CPK'); assert.equal(calls, 2);
  un(); store.set(true); assert.equal(calls, 2);
});

test('sklep działa bez localStorage (tryb prywatny)', () => {
  const store = createNarrativeStore({ search: () => '', read: () => { throw new Error('x'); }, write: () => { throw new Error('x'); }, replaceSearch: () => { throw new Error('x'); } });
  assert.equal(store.get(), false); store.set(true); assert.equal(store.get(), true);
});

test('stripDiagnoses usuwa węzły, krawędzie i licznik diagnoz, resztę zostawia', () => {
  const g = { topic: 'x', counts: { statement: 2, diagnosis: 1, person: 1 },
    nodes: [{ id: 'p', kind: 'person' }, { id: 's', kind: 'statement' }, { id: 'd', kind: 'diagnosis' }, { id: 'o', kind: 'organisation' }],
    edges: [{ source: 'p', target: 's', label: 'napisał(a)' }, { source: 's', target: 'd', label: 'diagnoza Dr. Spina' }, { source: 'p', target: 'o', label: 'prezes' }] };
  const r = stripDiagnoses(g);
  assert.deepEqual(r.nodes.map(n => n.id), ['p', 's', 'o']);
  assert.deepEqual(r.edges.map(e => e.target), ['s', 'o']);
  assert.equal('diagnosis' in r.counts, false); assert.equal(r.counts.statement, 2);
  assert.equal(g.nodes.length, 4); // wejście nietknięte
  const clean = { nodes: [{ id: 'p', kind: 'person' }], edges: [], counts: { person: 1 } };
  assert.equal(stripDiagnoses(clean), clean);
});

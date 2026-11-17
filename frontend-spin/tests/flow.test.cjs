const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const fixture = require('./flow.fixture.cjs');
const mod = { exports: {} };
new Function('module', 'exports', ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../app/przeszlosc/flow.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)(mod, mod.exports);
const { parseFlow, readFilters, visibleFlow, flowLayout, flowQuery, edgeWidth, safeHref } = mod.exports;
test('parsuje dokładne pola kontraktu i odrzuca niepoprawne węzły/krawędzie', () => {
  assert.equal(parseFlow(fixture).edges[0].from, 'root');
  for (const change of [d => d.nodes[0].level = 4, d => delete d.nodes[0].source.license, d => d.edges[0].to = 'missing', d => d.nodes.push(d.nodes[0]), d => d.categories.pop()]) {
    const data = structuredClone(fixture); change(data); assert.throws(() => parseFlow(data));
  }
});
test('deterministyczne rzędy level 0..3, równe odległości i brak kolizji', () => {
  const a = flowLayout(fixture.nodes), b = flowLayout([...fixture.nodes].reverse());
  assert.deepEqual(a, b);
  for (let level = 0; level < 4; level++) {
    const row = a.nodes.filter(p => p.node.level === level);
    assert.equal(new Set(row.map(p => p.y)).size, 1);
    for (let i = 1; i < row.length; i++) assert.equal(row[i].x - row[i - 1].x, 276);
  }
});
test('polityka obejmuje media, korzeń zostaje, pusty wybór usuwa gałęzie', () => {
  const filters = readFilters('?kategorie=polityka');
  const data = visibleFlow(fixture, filters, false);
  assert(data.nodes.some(n => n.kind === 'media'));
  assert(data.nodes.every(n => n.id === 'root' || ['polityka', 'media'].includes(n.category)));
  assert.deepEqual(visibleFlow(fixture, readFilters('?kategorie='), false).nodes.map(n => n.id), ['root']);
});
test('narracja=0 usuwa diagnozy, ich krawędzie, oś i grupy', () => {
  const data = structuredClone(fixture); data.limits.grouped = [{ id: 'g', kind: 'diagnosis', category: 'media', label: 'Diagnozy', count: 5 }];
  const off = visibleFlow(data, readFilters(''), false), on = visibleFlow(data, readFilters(''), true);
  assert(!off.nodes.some(n => n.kind === 'diagnosis')); assert(!off.edges.some(e => e.to === 'diagnoza'));
  assert(!off.timeline.some(t => t.node_id === 'diagnoza')); assert.equal(off.limits.grouped.length, 0);
  assert(on.nodes.some(n => n.kind === 'diagnosis'));
  assert.equal(new URLSearchParams(flowQuery(readFilters(''), false)).get('narracja'), '0');
});
test('daty, name_only i anonimizacja działają obronnie', () => {
  const data = structuredClone(fixture); data.nodes.find(n => n.id === 'anon').label = 'Nie ujawniaj';
  const graph = visibleFlow(data, readFilters('?od=2025-01-01&do=2025-12-31'), false);
  assert(!graph.nodes.some(n => n.id === 'nazwa')); assert(!graph.nodes.some(n => n.id === 'odbiorca'));
  assert.equal(graph.nodes.find(n => n.id === 'anon').label, 'osoba fizyczna');
  assert(visibleFlow(data, readFilters('?pokaz_niepowiazane=1'), false).nodes.some(n => n.id === 'nazwa'));
});
test('300 węzłów mieści się w deterministycznym układzie, kwoty i bezpieczne URL', () => {
  const nodes = Array.from({ length: 300 }, (_, i) => ({ ...fixture.nodes[0], id: String(i), level: i % 4 }));
  assert.equal(flowLayout(nodes).nodes.length, 300);
  assert(edgeWidth(1000000) > edgeWidth(100)); assert(edgeWidth(1000000) < edgeWidth(100) * 10000);
  assert.equal(safeHref('javascript:alert(1)'), undefined); assert.equal(safeHref('//example.org'), undefined);
  assert.equal(safeHref('/przeszlosc'), '/przeszlosc');
});

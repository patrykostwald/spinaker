const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const routing = require('../lib/threadsRouting');

function load(file, env, mocks = {}, globals = {}) {
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, process: { env },
    require: name => Object.hasOwn(mocks, name) ? mocks[name] : require(path.resolve(__dirname, name)),
    URL, Date, ...globals,
  });
  return exports;
}
const spinkaSource = value => /spinki|nitki|tropy/.test(value);

test('isThreadsEnabled reads only the exact string "true"', () => {
  assert.equal(routing.isThreadsEnabled({ NEXT_PUBLIC_THREADS_ENABLED: 'true' }), true);
  for (const value of [undefined, '', 'false', '1', 'TRUE']) assert.equal(routing.isThreadsEnabled({ NEXT_PUBLIC_THREADS_ENABLED: value }), false);
});

test('flag true: legacy addresses redirect to /spinki as before (permanent)', () => {
  const rows = routing.threadRedirects(true);
  assert.equal(rows.length, 6);
  assert.ok(rows.every(row => row.permanent === true && !row.has && !row.missing));
  assert.deepEqual(rows.find(row => row.source === '/tropy'), { source: '/tropy', destination: '/spinki', permanent: true });
  assert.deepEqual(rows.find(row => row.source === '/konto/nitki/:path*'), { source: '/konto/nitki/:path*', destination: '/konto/spinki/:path*', permanent: true });
  assert.equal(rows.find(row => row.source === '/spinki'), undefined, '/spinki stays a real route');
});

test('flag false: every spinki, nitki and tropy address goes to /klinika, never to /spinki', () => {
  const rows = routing.threadRedirects(false);
  const guarded = rows.filter(row => row.missing);
  const sources = guarded.map(row => row.source);
  for (const source of ['/spinki', '/spinki/:path*', '/nitki', '/nitki/:path*', '/tropy', '/tropy/:path*', '/konto/spinki', '/konto/spinki/:path*', '/konto/nitki/:path*', '/konto/tropy/:path*']) {
    assert.ok(sources.includes(source), source);
  }
  assert.ok(guarded.every(row => row.destination === '/klinika' && row.permanent === false));
  assert.ok(guarded.every(row => row.missing[0].key === 'sc_preview' && row.missing[0].value === '1'));
  // podgląd: stare nazwy dalej do /spinki, ale nigdy łańcuch /nitki -> /spinki -> /klinika dla zwykłych użytkowników
  const preview = rows.filter(row => row.has);
  assert.ok(preview.every(row => row.destination.startsWith('/spinki') && row.has[0].key === 'sc_preview' && row.permanent === false));
});

test('next.config.js builds redirects from the flag at build time', async () => {
  for (const [flag, expectTarget] of [['true', '/spinki'], ['false', '/klinika'], [undefined, '/klinika']]) {
    const saved = process.env.NEXT_PUBLIC_THREADS_ENABLED;
    if (flag === undefined) delete process.env.NEXT_PUBLIC_THREADS_ENABLED; else process.env.NEXT_PUBLIC_THREADS_ENABLED = flag;
    delete require.cache[require.resolve('../next.config.js')];
    const config = require('../next.config.js');
    const rows = await config.redirects();
    if (saved === undefined) delete process.env.NEXT_PUBLIC_THREADS_ENABLED; else process.env.NEXT_PUBLIC_THREADS_ENABLED = saved;
    const nitki = rows.find(row => row.source === '/nitki' && !row.has);
    assert.equal(nitki.destination, expectTarget);
    assert.ok(rows.some(row => row.source === '/szukaj'), 'unrelated redirects stay');
  }
});

test('manifest: installable fields stay valid and shortcuts follow the flag', () => {
  for (const [flag, names] of [['true', ['Klinika', 'Wiadomości', 'Spinki']], ['false', ['Klinika', 'Przekazy dnia', 'Wiadomości']]]) {
    const manifest = load('../app/manifest.ts', { NEXT_PUBLIC_THREADS_ENABLED: flag }, { '../lib/threadsRouting': { ...routing, isThreadsEnabled: () => routing.isThreadsEnabled({ NEXT_PUBLIC_THREADS_ENABLED: flag }) } }).default();
    assert.deepEqual(manifest.shortcuts.map(item => item.name), names);
    assert.equal(spinkaSource(JSON.stringify(manifest.shortcuts)), flag === 'true' ? true : false);
    assert.equal(manifest.display, 'standalone');
    assert.equal(manifest.start_url, '/');
    assert.equal(manifest.scope, '/');
    assert.equal(manifest.theme_color, '#000000');
    assert.equal(JSON.stringify(manifest.categories), '["news"]');
    assert.ok(manifest.name && manifest.short_name);
    for (const size of ['192x192', '512x512']) {
      assert.ok(manifest.icons.some(icon => icon.sizes === size && icon.purpose === 'any'), `any ${size}`);
      assert.ok(manifest.icons.some(icon => icon.sizes === size && icon.purpose === 'maskable'), `maskable ${size}`);
    }
    for (const icon of manifest.icons) assert.ok(fs.existsSync(path.join(__dirname, '../public', icon.src)), icon.src);
    for (const item of manifest.shortcuts) assert.ok(item.url.startsWith('/'));
  }
});

test('sitemap never lists spinki addresses', async () => {
  for (const flag of ['true', 'false']) {
    const sitemap = load('../app/sitemap.ts', { NEXT_PUBLIC_THREADS_ENABLED: flag }, {}, { fetch: async () => ({ ok: false }) }).default;
    const rows = await sitemap();
    assert.ok(rows.length > 10);
    assert.ok(rows.every(row => !spinkaSource(row.url)), flag);
  }
});

test('PwaControls offers the nitki-dr-spina topic only with the flag on', () => {
  const source = fs.readFileSync(path.join(__dirname, '../app/PwaControls.tsx'), 'utf8');
  assert.match(source, /threadsEnabled \? allTopics : allTopics\.filter\(\(\[key\]\) => key !== THREAD_TOPIC\)/);
  assert.match(source, /filter\(topic => threadsEnabled \|\| topic !== THREAD_TOPIC\)/);
});

test('offline page has no link to a spinki route', () => {
  const html = fs.readFileSync(path.join(__dirname, '../public/app/offline.html'), 'utf8');
  assert.ok(!/href="\/(nitki|spinki|tropy)/.test(html));
});

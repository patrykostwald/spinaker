const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToString } = require('react-dom/server');

function load(file, globals = {}, mocks = {}) {
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, process: { env: {} },
    require: name => Object.hasOwn(mocks, name) ? mocks[name] : require(name),
    ...globals,
  });
  return exports;
}

test('preview SSR and first browser render agree for all four flags', () => {
  for (const document of [undefined, { cookie: 'sc_preview=1' }]) {
    const features = load('../../packages/ui/src/lib/features.ts', { document });
    function Flags() {
      return React.createElement('span', null, ['ACCOUNTS_ENABLED', 'THREADS_ENABLED', 'PUSH_ENABLED', 'APP_ENABLED']
        .map(name => String(features.useFeature(name))).join(','));
    }
    assert.equal(renderToString(React.createElement(Flags)), '<span>false,false,false,false</span>');
    assert.equal(features.isPreview(), !!document);
    assert.equal(features.ACCOUNTS_ENABLED, !!document);
  }
});

test('cookie matching does not accept similarly named or valued cookies', () => {
  for (const cookie of ['sc_preview=10', 'other_sc_preview=1', 'sc_preview_sig=1', 'sc_preview=0']) {
    const features = load('../../packages/ui/src/lib/features.ts', { document: { cookie } });
    assert.equal(features.isPreview(), false);
  }
});

test('server gates and verified landing page forward Django signature unchanged without caching', async () => {
  const values = new Map();
  let calls = 0;
  let active = true;
  const features = load('../lib/features.ts', {
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, 'http://localhost:8000/api/preview/status/');
      assert.equal(options.headers.Cookie, 'sc_preview_sig=abc:timestamp:signature');
      assert.equal(options.cache, 'no-store');
      return { ok: true, json: async () => ({ active }) };
    },
  }, { 'server-only': {}, 'next/headers': { cookies: async () => ({ get: key => values.has(key) ? { value: values.get(key) } : undefined }) } });
  assert.equal(await features.serverFeature('ACCOUNTS_ENABLED'), false);
  assert.equal(await features.serverFeature('THREADS_ENABLED'), false);
  assert.equal(await features.verifiedPreview(), false);
  values.set('sc_preview', '1');
  assert.equal(await features.serverFeature('ACCOUNTS_ENABLED'), true);
  assert.equal(await features.serverFeature('THREADS_ENABLED'), true);
  assert.equal(await features.verifiedPreview(), false);
  assert.equal(calls, 0);
  values.set('sc_preview_sig', 'abc:timestamp:signature');
  assert.equal(await features.verifiedPreview(), true);
  active = false;
  assert.equal(await features.verifiedPreview(), false);
  values.set('sc_preview_sig', 'invalid\r\nCookie: injected');
  assert.equal(await features.verifiedPreview(), false);
  assert.equal(calls, 2);
});

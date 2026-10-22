const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../app/klinika/[id]/page.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function metadata(data, ok = true) {
  const module = { exports: {} };
  const fetch = async (url, options) => {
    assert.equal(url.endsWith('/api/clinic/spins/65/'), true);
    assert.equal(options.cache, 'no-store');
    return { ok, json: async () => data };
  };
  new Function('module', 'exports', 'require', 'fetch', code)(module, module.exports, () => ({}), fetch);
  return module.exports.generateMetadata({ params: { id: '65' } });
}

test('withdrawn detail metadata is noindex and contains no verdict or card', async () => {
  const result = await metadata({ status: 'withdrawn', headline: 'NIE PUBLIKUJ', verdict_label: 'Spin', summary: 'NIE PUBLIKUJ' });
  assert.equal(result.robots.index, false);
  assert.deepEqual(result.openGraph.images, []);
  assert.deepEqual(result.twitter.images, []);
  assert(!JSON.stringify(result).includes('NIE PUBLIKUJ'));
});

test('hidden or unavailable detail metadata is noindex', async () => {
  assert.equal((await metadata({}, false)).robots.index, false);
});

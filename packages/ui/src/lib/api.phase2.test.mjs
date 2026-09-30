import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../../../../frontend-spin/package.json', import.meta.url));
const ts = require('typescript');
const code = ts.transpileModule(readFileSync(new URL('./api.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { apiWrite, ApiError } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);

test('missing mutation endpoint retains 404, including non-JSON responses', async () => {
  const original = globalThis.fetch;
  try {
    let calls = 0;
    globalThis.fetch = async () => ++calls === 1
      ? new Response(JSON.stringify({ csrfToken: 'test-token' }))
      : new Response('<html>Not deployed</html>', { status: 404 });
    await assert.rejects(apiWrite('/api/account/follows/', { kind: 'figure', target_id: 12 }), error => error instanceof ApiError && error.status === 404);
    assert.equal(calls, 2);
  } finally { globalThis.fetch = original; }
});

test('validation errors retain their HTTP status and explanation', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async path => path.endsWith('/csrf/')
      ? new Response(JSON.stringify({ csrfToken: 'test-token' }))
      : new Response(JSON.stringify({ detail: 'Email verification required' }), { status: 403 });
    await assert.rejects(apiWrite('/api/account/me/', {}, 'PATCH'), error => error instanceof ApiError && error.status === 403 && error.message === 'Email verification required');
  } finally { globalThis.fetch = original; }
});

test('DELETE sends session and CSRF and accepts an empty 204 response', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (path, options) => {
      if (path.endsWith('/csrf/')) return new Response(JSON.stringify({ csrfToken: 'test-token' }));
      assert.equal(options.method, 'DELETE');
      assert.equal(options.credentials, 'include');
      assert.equal(options.headers['X-CSRFToken'], 'test-token');
      return new Response(null, { status: 204 });
    };
    assert.equal(await apiWrite('/api/account/follows/1/', {}, 'DELETE'), undefined);
  } finally { globalThis.fetch = original; }
});

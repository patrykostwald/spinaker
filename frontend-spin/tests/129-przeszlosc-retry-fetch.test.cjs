// przeszłość.today: ponawianie odczytów po 429/502-504 (app/przeszlosc/retry-fetch.ts). TS przez typescript.transpileModule, jak w teście 119.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
function load(file) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: () => ({}), setTimeout, clearTimeout, Error, Number, String, Math, Promise, Map, Set }, { filename: file });
  return exports;
}
const R = load('app/przeszlosc/retry-fetch.ts');

const res = (status, retryAfter) => ({ status, ok: status < 400, headers: { get: name => (name.toLowerCase() === 'retry-after' && retryAfter != null ? String(retryAfter) : null) } });
function script(...steps) {
  const calls = [];
  const base = async (input, init) => {
    calls.push({ input, init });
    const step = steps[Math.min(calls.length - 1, steps.length - 1)];
    if (step instanceof Error) throw step;
    return step;
  };
  const waits = [];
  const sleep = async ms => { waits.push(ms); };
  return { base, calls, waits, sleep };
}
const GET = '/api/przeszlosc/temat/?q=KPO';

test('429 z Retry-After: czeka tyle, ile kazał serwer, i zwraca udaną odpowiedź', async () => {
  const s = script(res(429, 7), res(200));
  const r = await R.fetchWithRetry(s.base, GET, undefined, s.sleep);
  assert.equal(r.status, 200);
  assert.equal(s.calls.length, 2);
  assert.deepEqual(s.waits, [7000]);
});

test('502/503/504 bez Retry-After: rosnące odstępy, najwyżej MAX_RETRIES ponowień', async () => {
  const s = script(res(503), res(502), res(504));
  const r = await R.fetchWithRetry(s.base, GET, undefined, s.sleep);
  assert.equal(r.status, 504);
  assert.equal(s.calls.length, R.MAX_RETRIES + 1);
  assert.deepEqual(s.waits, [R.BASE_WAIT_MS, R.BASE_WAIT_MS * 2]);
});

test('Retry-After dłuższy niż limit: bez ponawiania, od razu odpowiedź 429', async () => {
  const s = script(res(429, 60), res(200));
  const r = await R.fetchWithRetry(s.base, GET, undefined, s.sleep);
  assert.equal(r.status, 429);
  assert.equal(s.calls.length, 1);
  assert.deepEqual(s.waits, []);
});

test('błąd 4xx inny niż 429 (np. 404) i sukces nie są ponawiane', async () => {
  for (const status of [200, 404, 400, 500]) {
    const s = script(res(status));
    const r = await R.fetchWithRetry(s.base, GET, undefined, s.sleep);
    assert.equal(r.status, status);
    assert.equal(s.calls.length, 1, `status ${status}`);
  }
});

test('zapisy (POST) i inne ścieżki nigdy nie są ponawiane', async () => {
  const post = script(res(429, 1), res(200));
  assert.equal((await R.fetchWithRetry(post.base, '/api/przeszlosc/alerty/', { method: 'POST' }, post.sleep)).status, 429);
  assert.equal(post.calls.length, 1);
  const other = script(res(503), res(200));
  assert.equal((await R.fetchWithRetry(other.base, '/api/auth/csrf/', undefined, other.sleep)).status, 503);
  assert.equal(other.calls.length, 1);
  assert.equal(R.isRetryable('/api/przeszlosc/start/'), true);
  assert.equal(R.isRetryable('https://przeszlosc.today/api/przeszlosc/start/'), true);
  assert.equal(R.isRetryable('/api/clinic/spins/1/'), false);
  assert.equal(R.isRetryable({ url: '/api/przeszlosc/start/', method: 'DELETE' }), false);
});

test('błąd sieci: jedno lub dwa ponowienia, potem rzuca; AbortError rzuca od razu', async () => {
  const net = script(new Error('network'), res(200));
  assert.equal((await R.fetchWithRetry(net.base, GET, undefined, net.sleep)).status, 200);
  assert.equal(net.calls.length, 2);
  const dead = script(new Error('network'));
  await assert.rejects(R.fetchWithRetry(dead.base, GET, undefined, dead.sleep), /network/);
  assert.equal(dead.calls.length, R.MAX_RETRIES + 1);
  const aborted = new Error('x'); aborted.name = 'AbortError';
  const abort = script(aborted, res(200));
  await assert.rejects(R.fetchWithRetry(abort.base, GET, undefined, abort.sleep), e => e.name === 'AbortError');
  assert.equal(abort.calls.length, 1);
});

test('przerwanie sygnałem w trakcie czekania kończy się AbortError, bez kolejnej próby', async () => {
  const signal = { aborted: false, addEventListener() {} };
  const s = script(res(429, 3), res(200));
  const sleep = async ms => { s.waits.push(ms); signal.aborted = true; };
  await assert.rejects(R.fetchWithRetry(s.base, GET, { signal }, sleep), e => e.name === 'AbortError');
  assert.equal(s.calls.length, 1);
});

test('installRetryFetch owija fetch raz i zachowuje oryginał dla innych adresów', async () => {
  const calls = [];
  const host = { fetch: async (input) => { calls.push(input); return res(200); } };
  R.installRetryFetch(host);
  const wrapped = host.fetch;
  R.installRetryFetch(host);
  assert.equal(host.fetch, wrapped, 'drugi install nie owija ponownie');
  assert.equal((await host.fetch('/inne/')).status, 200);
  assert.deepEqual(calls, ['/inne/']);
});

test('układ: layout przeszłości montuje RetryFetch przed treścią', () => {
  const layout = read('app/przeszlosc/layout.tsx');
  assert.match(layout, /import \{ RetryFetch \} from '\.\/RetryFetch'/);
  assert.ok(layout.indexOf('<RetryFetch />') > -1 && layout.indexOf('<RetryFetch />') < layout.indexOf('{children}'));
});

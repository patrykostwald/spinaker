/* Zlecenie 116: next dev z aplikacją (APP, PUSH, ACCOUNTS włączone) i atrapą API (tylko loopback, wzorzec 109-dev). */
const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { response } = require('./109-fixture.cjs');
const root = path.resolve(__dirname, '..');
const people = [[11, 'Anna Testowa'], [12, 'Jan Przykładowy'], [13, 'Maria Fikcyjna-Nowakowska'], [14, 'Piotr Syntetyczny']];
const prefs = { push_followed: true, quiet_hours_enabled: true, quiet_hours_start: '23:00:00', quiet_hours_end: '07:00:00', wake_person_ids: [11] };
function answer(p) {
  if (p === '/api/account/me/') return { authenticated: true, user: { id: 1, username: 'czytelnik', email: 't@example.org', email_verified: true, accepted_terms_version: '2026-10-03' }, csrfToken: 'fixture' };
  if (p === '/api/account/profile/') return { theme_preference: 'dark', display_name: 'czytelnik', bio: '', is_public: false };
  if (p === '/api/account/follows/') return people.map(([id, label], n) => ({ id: n + 1, kind: 'figure', target_id: id, label, url: '/osoby/' + id }));
  if (p === '/api/account/notification-settings/') return prefs;
  if (p === '/api/push/subscriptions/') return { enabled: true, public_key: 'AAAA', csrfToken: 'fixture', consent_version: '1', results: [{ endpoint: 'x', topics: ['spin-dnia', 'nitki-dr-spina'] }] };
  if (p.startsWith('/api/account/')) return { results: [], count: 0, next_page: null };
  return response(p);
}
const server = http.createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(answer(new URL(req.url, 'http://localhost').pathname.replace(/\/+$/, '/')))); });
server.listen(3116, '127.0.0.1', () => {
  const child = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'dev', root, '-p', '3016', '-H', '127.0.0.1'], { cwd: root, stdio: 'inherit', env: { ...process.env,
    NODE_OPTIONS: `--require="${path.join(__dirname, '109-preload.cjs').replaceAll(String.fromCharCode(92), '/')}"`, NEXT_TELEMETRY_DISABLED: '1',
    NEXT_FONT_GOOGLE_MOCKED_RESPONSES: path.join(__dirname, '109-fonts.cjs'),
    THREADS_ENABLED: 'false', NEXT_PUBLIC_THREADS_ENABLED: process.env.FLAG || 'false', NEXT_PUBLIC_ACCOUNTS_ENABLED: 'true', NEXT_PUBLIC_APP_ENABLED: 'true', NEXT_PUBLIC_PUSH_ENABLED: 'true',
    NEXT_PUBLIC_API_URL: 'http://127.0.0.1:3116', API_INTERNAL_URL: 'http://127.0.0.1:3116', NEXT_PUBLIC_PLAUSIBLE_DOMAIN: '',
  } });
  child.on('exit', code => { server.close(); process.exitCode = code; });
});

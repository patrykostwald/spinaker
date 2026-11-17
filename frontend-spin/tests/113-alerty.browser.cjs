/* Zlecenie 113: prawdziwy komponent AlertSettings z atrapą API na lokalnym serwerze (bez sieci zewnętrznej). */
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const webpackModule = require('next/dist/compiled/webpack/webpack'); webpackModule.init();
const { webpack } = webpackModule;
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '../..'), temp = path.join(root, '.pytest-tmp/113-browser');
const output = process.env.OUT_DIR || path.join(temp, 'out');
fs.mkdirSync(temp, { recursive: true }); fs.mkdirSync(output, { recursive: true });
const ui = path.join(root, 'packages/ui/src');
fs.writeFileSync(path.join(temp, 'entry.tsx'), `import React from 'react';import {createRoot} from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {AlertSettings} from ${JSON.stringify(path.join(root, 'frontend-spin/app/konto/alerty/AlertSettings'))};const client=new QueryClient({defaultOptions:{queries:{retry:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><AlertSettings/></QueryClientProvider>);`);

function build(push) {
  return new Promise((resolve, reject) => webpack({ mode: 'development', devtool: false, entry: path.join(temp, 'entry.tsx'),
    output: { path: temp, filename: `bundle-${push}.js` },
    resolve: { extensions: ['.tsx', '.ts', '.js', '.json'], modules: [path.join(root, 'frontend-spin/node_modules'), 'node_modules'] },
    module: { rules: [{ test: /\.(tsx?|css)$/, use: path.join(__dirname, 'corrections.loader.cjs') }] },
    plugins: [new webpack.DefinePlugin({ 'process.env': JSON.stringify({ NODE_ENV: 'development', NEXT_PUBLIC_ACCOUNTS_ENABLED: 'true', NEXT_PUBLIC_PUSH_ENABLED: String(push), NEXT_PUBLIC_API_URL: '' }) })] },
    (e, s) => e || s.hasErrors() ? reject(e || new Error(s.toString({ all: false, errors: true }))) : resolve()));
}

const people = [[11, 'Anna Testowa'], [12, 'Jan Przykładowy'], [13, 'Maria Fikcyjna-Nowakowska'], [14, 'Piotr Syntetyczny']];

async function main() {
  await build(true); await build(false);
  const font = fs.readFileSync(path.join(root, 'backend/news/assets/fonts/Montserrat[wght].ttf')).toString('base64');
  const css = fs.readFileSync(path.join(ui, 'kit/kit.css'), 'utf8') + `\nbody{margin:0;background:var(--sc-bg);color:var(--sc-text);font-family:var(--sc-font-sans)}@font-face{font-family:Montserrat;src:url(data:font/ttf;base64,${font}) format('truetype');font-weight:100 900}`;
  let prefs = { push_followed: true, quiet_hours_enabled: true, quiet_hours_start: '23:00:00', quiet_hours_end: '07:00:00', wake_person_ids: [11] };
  let patched = null;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x'), p = url.pathname, json = v => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(v)); };
    if (p === '/alerty' || p === '/alerty-nopush') {
      const bundle = p === '/alerty' ? 'bundle-true.js' : 'bundle-false.js';
      res.setHeader('Content-Type', 'text/html'); return res.end(`<!doctype html><html lang="pl" data-theme="dark"><meta charset="utf-8"><title>Ustawienia alertów</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style><div id="root"></div><script src="/${bundle}"></script></html>`);
    }
    if (p.startsWith('/bundle-')) { res.setHeader('Content-Type', 'text/javascript'); return res.end(fs.readFileSync(path.join(temp, p.slice(1)))); }
    if (p === '/api/auth/csrf/') return json({ csrfToken: 'fixture' });
    if (p === '/api/account/me/') return json({ authenticated: true, user: { id: 1, username: 'czytelnik', email: 't@example.org', email_verified: true, accepted_terms_version: '2026-10-03' }, csrfToken: 'fixture' });
    if (p === '/api/account/follows/') return json(people.map(([id, label], n) => ({ id: n + 1, kind: 'figure', target_id: id, label, url: '/osoby/' + id })));
    if (p === '/api/account/notification-settings/') {
      if (req.method === 'PATCH') { let body = ''; req.on('data', c => body += c); req.on('end', () => { patched = JSON.parse(body); prefs = { ...prefs, ...patched }; json(prefs); }); return; }
      return json(prefs);
    }
    res.statusCode = 404; res.end('{}');
  });
  await new Promise(resolve => server.listen(Number(process.env.PORT || 3113), '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  if (process.env.SERVE_ONLY) { console.log('SERVING', base); return; }
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const errors = [];
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(base + '/alerty'); await page.getByRole('heading', { name: 'Ustawienia alertów' }).waitFor();
      await page.getByRole('button', { name: 'Zapisz ustawienia' }).waitFor();
      await page.evaluate(() => document.fonts.ready);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow ${width}`);
      await page.screenshot({ path: path.join(output, `${width}-alerty.png`), fullPage: true });
      if (width === 1440) {
        await page.getByLabel('Wyciszaj w wybranych godzinach').uncheck();
        await page.getByRole('button', { name: 'Zapisz ustawienia' }).click();
        await page.getByText('Zapisano ustawienia alertów.').waitFor();
        assert.equal(patched.quiet_hours_enabled, false);
        assert.deepEqual(patched.wake_person_ids, [11]);
        await page.getByLabel('Wyciszaj w wybranych godzinach').check();
        await page.locator('input[type=time]').first().fill('23:00'); await page.locator('input[type=time]').nth(1).fill('23:00');
        await page.getByRole('button', { name: 'Zapisz ustawienia' }).click();
        await page.getByText('Wybierz różne godziny').waitFor();
      }
      await page.goto(base + '/alerty-nopush'); await page.getByText('Powiadomienia push są obecnie wyłączone').waitFor();
      await page.screenshot({ path: path.join(output, `${width}-alerty-bez-push.png`), fullPage: true });
      await page.close();
      console.log(`PASS ${width}px`);
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); server.close(); }
}
main().catch(e => { console.error(e); process.exitCode = 1; });

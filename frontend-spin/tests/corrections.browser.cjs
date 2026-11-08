/* Lokalny test prawdziwych komponentów: Playwright podstawia API i dokument, bez serwera i sieci. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const webpackModule = require('next/dist/compiled/webpack/webpack');
webpackModule.init();
const { webpack } = webpackModule;
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '../..');
const temp = path.join(root, '.pytest-tmp/065-browser');
const output = process.env.EVIDENCE_DIR || path.join(temp, 'evidence');
fs.mkdirSync(temp, { recursive: true });
fs.mkdirSync(output, { recursive: true });
const ui = path.join(root, 'packages/ui/src');
fs.writeFileSync(path.join(temp, 'link.tsx'), `import React from 'react'; export default function Link({href, children, prefetch, scroll, replace, ...props}: any) {return <a href={href} {...props}>{children}</a>}`);
fs.writeFileSync(path.join(temp, 'navigation.ts'), `export const usePathname = () => window.location.pathname; export const useRouter = () => ({push() {},replace() {},refresh() {}}); export const useSearchParams = () => new URLSearchParams(window.location.search);`);
fs.writeFileSync(path.join(temp, 'entry.tsx'), `
import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ClinicCorrections } from ${JSON.stringify(path.join(ui, 'components/clinic/ClinicCorrections'))};
import { SpinDetail } from ${JSON.stringify(path.join(ui, 'components/clinic/SpinDetail'))};
import { FeatureFooter } from ${JSON.stringify(path.join(root, 'frontend-spin/app/PreviewControls'))};
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}>{window.location.pathname.endsWith('korekty') ? <ClinicCorrections /> : <SpinDetail id="65" />}<FeatureFooter /></QueryClientProvider>);
`);
const author = { name: 'Aleksandra Nowak', handle: 'aleksandra_przyklad', account_url: 'https://x.com/aleksandra_przyklad',
  avatar_url: '', figure_id: null, role_title: '', party: null };
const response = { id: 1, body: 'Wypowiedź dotyczyła projektu ustawy, a nie obowiązujących przepisów. Pełne nagranie zawiera to zastrzeżenie.',
  source_url: 'https://example.org/stanowisko', received_at: '2026-09-30T10:00:00Z', published_at: '2026-10-01T08:00:00Z' };
const withdrawn = { id: 65, status: 'withdrawn', withdrawn_at: '2026-10-01T12:30:00Z',
  withdrawn_reason: 'Diagnoza opierała się na niepełnym kontekście wypowiedzi. Po sprawdzeniu pełnego nagrania wycofaliśmy analizę.',
  author, camp: 'government', camp_label: 'Rządzący', post: { url: 'https://x.com/aleksandra_przyklad/status/65', published_at: '2026-09-29T09:15:00Z' }, author_replies: [response] };
const event = { author, camp: 'government', camp_label: 'Rządzący', post_date: withdrawn.post.published_at, diagnosis_url: '/klinika/65', reason: '', reply_excerpt: '' };
const register = { count: 3, next_page: 2, counts: { published: 1204, withdrawn: 3, hidden: 1, replies: 2 }, results: [
  { ...event, id: 'withdrawal:65', type: 'withdrawal', date: withdrawn.withdrawn_at, reason: withdrawn.withdrawn_reason },
  { ...event, id: 'author_reply:1', type: 'author_reply', date: response.published_at, reply_excerpt: response.body, camp: 'opposition', camp_label: 'Opozycja', author: { ...author, name: 'Michał Kowalski' } },
  { id: 'hiding:66', type: 'hiding', date: '2026-09-30T08:45:00Z', author: null, camp: null, camp_label: null, post_date: null, diagnosis_url: null, reason: '', reply_excerpt: '', notice: 'Ukryto po zgłoszeniu prawnym' },
] };

async function main() {
  await new Promise((resolve, reject) => webpack({
    mode: 'development', devtool: false, entry: path.join(temp, 'entry.tsx'),
    output: { path: temp, filename: 'bundle.js' },
    resolve: { extensions: ['.tsx', '.ts', '.js', '.json'], modules: [path.join(root, 'frontend-spin/node_modules'), 'node_modules'],
      alias: { 'next/link$': path.join(temp, 'link.tsx'), 'next/navigation$': path.join(temp, 'navigation.ts') } },
    module: { rules: [{ test: /\.(tsx?|css)$/, use: path.join(__dirname, 'corrections.loader.cjs') }] },
    plugins: [new webpack.DefinePlugin({ 'process.env': JSON.stringify({ NEXT_PUBLIC_API_URL: '', NODE_ENV: 'development' }) })],
  }, (error, stats) => error || stats.hasErrors() ? reject(error || new Error(stats.toString({ all: false, errors: true }))) : resolve()));
  const bundle = fs.readFileSync(path.join(temp, 'bundle.js'), 'utf8');
  let css = fs.readFileSync(path.join(root, 'frontend-spin/app/globals.css'), 'utf8') + '\n' + fs.readFileSync(path.join(ui, 'kit/kit.css'), 'utf8');
  const font = fs.readFileSync(path.join(root, 'backend/news/assets/fonts/Montserrat[wght].ttf')).toString('base64');
  css += `\n@font-face{font-family:Montserrat;src:url(data:font/ttf;base64,${font}) format('truetype');font-weight:100 900;font-style:normal}`;
  css += '\n*{box-sizing:border-box}body{margin:0;background:var(--sc-bg);color:var(--sc-text);font-family:var(--sc-font-sans)}button{font:inherit}';
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [];
  try {
    for (const width of [1440, 390]) for (const theme of ['dark', 'light']) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, locale: 'pl-PL', timezoneId: 'Europe/Warsaw' });
      page.on('pageerror', e => { errors.push(e.message); console.error('Browser:', e.message); });
      let scenario = 'normal';
      await page.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/api/clinic/corrections/')) {
          if (scenario === 'error') return route.fulfill({ status: 503, body: '{}' });
          const data = scenario === 'empty' ? { results: [], next_page: null, count: 0, counts: { published: 1204, withdrawn: 0, hidden: 0, replies: 0 } }
            : url.searchParams.get('page') === '2' ? { ...register, results: [{ ...register.results[0], id: 'withdrawal:64', reason: 'Starsze wycofanie.' }], next_page: null } : register;
          return route.fulfill({ json: data });
        }
        if (url.pathname === '/api/clinic/spins/65/') return route.fulfill({ json: withdrawn });
        if (url.pathname.startsWith('/api/')) return route.fulfill({ json: { results: [] } });
        if (url.pathname === '/support-progress') return route.fulfill({ json: { goal: 0, raised: 0 } });
        if (url.pathname === '/bundle.js') return route.fulfill({ contentType: 'text/javascript', body: bundle });
        return route.fulfill({ contentType: 'text/html', body: `<!doctype html><html lang="pl" data-theme="${theme}"><head><meta charset="utf-8"><style>${css}</style></head><body><main id="root"></main><script src="/bundle.js"></script></body></html>` });
      });
      for (const [name, url, title] of [['rejestr', '/klinika/korekty', 'Rejestr korekt'], ['wycofana', '/klinika/65', 'Diagnoza wycofana']]) {
        await page.goto('http://clinic.test' + url);
        await page.getByRole('heading', { name: title, exact: true }).waitFor();
        if (name === 'rejestr') await page.getByText(withdrawn.withdrawn_reason, { exact: true }).waitFor();
        else {
          await page.getByRole('heading', { name: 'Odpowiedź autora' }).waitFor();
          assert.equal(await page.locator('.sc-dg-score, .sc-spin-detail__analysis, .sc-share-cta').count(), 0);
          assert.equal(await page.getByText('Uzasadnienie', { exact: true }).count(), 0);
        }
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} ${width}: overflow`);
        await page.screenshot({ path: path.join(output, `065-${name}-${width}-${theme}.png`), fullPage: true });
        if (name === 'rejestr') {
          await page.getByRole('button', { name: 'Pokaż wcześniejsze zdarzenia' }).click();
          await page.getByText('Starsze wycofanie.').waitFor();
          assert.equal(await page.getByRole('button', { name: 'Pokaż wcześniejsze zdarzenia' }).count(), 0);
        }
      }
      scenario = 'empty';
      await page.goto('http://clinic.test/klinika/korekty');
      await page.getByText('Na razie nie wycofaliśmy żadnej diagnozy.').waitFor();
      scenario = 'error';
      await page.reload();
      await page.getByRole('button', { name: 'Spróbuj ponownie' }).waitFor();
      scenario = 'normal';
      await page.getByRole('button', { name: 'Spróbuj ponownie' }).click();
      await page.getByText(withdrawn.withdrawn_reason, { exact: true }).waitFor();
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log('OK: 8 zrzutów, oba motywy, 1440/390, brak overflow, paginacja, pusto, błąd i ponowienie, wycofanie bez AI.');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

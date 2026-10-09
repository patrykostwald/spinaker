const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const fixture = require('./flow.fixture.cjs');
const source = fixture.nodes[0].source;
const person = { id: 1, slug: '1-przykladowy', name: 'Jan Przykładowy', role_title: 'Osoba publiczna', organisation: '', status: 'current', krs_note: 'Dane testowe', generated_at: fixture.generated_at,
  x_accounts: [], posts: { count: 0, diagnoses: 0, avg_spin: null, results: [] }, documents: { available: true, count: 0, by_kind: {}, results: [] },
  votes: { available: true, count: 0, summary: {}, reason: '', results: [] }, organisations: [], employment_timeline: [], materials: { count: 0, results: [] },
  activity: [{ month: '2026-09', posts: 0, documents: 0, votes: 0, media: 0 }, { month: '2026-10', posts: 0, documents: 0, votes: 0, media: 0 }], topics: [], denominators: null };
const company = { organisation: { id: 1, name: 'Spółka Przykładowa', krs_number: '0000012345', nip: '1234567890', regon: '', kind: 'company', legal_form: 'Spółka', sector: '', url: source.url, source },
  identifiers: { KRS: '0000012345', NIP: '1234567890' }, identifiers_missing: false, contracts: { count: 0, sums: [], results: [] }, grants: { count: 0, sums: [], results: [] },
  people: { count: 0, results: [] }, unlinked: { count: 0, results: [] }, sources: [source], note: 'Dane testowe', unlinked_reason: '', generated_at: fixture.generated_at };
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const results = [], errors = [], output = path.resolve(__dirname, '../../reports/105');
  try {
    for (const width of [1440, 390]) for (const kind of ['person', 'company']) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'http://127.0.0.1:3106') return route.abort();
        if (!url.pathname.startsWith('/api/')) return route.continue();
        return route.fulfill({ json: url.pathname.includes('/osoba/') ? person : url.pathname.includes('/spolka/') ? company
          : url.pathname.includes('/przeplyw/') ? fixture : url.pathname.includes('/funkcje/') ? { beta: true, label: 'Beta', locked: [] } : {} });
      });
      await page.goto(`http://127.0.0.1:3106/przeszlosc/${kind === 'person' ? 'osoba/1' : 'spolka/0000012345'}`, { waitUntil: 'networkidle', timeout: 120000 });
      const link = page.getByRole('link', { name: 'Drzewo przepływu →', exact: true }); await link.waitFor().catch(async e => { console.error(errors, (await page.locator('body').innerText()).slice(0, 1500)); throw e; });
      const rect = await link.boundingBox(); assert(rect.height >= 44); assert(rect.x >= 0 && rect.x + rect.width <= width);
      await page.screenshot({ path: path.join(output, `link-${kind}-${width}.png`), fullPage: false });
      await link.click(); await page.locator('.px-flow__node').first().waitFor();
      assert(decodeURIComponent(new URL(page.url()).pathname).endsWith(kind === 'person' ? 'osoba:1-przykladowy' : 'spolka:0000012345'));
      results.push({ kind, width, link: rect }); await page.close();
    }
    assert.deepEqual(errors, []); fs.writeFileSync(path.join(output, 'links-results.json'), JSON.stringify({ results, errors }, null, 2)); console.log('PASS: linki osoby i spółki, 1440/390');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });

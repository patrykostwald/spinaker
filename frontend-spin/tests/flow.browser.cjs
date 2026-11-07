const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const fixture = require('./flow.fixture.cjs');
const output = path.resolve(__dirname, '../../reports/105'); fs.mkdirSync(output, { recursive: true });
const base = 'http://127.0.0.1:3106', url = `${base}/przeszlosc/przeplyw/osoba:1`;
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const results = [], errors = [];
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
      page.on('pageerror', e => errors.push(e.message));
      let mode = 'ready', requests = [];
      await page.route('**/*', route => {
        const request = new URL(route.request().url());
        if (request.origin !== base) return route.abort();
        if (!request.pathname.startsWith('/api/')) return route.continue();
        if (request.pathname.startsWith('/api/przeszlosc/funkcje/')) return route.fulfill({ json: { beta: true, label: 'Beta', locked: [] } });
        if (!request.pathname.startsWith('/api/przeszlosc/przeplyw/')) return route.fulfill({ json: {} });
        requests.push(request.search);
        if (mode === 'error') return route.fulfill({ status: 500, json: { detail: 'Błąd testowy' } });
        if (mode === 'network') return route.abort();
        if (mode === 'locked') return route.fulfill({ status: 403, json: {} });
        if (mode === 'missing') return route.fulfill({ status: 404, json: {} });
        const data = structuredClone(fixture);
        if (mode === 'empty') { data.nodes = []; data.edges = []; data.timeline = []; }
        if (mode === 'grouped') { data.limits.truncated = true; data.limits.grouped = [{ id: 'g', label: '42 umowy z gminą', count: 42, category: 'zamowienia', kind: 'contract' }]; }
        if (mode === 'large') { data.nodes = Array.from({ length: 300 }, (_, i) => ({ ...fixture.nodes[0], id: i === 0 ? 'root' : `${request.searchParams.has('kategorie') ? 'm' : 'n'}${i}`, level: i % 4, label: `Węzeł ${i}`, short: `Węzeł ${i}` }));
          data.edges = Array.from({ length: 600 }, (_, i) => ({ ...fixture.edges[0], id: `large-e${i}`, from: data.nodes[i % 300].id, to: data.nodes[(i + 1) % 300].id })); data.timeline = []; }
        if (mode === 'ready' && request.searchParams.has('kategorie')) {
          const categories = request.searchParams.get('kategorie').split(',');
          data.nodes = data.nodes.filter(n => n.id === 'root' || categories.includes(n.category === 'media' ? 'polityka' : n.category));
          const ids = new Set(data.nodes.map(n => n.id)); data.edges = data.edges.filter(e => ids.has(e.from) && ids.has(e.to)); data.timeline = data.timeline.filter(t => ids.has(t.node_id));
        }
        return route.fulfill({ json: data });
      });
      await page.goto(url, { waitUntil: 'networkidle', timeout: 120000 });
      const nodes = page.locator('.px-flow__node'); await nodes.first().waitFor();
      assert.equal(await nodes.count(), 8);
      assert.equal(await page.locator('[data-kind="diagnosis"]').count(), 0);
      assert(requests.every(q => new URLSearchParams(q).get('narracja') === '0'));
      const measurements = await page.evaluate(() => {
        const box = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height }; };
        return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth, header: box('.px-flow__head'), bar: box('.px-bar'), graph: box('.px-flow__graph'), panel: box('.px-flow__panel'), timeline: box('.px-flow__timeline'),
          nodes: [...document.querySelectorAll('.px-flow__node')].map(e => { const r = e.getBoundingClientRect(); return { level: e.dataset.level, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; }) };
      });
      assert(measurements.scrollWidth <= width, 'strona nie może przewijać się poziomo');
      assert(measurements.graph.left >= 0 && measurements.graph.right <= width, 'scena mieści się na stronie');
      assert.equal(new Set(measurements.nodes.map(n => n.height)).size, 1);
      assert.equal(measurements.timeline.height, 220);
      if (width === 1440) assert.equal(measurements.graph.bottom, measurements.panel.bottom);
      assert(measurements.header.top - measurements.bar.bottom <= (width === 390 ? 28 : 40));
      await page.screenshot({ path: path.join(output, `flow-${width}.png`), fullPage: true });
      await nodes.first().focus(); await page.keyboard.press('Enter');
      await page.getByRole('button', { name: 'Zamknij szczegóły', exact: true }).first().waitFor();
      assert(await page.locator('.px-flow__panel').innerText().then(t => t.includes('Rejestr demonstracyjny')));
      await page.screenshot({ path: path.join(output, `flow-panel-${width}.png`), fullPage: true });
      await page.keyboard.press('Escape'); assert(await nodes.first().evaluate(e => e === document.activeElement));
      const beforeFilter = await page.locator('[id="flow-node-spolka"]').boundingBox();
      await page.getByRole('button', { name: /^Polityka / }).click(); await page.waitForLoadState('networkidle'); await nodes.first().waitFor();
      assert.deepEqual(await page.locator('[id="flow-node-spolka"]').boundingBox(), beforeFilter);
      assert.equal(await page.locator('.px-flow__node[data-kind="media"]').count(), 0);
      assert(new URL(page.url()).searchParams.has('kategorie'));
      await page.goBack(); await page.waitForLoadState('networkidle'); await page.locator('.px-flow__viewport[aria-busy="false"]').waitFor();
      assert.equal(await page.locator('.px-flow__node[data-kind="media"]').count(), 1);
      await page.getByLabel('Pokaż niepowiązane', { exact: true }).check(); await page.waitForLoadState('networkidle');
      await page.getByTitle('Podobna nazwa', { exact: true }).waitFor();
      assert(await page.getByTitle('Podobna nazwa', { exact: true }).innerText().then(t => t.includes('zgodność nazwy, nie liczona')));
      await page.locator('.px-layer-toggle').click(); await page.waitForLoadState('networkidle'); await page.locator('.px-flow__node[data-kind="diagnosis"]').waitFor();
      assert(requests.some(q => new URLSearchParams(q).get('narracja') === '1'));
      await page.locator('.px-layer-toggle').click(); await page.waitForLoadState('networkidle'); assert.equal(await page.locator('.px-flow__node[data-kind="diagnosis"]').count(), 0);
      await page.getByLabel('Początek zakresu dat').fill('1'); await page.waitForLoadState('networkidle'); assert(new URL(page.url()).searchParams.has('od'));
      await page.getByRole('button', { name: 'Wyczyść filtry' }).click(); await page.waitForLoadState('networkidle');
      await page.locator('.px-flow__events button').first().click(); assert.equal(await page.locator('.px-flow__node[data-selected="true"]').count(), 1); await page.keyboard.press('Escape');
      await page.getByRole('button', { name: 'Dopasuj', exact: true }).click();
      assert(await page.locator('.px-flow__viewport').evaluate(e => e.scrollHeight <= e.clientHeight + 1 && e.scrollWidth <= e.clientWidth + 1));
      await page.screenshot({ path: path.join(output, `flow-fit-${width}.png`), fullPage: true });
      await page.getByLabel('Przywróć skalę 100 procent').click();
      await page.getByText('Lista tekstowa węzłów i powiązań', { exact: true }).click();
      await page.locator('.px-flow__list ul button').first().click(); assert(await page.locator('.px-flow__panel').innerText().then(t => t.includes('Powiązanie'))); await page.keyboard.press('Escape');
      for (const scenario of ['empty', 'error', 'network', 'locked', 'missing', 'grouped', 'large']) {
        mode = scenario; await page.goto(url, { waitUntil: 'networkidle' });
        if (scenario === 'empty') assert(await page.getByText('Brak powiązań w danych, które zbieramy', { exact: true }).isVisible());
        if (scenario === 'error') { await page.getByRole('button', { name: 'Spróbuj ponownie' }).waitFor(); mode = 'ready'; await page.getByRole('button', { name: 'Spróbuj ponownie' }).click(); await nodes.first().waitFor(); }
        if (scenario === 'network') assert(await page.getByText('Nie udało się pobrać drzewa. Spróbuj ponownie.', { exact: true }).isVisible());
        if (scenario === 'locked') assert(await page.getByRole('link', { name: 'Pilotaż', exact: true }).isVisible());
        if (scenario === 'missing') assert(await page.getByRole('link', { name: 'Szukaj ponownie', exact: true }).isVisible());
        if (scenario === 'grouped') { await page.getByRole('button', { name: /42 umowy.*Rozwiń/ }).click(); await page.getByRole('button', { name: 'Pokaż kategorię do poziomu 3' }).click(); await page.waitForLoadState('networkidle'); assert.equal(new URL(page.url()).searchParams.get('glebokosc'), '3'); }
        if (scenario === 'large') { assert.equal(await nodes.count(), 300); assert.equal(await page.locator('.px-flow__edge').count(), 600); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          await page.getByRole('button', { name: /^Spółki / }).click(); await page.waitForLoadState('networkidle');
          assert.equal(await nodes.count(), 300); assert.equal(await page.locator('[id="flow-node-m1"]').count(), 1);
        }
      }
      results.push({ width, measurements, scenarios: ['keyboard', 'source', 'filters', 'history', 'name_only', 'narrative', 'timeline', 'zoom', 'edges', 'empty', 'error/retry', 'locked', '404', 'grouped', '300 nodes'] });
      await page.close();
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ results, errors }, null, 2));
    console.log(JSON.stringify({ passed: true, widths: results.map(r => r.width), output }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });

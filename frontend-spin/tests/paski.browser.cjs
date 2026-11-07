const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const data = require('./paski-mock.cjs');
const output = path.resolve(__dirname, '../../artifacts/106');
fs.mkdirSync(output, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  try {
    const measurements = [];
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
      let mode = 'ready';
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.includes('/api/')) {
          if (url.pathname.includes('/paski')) {
            if (mode === 'loading') await new Promise(resolve => setTimeout(resolve, 1500));
            return route.fulfill({ status: mode === 'error' ? 503 : 200, contentType: 'application/json', body: JSON.stringify(mode === 'empty' ? { ...data, youtube: [], publiczne: [] } : data) });
          }
          return route.fulfill({ status: url.pathname.includes('/start') ? 200 : 503, contentType: 'application/json', body: JSON.stringify(url.pathname.includes('/start') ? { counts: {}, latest: [], topics_enabled: false } : {}) });
        }
        if (url.hostname === 'i.ytimg.com') return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="144"><rect width="256" height="144" fill="#343434"/><text x="128" y="76" text-anchor="middle" fill="white" font-size="18">Miniatura testowa</text></svg>' });
        if (!['localhost', '127.0.0.1'].includes(url.hostname)) return route.abort();
        return route.continue();
      });
      await page.goto('http://localhost:3106/przeszlosc', { timeout: 120000 });
      await page.locator('.px-strip__card').first().waitFor();
      assert.equal(await page.locator('[data-strip="media"]').count(), 0);
      const measure = () => page.evaluate(() => {
        const box = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { top: r.top + scrollY, bottom: r.bottom + scrollY, height: r.height }; };
        return { width: innerWidth, pageWidth: document.documentElement.scrollWidth, bar: box('.px-bar'), youtube: box('[data-strip="youtube"]'), publiczne: box('[data-strip="publiczne"]'), cards: [...document.querySelectorAll('.px-strip__card')].map(e => ({ top: e.offsetTop, width: e.getBoundingClientRect().width, height: e.getBoundingClientRect().height })), targets: [...document.querySelectorAll('.px-strip button')].map(e => ({ width: e.getBoundingClientRect().width, height: e.getBoundingClientRect().height })) };
      });
      const initial = await measure();
      assert.equal(initial.pageWidth, width);
      assert(initial.cards.every(c => c.width === 280));
      assert(initial.youtube.top - initial.bar.bottom <= (width === 390 ? 28 : 40));
      assert(initial.targets.every(t => t.width >= 44 && t.height >= 44));
      await page.screenshot({ path: path.join(output, `paski-${width}.png`), fullPage: true });
      const beforeStyle = await page.addStyleTag({ content: '.px-strips { display:none !important } .px-home-top { display:contents !important } .px .px-home-top > .px-bar { margin-bottom:-48px } @media(max-width:760px){.px .px-home-top > .px-bar {margin-bottom:-36px}}' });
      await page.screenshot({ path: path.join(output, `przed-${width}.png`), fullPage: true });
      await beforeStyle.evaluate(node => node.remove());
      const strip = page.locator('[data-strip="youtube"]');
      await strip.getByRole('button', { name: 'Przewiń w prawo: YouTube' }).click();
      assert(await strip.locator('.px-strip__track').evaluate(e => e.scrollLeft) > 0);
      await strip.locator('.px-strip__track').focus();
      await page.keyboard.press('ArrowLeft');
      assert(await strip.locator('.px-strip__track').evaluate(e => e.scrollLeft) <= 2);
      await strip.getByRole('button', { name: 'Sejm RP', exact: true }).click();
      assert.equal(await strip.locator('.px-strip__card').count(), 4);
      assert.equal((await measure()).publiczne.top, initial.publiczne.top);
      console.log(width, 'reload storage'); await page.reload(); await page.locator('.px-strip__card').first().waitFor();
      assert.equal(await strip.locator('.px-strip__card').count(), 4);
      for (const next of ['empty', 'error', 'loading']) {
        console.log(width, next); mode = next; await page.reload();
        await page.locator('.px-strip__status').first().waitFor();
        const now = await measure();
        assert.equal(now.youtube.height, initial.youtube.height);
        assert.equal(now.publiczne.top - now.youtube.bottom, initial.publiczne.top - initial.youtube.bottom);
        assert.equal(now.publiczne.height, initial.publiczne.height);
        await page.screenshot({ path: path.join(output, `${next}-${width}.png`), fullPage: false });
        if (next === 'error') { mode = 'ready'; await strip.getByRole('button', { name: 'Spróbuj ponownie' }).click(); await page.locator('.px-strip__card').first().waitFor(); }
      }
      measurements.push(initial);
      await page.close();
    }
    fs.writeFileSync(path.join(output, 'pomiary.json'), JSON.stringify(measurements, null, 2));
    console.log('OK: 1440/390, no overflow, 44px, filters/storage, keyboard, stable states, retry');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

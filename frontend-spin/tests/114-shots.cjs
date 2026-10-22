/* Zlecenie 114: zrzuty i kontrola braku śladów spinek przy fladze false (next dev z 114-dev.cjs na 3014). */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const base = process.env.BASE || 'http://127.0.0.1:3014';
const flag = process.env.FLAG || 'false';
const out = process.env.OUT_DIR || path.join(process.env.TEMP, '114-shots'); fs.mkdirSync(out, { recursive: true });
const trace = /spink|nitk|\btrop/i;
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const results = {};
  try {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
    const api = ctx.request;
    for (const p of ['/spinki', '/spinki/12', '/nitki', '/nitki/x', '/tropy', '/tropy/x/y', '/konto/spinki/nowa', '/konto/spinki/5', '/konto/nitki/5', '/konto/tropy/5']) {
      const r = await api.get(base + p, { maxRedirects: 0 });
      results['redirect ' + p] = `${r.status()} -> ${r.headers().location}`;
    }
    const manifest = await (await api.get(base + '/manifest.webmanifest')).json();
    results.shortcuts = manifest.shortcuts.map(s => `${s.name} ${s.url}`);
    const sitemap = await (await api.get(base + '/sitemap.xml')).text();
    results.sitemapSpinki = /spink|nitki|tropy/.test(sitemap);
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      for (const [name, url] of [['glowna', '/'], ['alerty', '/konto/alerty'], ['o-nas', '/o-nas'], ['klinika', '/klinika']]) {
        for (let i = 0; i < 3; i++) { try { await page.goto(base + url, { waitUntil: 'load', timeout: 90000 }); break; } catch (e) { if (i === 2) throw e; await page.waitForTimeout(3000); } } await page.waitForTimeout(1500);
        await page.evaluate(() => document.fonts.ready);
        const text = await page.evaluate(() => document.body.innerText);
        results[`${width} ${name} trace`] = (text.match(new RegExp(trace.source, 'gi')) || []).length;
        results[`${width} ${name} overflow`] = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        await page.screenshot({ path: path.join(out, `${width}-${name}-flag-${flag}.png`), fullPage: true });
      }
      await page.goto(base + '/#powiadomienia', { waitUntil: 'load' }); await page.waitForTimeout(2500);
      const dialog = await page.evaluate(() => { const d = document.querySelector('dialog.sc-pwa-dialog'); return d ? { open: d.open, text: d.innerText, boxes: d.querySelectorAll('input[type=checkbox]').length } : null; });
      results[`${width} dialog`] = dialog && { open: dialog.open, boxes: dialog.boxes, trace: trace.test(dialog.text) };
      if (dialog && width === 1440) await page.screenshot({ path: path.join(out, `${width}-dialog-flag-${flag}.png`) });
      results[`${width} errors`] = errors;
      await page.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(results, null, 1));
})();

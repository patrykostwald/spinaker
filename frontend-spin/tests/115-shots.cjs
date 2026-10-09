/* Zlecenie 115: zrzuty i kontrola braku śladów spinek/nitek przy fladze false (next dev z 115-dev.cjs na 3015). */
const fs = require('node:fs'), path = require('node:path');
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const base = process.env.BASE || 'http://127.0.0.1:3015';
const flag = process.env.FLAG || 'false';
const out = process.env.OUT_DIR || path.join(process.env.TEMP, '115-shots'); fs.mkdirSync(out, { recursive: true });
const trace = /spink|spinek|nitk|\btrop/i;
const pages = [['glowna', '/'], ['klinika', '/klinika'], ['diagnoza', '/klinika/109'], ['konto', '/konto'], ['konto-zapisane', '/konto#obserwowani'], ['szukaj', '/search?q=test'], ['profil', '/profile/czytelnik']];
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const results = {};
  try {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
    for (const p of ['/thread/jakis-slug', '/thread', '/spinki', '/konto/spinki/nowa']) {
      const r = await ctx.request.get(base + p, { maxRedirects: 0, timeout: 180000 });
      results['redirect ' + p] = `${r.status()} -> ${r.headers().location}`;
    }
    const title = async url => { const r = await ctx.request.get(base + url, { timeout: 180000 }); const t = await r.text(); return (t.match(/<meta name="description" content="([^"]*)"/) || [])[1]; };
    results.metaSzukaj = await title('/search');
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      for (const [name, url] of pages) {
        for (let i = 0; i < 3; i++) { try { await page.goto(base + url, { waitUntil: 'load', timeout: 90000 }); break; } catch (e) { if (i === 2) throw e; await page.waitForTimeout(3000); } }
        await page.waitForTimeout(2500);
        await page.evaluate(() => document.fonts.ready);
        const text = await page.evaluate(() => document.body.innerText);
        const hrefs = await page.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => /spinki|nitki|tropy|\/thread|jak-dziala/.test(h)));
        results[`${width} ${name}`] = { trace: (text.match(new RegExp(trace.source, 'gi')) || []), badLinks: hrefs, errs: errors.length, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), url: page.url().replace(base, '') };
        await page.screenshot({ path: path.join(out, `${width}-${name}-flag-${flag}.png`), fullPage: true });
      }
      results[`${width} errors`] = errors;
      await page.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(results, null, 1));
})();

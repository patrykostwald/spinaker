/* Zlecenie 116: zrzuty /aplikacja i /konto/alerty (1440, 390) oraz zrzuty do manifestu (public/app/screenshots). Wymaga 116-dev.cjs na 3016. */
const fs = require('node:fs'), path = require('node:path');
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const base = process.env.BASE || 'http://127.0.0.1:3016';
const out = process.env.OUT_DIR || path.join(process.env.TEMP, '116-shots'); fs.mkdirSync(out, { recursive: true });
const manifestDir = path.resolve(__dirname, '../public/app/screenshots');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const results = {};
  async function open(page, url) {
    for (let i = 0; i < 3; i++) { try { await page.goto(base + url, { waitUntil: 'load', timeout: 90000 }); break; } catch (e) { if (i === 2) throw e; await page.waitForTimeout(3000); } }
    await page.waitForTimeout(2500); await page.evaluate(() => document.fonts.ready);
  }
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, locale: 'pl-PL', reducedMotion: 'reduce' });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      for (const [name, url] of [['aplikacja', '/aplikacja'], ['alerty', '/konto/alerty'], ['glowna', '/']]) {
        await open(page, url);
        results[`${width} ${name} overflow`] = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        if (name === 'aplikacja') results[`${width} aplikacja boxes`] = await page.evaluate(() => [...document.querySelectorAll('.sc-appguide__box')].map(b => { const r = b.getBoundingClientRect(); const h = b.querySelector('h3'); return { top: Math.round(r.top + scrollY), h: Math.round(r.height), bottom: Math.round(r.bottom + scrollY), titleH: Math.round(h.getBoundingClientRect().height), clipped: [...b.querySelectorAll('ol,p')].some(n => n.scrollHeight > n.clientHeight + 1) || b.scrollHeight > b.clientHeight + 1 }; }));
        if (name === 'aplikacja') results[`${width} touch targets`] = await page.evaluate(() => [...document.querySelectorAll('.sc-appguide a, .sc-appguide button')].filter(n => n.getBoundingClientRect().height < 43.5).map(n => n.textContent.trim()));
        await page.screenshot({ path: path.join(out, `${width}-${name}.png`), fullPage: true });
      }
      await open(page, '/#zainstaluj-aplikacje');
      results[`${width} dialog install`] = await page.evaluate(() => { const d = document.querySelector('dialog.sc-pwa-dialog'); return d && { open: d.open, text: d.innerText.slice(0, 160) }; });
      if (width === 1440) await page.screenshot({ path: path.join(out, `${width}-dialog-install.png`) });
      await open(page, '/#alerty-obserwowani');
      results[`${width} dialog push`] = await page.evaluate(() => { const d = document.querySelector('dialog.sc-pwa-dialog'); return d && { open: d.open, boxes: d.querySelectorAll('input[type=checkbox]').length, checked: [...d.querySelectorAll('input:checked')].length, text: d.innerText.slice(0, 260) }; });
      if (width === 1440) await page.screenshot({ path: path.join(out, `${width}-dialog-push.png`) });
      results[`${width} errors`] = errors;
      await page.close();
    }
    if (process.env.MANIFEST_SHOTS) {
      fs.mkdirSync(manifestDir, { recursive: true });
      const wide = await browser.newPage({ viewport: { width: 1280, height: 720 }, locale: 'pl-PL', reducedMotion: 'reduce' });
      await open(wide, '/'); await wide.screenshot({ path: path.join(manifestDir, 'wide-1.png') });
      await open(wide, '/aplikacja'); await wide.screenshot({ path: path.join(manifestDir, 'wide-2.png') });
      await wide.close();
      const narrow = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'pl-PL', reducedMotion: 'reduce' });
      await open(narrow, '/'); await narrow.screenshot({ path: path.join(manifestDir, 'narrow-1.png') });
      await open(narrow, '/konto/alerty'); await narrow.screenshot({ path: path.join(manifestDir, 'narrow-2.png') });
      await narrow.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(results, null, 1));
})();

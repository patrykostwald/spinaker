const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const fixture = require('./109-fixture.cjs');
const output = path.resolve(__dirname, '../../artifacts/109');
fs.mkdirSync(output, { recursive: true });
(async () => {
 const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args: ['--window-position=-32000,-32000','--window-size=1,1'] });
 const measurements = [];
 const errors = [];
 try {
 for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, locale: 'pl-PL', timezoneId: 'Europe/Warsaw', reducedMotion: 'reduce', serviceWorkers: 'block' });
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => {
   const url = new URL(route.request().url());
   if (!['127.0.0.1','localhost'].includes(url.hostname)) return route.abort();
   if (url.pathname.startsWith('/api/')) return route.fulfill({ json: fixture.response(url.pathname) });
   return route.continue();
  });
  for (const [name, url] of [['home','/'],['clinic','/klinika'],['diagnosis','/klinika/109'],['interview','/klinika/wywiady/109']]) {
   console.log('Capture', name, width);
   await page.goto(`http://127.0.0.1:3009${url}`, { waitUntil: 'networkidle', timeout: 120000 });
   await page.locator(name === 'diagnosis' || name === 'interview' ? '.sc-clinic-discussion' : '.sc-overview-message').first().waitFor({ timeout: 30000 }).catch(async error => { console.error(errors, await page.locator('body').innerText()); throw error; });
   await page.evaluate(() => document.fonts.ready);
   await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: true });
   const m = await page.evaluate(() => {
    const rect = el => { if (!el) return null; const r = el.getBoundingClientRect(); return { x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom }; };
    return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight,
     header: rect(document.querySelector('.sc-shell-header')), intro: rect(document.querySelector('.sc-overview-intro')),
     latest: rect(document.querySelector('#overview-latest')), cards: [...document.querySelectorAll('.sc-overview-card')].map(rect),
     metricLabels: [...document.querySelectorAll('.sc-overview-metrics dt')].map(rect),
     discussion: rect(document.querySelector('.sc-clinic-discussion')), main: rect(document.querySelector('.sc-spin-detail__diagnosis')),
     animation: [...document.querySelectorAll('.sc-overview-metrics dl > div')].map(el => getComputedStyle(el).animationName),
    };
   });
   measurements.push({ name, ...m });
   fs.writeFileSync(path.join(output, 'measurements.json'), JSON.stringify(measurements,null,2));
   assert.equal(m.scrollWidth, width, `${name}: overflow`);
   if (m.intro) assert.ok(m.intro.y - m.header.bottom <= (width === 390 ? 28 : 40), 'intro gap');
   if (name === 'home') { assert.ok(m.latest.y < 1800); assert.ok(!/spink|nitk/i.test(await page.locator('body').innerText())); }
   if (m.main && m.discussion) { assert.ok(Math.abs(m.main.x-m.discussion.x)<1); assert.ok(Math.abs(m.main.width-m.discussion.width)<1); }
  }
  await page.close();
 }
 fs.writeFileSync(path.join(output, 'measurements.json'), JSON.stringify(measurements,null,2));
 assert.deepEqual(errors, []);
 console.log('PASS: 8 screenshots, no overflow, intro spacing, content in 2 screens, discussion alignment, no page errors.');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });

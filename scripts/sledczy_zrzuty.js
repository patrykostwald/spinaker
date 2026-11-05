// Zrzuty 1440 i 390 px dla pętli Śledczy-Budowniczy + pomiar odstępów (zasada właściciela 8.10) jednym poleceniem.
// Użycie: node scripts/sledczy_zrzuty.js <katalog-wyjściowy> <url-lub-plik> [<url-lub-plik> ...]
//   np. node scripts/sledczy_zrzuty.js C:\Users\User\Desktop\projekty\przeszlosc-gotowe\runda-2 https://przeszlosc.today/?q=VAT
// Dla każdego adresu: <nazwa>-1440.png, <nazwa>-390.png (ekran i cała strona), <nazwa>-pomiar.json (położenia nagłówków,
// przycisków, pierwszego elementu pod menu, scrollWidth) i wynik odstepy.js (ZLE = do poprawy). Przeglądarka niewidoczna:
// headless bez --headless=new i okno poza ekranem (notatka „Invisible browser”).
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const PLAYWRIGHT = process.env.PLAYWRIGHT_DIR
  || 'C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright';
const CHROME = process.env.PLAYWRIGHT_CHROME
  || 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe';
const ODSTEPY = process.env.ODSTEPY_JS || 'C:/Users/User/zbudujmi/gust/odstepy.js';
const WIDTHS = [1440, 390];

const [outDir, ...targets] = process.argv.slice(2);
if (!outDir || !targets.length) {
  console.error('Użycie: node scripts/sledczy_zrzuty.js <katalog-wyjściowy> <url-lub-plik> [...]');
  process.exit(2);
}
const { chromium } = require(PLAYWRIGHT);

const slug = (t) => (t.replace(/^https?:\/\//, '').replace(/[^a-z0-9ąćęłńóśźż]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'strona').slice(0, 60);
const asUrl = (t) => (/^https?:|^file:/.test(t) ? t : 'file:///' + path.resolve(t).split('\\').join('/'));

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: CHROME,
    args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  const summary = [];
  for (const target of targets) {
    for (const width of WIDTHS) {
      const page = await browser.newPage({ viewport: { width, height: width > 800 ? 900 : 844 } });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      try {
        await page.goto(asUrl(target), { waitUntil: 'networkidle', timeout: 45000 });
      } catch (e) {
        console.error(`nie wczytano ${target} (${width}): ${e.message}`);
      }
      await page.waitForTimeout(1200);
      const base = path.join(outDir, `${slug(target)}-${width}`);
      await page.screenshot({ path: `${base}.png` });
      await page.screenshot({ path: `${base}-cala.png`, fullPage: true });
      // Pomiar zamiast zgadywania (zasada 9): górne i dolne krawędzie nagłówków i celów dotyku, pierwszy element pod menu.
      const measure = await page.evaluate(() => {
        const box = (e) => { const r = e.getBoundingClientRect(); return { top: Math.round(r.top + scrollY), bottom: Math.round(r.bottom + scrollY), left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height) }; };
        const vis = (e) => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
        const nav = document.querySelector('header, nav, [role="banner"]');
        const navBottom = nav ? box(nav).bottom : 0;
        const main = document.querySelector('main') || document.body;
        const first = [...main.querySelectorAll('*')].find((e) => vis(e) && e.children.length === 0 && e.textContent.trim());
        const small = [...document.querySelectorAll('a, button, input, select, [role="button"]')].filter(vis).map(box).filter((b) => b.w < 44 || b.h < 44).length;
        const unnamed = [...document.querySelectorAll('a, button, [role="button"]')].filter(vis).filter((e) => !(e.getAttribute('aria-label') || e.textContent.trim() || e.getAttribute('title'))).length;
        return {
          scrollWidth: document.documentElement.scrollWidth, innerWidth,
          firstElementGapBelowMenu: first ? box(first).top - navBottom : null,
          headings: [...document.querySelectorAll('h1, h2, h3')].filter(vis).slice(0, 40).map((h) => ({ tag: h.tagName, text: h.textContent.trim().slice(0, 60), ...box(h) })),
          touchTargetsBelow44: small, interactiveWithoutName: unnamed,
          overflowing: [...document.querySelectorAll('*')].filter(vis).filter((e) => e.getBoundingClientRect().right > innerWidth + 1).length,
        };
      });
      fs.writeFileSync(`${base}-pomiar.json`, JSON.stringify(measure, null, 1));
      let gaps = 'odstepy.js niedostępny';
      if (fs.existsSync(ODSTEPY)) {
        try { gaps = execFileSync('node', [ODSTEPY, asUrl(target), String(width)], { encoding: 'utf8', timeout: 90000 }); } catch (e) { gaps = `odstepy.js błąd: ${e.message}`; }
      }
      fs.writeFileSync(`${base}-odstepy.txt`, gaps);
      const bad = /ZLE/.test(gaps);
      const gap = measure.firstElementGapBelowMenu;
      const gapLimit = width > 800 ? 40 : 28;
      summary.push({ target, width, scrollOk: measure.scrollWidth <= width, firstGap: gap, firstGapOk: gap == null || gap <= gapLimit,
        touchTargetsBelow44: measure.touchTargetsBelow44, interactiveWithoutName: measure.interactiveWithoutName, overflowing: measure.overflowing, odstepyOk: !bad });
      console.log(`${slug(target)} ${width}: scroll ${measure.scrollWidth <= width ? 'ok' : 'ZLE ' + measure.scrollWidth}, pierwszy pod menu ${gap} px (limit ${gapLimit}), cele < 44 px: ${measure.touchTargetsBelow44}, bez nazwy: ${measure.interactiveWithoutName}, odstępy ${bad ? 'ZLE' : 'ok'}`);
      await page.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(outDir, 'podsumowanie.json'), JSON.stringify(summary, null, 1));
  const failures = summary.filter((s) => !s.scrollOk || !s.firstGapOk || !s.odstepyOk || s.interactiveWithoutName > 0);
  console.log(failures.length ? `DO POPRAWY: ${failures.length} z ${summary.length} pomiarów` : `OK: ${summary.length} pomiarów bez uwag`);
  process.exit(failures.length ? 1 : 0);
})();

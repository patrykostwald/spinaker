// Zrzuty 1440 i 390 px oraz pomiar położeń boksów. Użycie: node zrzuty.mjs <katalog-koncepcji> <katalog-wyjścia>
import { chromium } from 'playwright';
import path from 'node:path';

const [, , kat, wyj] = process.argv;
const pliki = [['A-rzezba-nocna.html', 'A'], ['B-makieta-polski.html', 'B']];
const szer = [[1440, 900], [390, 844]];
const przegl = await chromium.launch({ headless: true });
const raport = [];
for (const [plik, lit] of pliki) {
  for (const [w, h] of szer) {
    for (const wariant of ['', 'prosty', 'rcb', 'ruch-wyl']) {
      if (wariant === 'rcb' && lit !== 'B') continue;
      const ctx = await przegl.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, reducedMotion: wariant === 'ruch-wyl' ? 'reduce' : 'no-preference' });
      const s = await ctx.newPage();
      const bledy = [];
      s.on('console', m => { if (m.type() === 'error') bledy.push(m.text()); });
      s.on('pageerror', e => bledy.push(String(e)));
      const t0 = Date.now();
      await s.goto('file://' + path.resolve(kat, plik));
      await s.waitForTimeout(1600);
      const czas = Date.now() - t0;
      if (wariant === 'prosty') await s.click('#przel-prosty');
      if (wariant === 'rcb') await s.click('.rcb__karta[data-id="r2"]');
      await s.waitForTimeout(1300);
      await s.evaluate(() => window.scrollTo(0, 0));
      await s.mouse.move(0, 0);
      await s.waitForTimeout(200);
      const nazwa = `${lit}-${w}${wariant ? '-' + wariant : ''}.png`;
      await s.screenshot({ path: path.join(wyj, nazwa), fullPage: true });
      const pomiar = await s.evaluate(() => {
        const r = e => { const b = e.getBoundingClientRect(); return [Math.round(b.top + scrollY), Math.round(b.bottom + scrollY), Math.round(b.left), Math.round(b.right)]; };
        const out = {};
        out.pasek = r(document.querySelector('.pasek'));
        out.glowa = r(document.querySelector('.scena-glowa'));
        out.scena = r(document.querySelector('.scena'));
        document.querySelectorAll('.boks').forEach((b, i) => { if (b.offsetParent) out['boks' + i + ':' + (b.querySelector('.boks__tytul')?.textContent || '')] = r(b); });
        const zr = [...document.querySelectorAll('.zrodlo')].map(e => e.getBoundingClientRect().height);
        out.zrodlaWys = [Math.min(...zr), Math.max(...zr)];
        const zd = [...document.querySelectorAll('.zdarzenie')].map(e => e.getBoundingClientRect().height);
        out.zdarzeniaWys = [Math.min(...zd), Math.max(...zd)];
        const rc = [...document.querySelectorAll('.rcb__karta')].map(e => e.getBoundingClientRect().height);
        if (rc.length) out.rcbWys = [Math.min(...rc), Math.max(...rc)];
        out.przepelnienie = document.documentElement.scrollWidth > innerWidth;
        // tytuły boksów w jednej linii
        out.tytulyLamane = [...document.querySelectorAll('.boks__tytul, .scena-glowa h1')].filter(e => e.getBoundingClientRect().height > 30).map(e => e.textContent);
        return out;
      });
      raport.push({ nazwa, czas, bledy, pomiar });
      await ctx.close();
    }
  }
}
await przegl.close();
const fs = await import('node:fs');
fs.writeFileSync(path.join(wyj, 'pomiar.json'), JSON.stringify(raport, null, 1));
for (const x of raport) console.log(x.nazwa, x.czas + ' ms', 'błędy:', x.bledy.length ? x.bledy : 0, 'przepełnienie:', x.pomiar.przepelnienie, 'łamane tytuły:', x.pomiar.tytulyLamane.join('|') || 0);

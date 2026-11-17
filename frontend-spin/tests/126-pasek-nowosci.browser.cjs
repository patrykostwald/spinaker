// przeszłość.today (13.10.2026): pasek "Ostatnio w bazie" w przeglądarce. Wymaga działającego `next dev` (PT_URL, domyślnie
// http://localhost:3012/przeszlosc); API strony głównej jest podstawiane (route) z fikstury w kształcie /api/przeszlosc/start/.
// Sprawdza: stałą wysokość 40 px (320-1480 px), brak skoku układu (szkielet -> dane -> zmiana pozycji), brak poziomego przewijania
// strony i widocznych pasków, równe odstępy (menu -> pasek -> hero), cele 44 px, kontrast, pauzę (najechanie, fokus, przycisk),
// reduced motion ("Następna"), ukrycie przy braku danych i błędzie API. Zrzuty 1440 / 390 do PT_SHOTS (gdy podane).
// Uruchomienie: node tests/126-pasek-nowosci.browser.cjs   (Playwright z npx cache, Chromium poza ekranem, headless)
const path = require('node:path');
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const URL_ = process.env.PT_URL || 'http://localhost:3012/przeszlosc';
const SHOTS = process.env.PT_SHOTS || '';
const EXE = 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe';

const START = { counts: { people: 1387695, organisations: 9037, records: 412880, posts: 76512, diagnoses: 1204, articles: 50311 }, topics_enabled: false, auto_topics: [],
  latest: [
    { title: 'Druk nr 1234: rządowy projekt ustawy o zmianie ustawy o Centralnym Porcie Komunikacyjnym oraz niektórych innych ustaw', date: '2026-10-13', kind: 'Druk', url: 'https://orka.sejm.gov.pl/Druki10ka.nsf/0/1234' },
    { title: 'Interpelacja nr 777 w sprawie cen energii dla gospodarstw domowych', date: '2026-10-13', kind: 'Interpelacja', url: 'https://api.sejm.gov.pl/sejm/term10/interpellations/777' },
    { title: 'Głosowanie nr 12 nad projektem ustawy o zmianie ustawy o VAT', date: '2026-10-12', kind: 'Głosowanie', url: 'https://www.sejm.gov.pl/Sejm10.nsf/agent.xsp?symbol=glosowania' },
    { title: 'Uchwała Senatu w sprawie ustawy o KPO', date: '2026-10-10', kind: 'Senat', url: 'https://www.senat.gov.pl/prace/uchwaly/1' },
    { title: 'Projekt rozporządzenia Ministra Finansów w RCL', date: '2026-10-09', kind: 'Projekt rządowy', url: 'https://legislacja.rcl.gov.pl/projekt/1' },
    { title: 'Posiedzenie Komisji Finansów Publicznych', date: '2026-10-08', kind: 'Komisja', url: 'https://www.sejm.gov.pl/komisje/1' },
  ], scheduled: [] };

const fails = [];
const bad = (m) => { fails.push(m); console.log('ZLE  ' + m); };
const ok = (m) => console.log('ok   ' + m);
const lum = (c) => { const [r, g, b] = c.match(/\d+(\.\d+)?/g).map(Number); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };

async function page(b, w, o = {}) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, reducedMotion: o.reduced ? 'reduce' : 'no-preference' });
  // pasek: klasyczny pasek przewijania, żeby wykryć jego widoczność (bez --hide-scrollbars)
  await ctx.addInitScript(t => { try { localStorage.setItem('spin-theme', t); } catch (e) {} }, o.theme || 'dark');
  const p = await ctx.newPage();
  let release;
  const gate = new Promise(r => { release = r; });
  await p.route('**/api/**', async r => {
    const u = r.request().url();
    if (/\/api\/przeszlosc\/start\//.test(u)) {
      if (o.hold) await gate;
      if (o.start === 'error') return r.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(o.start ?? START) });
    }
    if (/\/api\/przeszlosc\/temat\//.test(u)) return r.fulfill({ status: 404, body: '' });
    // reszta API (paski, odstępstwa, dostęp): stan błędu komponentów, żeby pusty JSON nie wywracał strony
    return r.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
  });
  if (o.css) await ctx.addInitScript(css => { document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }); }, o.css);
  await p.goto(URL_ + '?__bez_uwag=1', { waitUntil: 'domcontentloaded' });
  // strona osobna (useStandalone) chowa menu spin.clinic po hydracji: mierzymy dopiero, gdy pasek przeszłości jest przy górnej krawędzi
  await p.waitForFunction(() => { const t = document.querySelector('.pt-top'); return t && t.getBoundingClientRect().top + scrollY < 1; });
  return { p, ctx, release };
}
const M = () => ({
  tick: (() => { const t = document.querySelector('.pt-tick'); if (!t) return null; const q = t.getBoundingClientRect(); return { top: q.top + scrollY, bottom: q.bottom + scrollY, h: Math.round(q.height * 10) / 10, w: q.width, state: t.dataset.state }; })(),
  barLine: (() => { const t = document.querySelector('.pt-top'); const q = t.getBoundingClientRect(); return q.bottom + scrollY; })(),
  heroFirst: (() => { const e = document.querySelector('.pt-hero .px-kicker') || document.querySelector('.px-result'); const q = e.getBoundingClientRect(); return q.top + scrollY; })(),
  heroTop: (() => { const e = document.querySelector('.pt-hero'); const q = e.getBoundingClientRect(); return q.top + scrollY; })(),
  scrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  bars: [...document.querySelectorAll('body *')].filter(e => { const cs = getComputedStyle(e); const q = e.getBoundingClientRect(); if (!q.width || !q.height) return false;
    const sx = /(auto|scroll)/.test(cs.overflowX) && e.scrollWidth > e.clientWidth + 1, sy = /(auto|scroll)/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 1; if (!sx && !sy) return false;
    const barPx = (e.offsetHeight - e.clientHeight) + (e.offsetWidth - e.clientWidth) - (parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth));
    return cs.scrollbarWidth !== 'none' || barPx > 0; }).map(e => e.tagName + '.' + String(e.className).split(' ')[0]),
  targets: [...document.querySelectorAll('.pt-tick a, .pt-tick button')].filter(e => e.getBoundingClientRect().width > 0).map(e => { const q = e.getBoundingClientRect(); return { t: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 16) || e.className, w: Math.round(q.width), h: Math.round(q.height) }; }),
  // linia bazowa każdego widocznego tekstu wiersza: sonda inline-block 0x0 (jej górna krawędź = linia bazowa), różnica ma być <= 1 px
  baselines: [...document.querySelectorAll('.pt-tick__lab, .pt-tick__kind, .pt-tick__time, .pt-tick__t, .pt-tick__srcname, .pt-tick__all .pt-tick__txt')].filter(e => { const q = e.getBoundingClientRect(); return q.width > 2 && q.height > 2; }).map(e => {
    const probe = document.createElement('span'); probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline;padding:0;margin:0;border:0;';
    e.appendChild(probe); const y = probe.getBoundingClientRect().top + scrollY; probe.remove();
    return { t: e.className.split(' ')[0], y: Math.round(y * 10) / 10 }; }),
  // tytuł ucięty tylko wtedy, gdy pełny tekst naprawdę się nie mieści (pomiar canvasem w komputowanym kroju)
  titleRoom: (() => { const t = document.querySelector('.pt-tick__title'); if (!t) return null; const cs = getComputedStyle(t); const c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const full = c.measureText(t.getAttribute('title')).width; return { full: Math.round(full), box: t.clientWidth, cut: t.dataset.cut !== undefined, overflow: t.scrollWidth > t.clientWidth + 1 }; })(),
  srcShown: (() => { const s = document.querySelector('.pt-tick__src'); return Boolean(s && s.getBoundingClientRect().width > 0); })(),
  item: (() => { const e = document.querySelector('.pt-tick__item'); if (!e) return null; const t = e.querySelector('.pt-tick__title'); const q = e.getBoundingClientRect(), v = e.parentElement.getBoundingClientRect();
    // skrót po całym słowie: widoczny tekst (bez "…") jest przedrostkiem pełnego tytułu zakończonym na granicy słowa
    const vis = (t.querySelector('.pt-tick__t') || t).textContent, full = t.getAttribute('title');
    const base = vis.endsWith('…') ? vis.slice(0, -1) : vis;
    const wordCut = vis === full || (full.startsWith(base) && (base.length === full.length || /[\s,;:.\-]/.test(full[base.length])));
    return { text: full, shown: vis, titleW: Math.round(t.getBoundingClientRect().width), clipped: vis !== full, wordCut, overflowView: q.right > v.right + 1, h: Math.round(q.height), right: Math.round(v.right - q.right) }; })(),
  colors: (() => { const t = document.querySelector('.pt-tick'); if (!t || !t.querySelector('.pt-tick__title')) return null; const g = s => { const e = t.querySelector(s); return e ? getComputedStyle(e).color : null; }; const bg = getComputedStyle(t).backgroundColor;
    return { bg, title: g('.pt-tick__title'), meta: g('.pt-tick__time'), kind: g('.pt-tick__kind'), src: g('.pt-tick__src'), link: g('.pt-tick__all'), btn: g('.pt-tick__btn'), lab: g('.pt-tick__lab') }; })(),
  fonts: (() => { const t = document.querySelector('.pt-tick'); if (!t || !t.querySelector('.pt-tick__title')) return null; const f = s => { const e = t.querySelector(s); return e ? getComputedStyle(e).fontFamily.split(',')[0] : null; }; return { lab: f('.pt-tick__lab'), title: f('.pt-tick__title'), kind: f('.pt-tick__kind') }; })(),
});

(async () => {
  const b = await chromium.launch({ headless: true, executablePath: EXE, args: ['--window-position=-32000,-32000', '--window-size=1,1'] });

  // 1. stan ładowania -> dane: szkielet tej samej wysokości, hero bez skoku; zmiana pozycji bez skoku
  {
    const { p, ctx, release } = await page(b, 1440, { hold: true, css: '.pt-v3 .px{--fx-ticker-interval:500ms;--fx-ticker-fade:120ms}' });
    await p.waitForSelector('.pt-tick[data-state="loading"]');
    const before = await p.evaluate(M);
    release(); await p.waitForSelector('.pt-tick[data-state="running"]');
    const after = await p.evaluate(M);
    if (!before.tick || before.tick.h !== 40) bad(`szkielet: wysokość ${before.tick && before.tick.h} (ma być 40)`); else ok('szkielet 40 px');
    if (after.tick.h !== 40) bad(`pasek z danymi: wysokość ${after.tick.h}`); else ok('pasek 40 px');
    if (Math.abs(before.heroTop - after.heroTop) > .5) bad(`skok układu po danych: hero ${before.heroTop} -> ${after.heroTop}`); else ok('hero bez skoku po nadejściu danych');
    const t0 = after.item.text;
    await p.waitForFunction(t => document.querySelector('.pt-tick__title') && document.querySelector('.pt-tick__title').getAttribute('title') !== t, t0, { timeout: 4000 });
    const rot = await p.evaluate(M);
    if (rot.tick.h !== 40 || Math.abs(rot.heroTop - after.heroTop) > .5) bad('skok układu przy zmianie pozycji'); else ok(`zmiana pozycji bez skoku ("${t0.slice(0, 24)}…" -> "${rot.item.text.slice(0, 24)}…")`);
    // kolejność: po czasie malejąco (druga pozycja = Interpelacja z 13.10)
    if (!/Interpelacja/.test(rot.item.text)) bad('kolejność: druga pozycja powinna być z 13.10 (Interpelacja)'); else ok('kolejność po czasie');
    // najechanie = pauza, zdjęcie = wznowienie; przycisk Pauza = aria-pressed i brak zmiany przez 2 interwały
    // najechanie na stały element paska (etykietę), nie na pozycję, która co interwał jest podmieniana
    await p.hover('.pt-tick__lab');
    let st = await p.waitForFunction(() => document.querySelector('.pt-tick').dataset.state, null, { timeout: 800, polling: 50 }).then(() => p.evaluate(() => document.querySelector('.pt-tick').dataset.state)).catch(() => 'brak');
    for (let k = 0; k < 10 && st !== 'paused'; k++) { await p.waitForTimeout(60); st = await p.evaluate(() => document.querySelector('.pt-tick').dataset.state); }
    if (st !== 'paused') bad(`najechanie: stan ${st}`); else ok('najechanie = pauza');
    await p.mouse.move(5, 5); await p.waitForTimeout(150);
    st = await p.evaluate(() => document.querySelector('.pt-tick').dataset.state);
    if (st !== 'running') bad(`zdjęcie kursora: stan ${st}`); else ok('zdjęcie kursora = wznowienie');
    await p.click('.pt-tick__btn'); await p.mouse.move(5, 5); await p.waitForTimeout(100);
    const pr = await p.evaluate(() => [document.querySelector('.pt-tick__btn').getAttribute('aria-pressed'), document.querySelector('.pt-tick__btn').getAttribute('title'), document.querySelector('.pt-tick').dataset.state, document.querySelector('.pt-tick__title').textContent]);
    await p.waitForTimeout(1300);
    const pr2 = await p.evaluate(() => document.querySelector('.pt-tick__title').textContent);
    if (pr[0] !== 'true' || pr[1] !== 'Wznów' || pr[2] !== 'paused' || pr[3] !== pr2) bad(`Pauza: ${JSON.stringify(pr)} -> "${pr2.slice(0, 20)}"`); else ok('przycisk Pauza: aria-pressed=true, "Wznów", pozycja stoi');
    await p.click('.pt-tick__btn'); await p.mouse.move(5, 5); await p.waitForTimeout(100);
    const re = await p.evaluate(() => [document.querySelector('.pt-tick__btn').getAttribute('aria-pressed'), document.querySelector('.pt-tick').dataset.state]);
    if (re[0] !== 'false' || re[1] !== 'running') bad(`Wznów: ${JSON.stringify(re)}`); else ok('Wznów = running');
    // fokus klawiatury = pauza; Tab przechodzi po: źródło, Pauza, Wszystkie nowości
    // fokus programowy po kliknięciu myszą nie jest :focus-visible (tak ma być): pauzę daje dopiero fokus z klawiatury (Tab)
    await p.focus('.pt-tick__src'); await p.keyboard.press('Tab'); await p.waitForTimeout(100);
    const order = [await p.evaluate(() => document.activeElement.className)];
    st = await p.evaluate(() => document.querySelector('.pt-tick').dataset.state);
    if (st !== 'paused') bad(`fokus z klawiatury: stan ${st}`); else ok('fokus z klawiatury = pauza');
    await p.keyboard.press('Tab'); order.push(await p.evaluate(() => document.activeElement.className));
    if (!/pt-tick__btn/.test(order[0]) || !/pt-tick__all/.test(order[1])) bad(`kolejność Tab: ${order.join(' > ')}`); else ok('klawiatura: źródło > Pauza > Wszystkie nowości');
    await p.keyboard.press('Enter'); await p.waitForTimeout(1500); // globals.css: scroll-behavior smooth
    const anchored = await p.evaluate(() => { const s = document.getElementById('najnowsze'); const q = s.getBoundingClientRect(); return { hash: location.hash, top: Math.round(q.top), atEnd: scrollY + innerHeight >= document.documentElement.scrollHeight - 2 }; });
    if (anchored.hash !== '#najnowsze' || anchored.top < 0 || (anchored.top > 60 && !anchored.atEnd)) bad(`kotwica: ${JSON.stringify(anchored)}`); else ok(`kotwica #najnowsze (sekcja ${anchored.top} px od góry okna${anchored.atEnd ? ', koniec strony' : ''})`);
    await ctx.close();
  }

  // 2. sweep 320-1920: wysokość stała, bez poziomego przewijania i pasków, równe odstępy, cele 44 px, jedna linia bazowa,
  //    tytuł ucięty tylko bez miejsca, domena tylko od 1100 px
  for (let w = 320; w <= 1920; w += 40) {
    const { p, ctx } = await page(b, w);
    // pomiar po zakończeniu animacji wejścia pozycji (translateY -4 px -> 0, --fx-ticker-fade 320 ms)
    await p.waitForSelector('.pt-tick[data-state="running"]'); await p.waitForTimeout(450);
    const m = await p.evaluate(M);
    const gapUp = Math.round(m.tick.top - m.barLine), gapDown = Math.round(m.heroFirst - m.tick.bottom);
    const exp = w <= 760 ? 24 : 24;
    const small = m.targets.filter(t => t.h < 44 || t.w < 44);
    const probs = [];
    if (m.tick.h !== 40) probs.push(`h=${m.tick.h}`);
    if (m.scrollX) probs.push('przewijanie poziome strony');
    if (m.bars.length) probs.push('paski: ' + m.bars.join(','));
    if (gapUp !== exp || gapDown !== exp) probs.push(`odstępy ${gapUp}/${gapDown} (ma być ${exp}/${exp})`);
    if (small.length) probs.push('cele <44: ' + small.map(t => `${t.t} ${t.w}x${t.h}`).join(', '));
    if (m.item.overflowView || m.item.right < 0) probs.push(`pozycja wystaje z pola (${m.item.right})`);
    if (m.item.titleW < 60) probs.push(`tytuł ${m.item.titleW} px (za mało miejsca)`);
    if (!m.item.wordCut) probs.push(`tytuł ucięty w pół słowa: "${m.item.shown}"`);
    const ys = m.baselines.map(b => b.y), spread = Math.max(...ys) - Math.min(...ys);
    if (spread > 1) probs.push(`linie bazowe rozjechane o ${spread.toFixed(1)} px: ${m.baselines.map(b => `${b.t} ${b.y}`).join(', ')}`);
    if (m.titleRoom.cut && m.titleRoom.full <= m.titleRoom.box - 4) probs.push(`tytuł ucięty mimo miejsca (tekst ${m.titleRoom.full} px, pole ${m.titleRoom.box} px)`);
    if (m.titleRoom.overflow) probs.push('tytuł wylewa się z pola');
    if (m.srcShown !== (w >= 1100)) probs.push(`domena źródła ${m.srcShown ? 'widoczna' : 'ukryta'} przy ${w} px`);
    if (probs.length) bad(`${w} px: ${probs.join('; ')}`); else ok(`${w} px: h 40, odstępy ${gapUp}/${gapDown}, baseline ±${spread.toFixed(1)}, tytuł ${m.item.titleW} px${m.item.clipped ? ` ("${m.item.shown}")` : ' (cały)'}, cele ${m.targets.map(t => `${t.w}x${t.h}`).join(' ')}`);
    await ctx.close();
  }

  // 3. kontrast i kroje (ciemny i jasny), zrzuty 1440 / 390
  for (const theme of ['dark', 'light']) for (const w of [1440, 390]) {
    const { p, ctx } = await page(b, w, { theme });
    await p.waitForSelector('.pt-tick[data-state="running"]'); await p.waitForTimeout(400);
    const m = await p.evaluate(M);
    const c = m.colors, r = k => ratio(c[k], c.bg).toFixed(1);
    const need = { title: 7, meta: 4.5, kind: 4.5, src: 4.5, link: 4.5, btn: 4.5, lab: 4.5 };
    const low = Object.entries(need).filter(([k, v]) => ratio(c[k], c.bg) < v).map(([k]) => `${k} ${r(k)}`);
    if (low.length) bad(`${theme} ${w}: kontrast ${low.join(', ')}`); else ok(`${theme} ${w}: kontrast tytuł ${r('title')}, meta ${r('meta')}, rodzaj ${r('kind')}, źródło ${r('src')}, odnośnik ${r('link')}, przycisk ${r('btn')}, etykieta ${r('lab')}`);
    if (!/Montserrat/i.test(m.fonts.lab) || /Montserrat/i.test(m.fonts.title)) bad(`${theme} ${w}: kroje ${JSON.stringify(m.fonts)}`); else if (theme === 'dark') ok(`${w}: etykieta ${m.fonts.lab}, treść ${m.fonts.title}`);
    if (SHOTS && theme === 'dark') { await p.screenshot({ path: path.join(SHOTS, `pasek-${w}.png`), clip: { x: 0, y: 0, width: w, height: Math.min(900, w === 390 ? 520 : 420) } }); }
    await ctx.close();
  }

  // 4. reduced motion: stan statyczny, przycisk "Następna" zmienia pozycję, bez animacji
  {
    const { p, ctx } = await page(b, 1440, { reduced: true });
    await p.waitForSelector('.pt-tick[data-state="static"]');
    const a = await p.evaluate(() => [document.querySelector('.pt-tick__btn').getAttribute('title'), document.querySelector('.pt-tick__title').textContent, getComputedStyle(document.querySelector('.pt-tick__title')).animationName]);
    await p.click('.pt-tick__btn'); await p.waitForTimeout(100);
    const t2 = await p.evaluate(() => document.querySelector('.pt-tick__title').textContent);
    if (a[0] !== 'Następna pozycja' || a[1] === t2 || a[2] !== 'none') bad(`reduced motion: ${JSON.stringify(a)} -> "${t2.slice(0, 20)}"`); else ok('reduced motion: "Następna" zmienia pozycję, animacja wyłączona');
    await ctx.close();
  }

  // 5. brak danych i błąd API = brak paska (bez "zero"); hero wtedy 32 px pod menu jak dotąd
  for (const [name, start] of [['brak danych', { ...START, latest: [] }], ['2 pozycje', { ...START, latest: START.latest.slice(0, 2) }], ['błąd API', 'error']]) {
    const { p, ctx } = await page(b, 1440, { start });
    await p.waitForTimeout(900);
    const m = await p.evaluate(M);
    const gap = Math.round(m.heroFirst - m.barLine);
    if (m.tick) bad(`${name}: pasek widoczny (${m.tick.state})`); else if (gap !== 32) bad(`${name}: hero ${gap} px pod menu (ma być 32)`); else ok(`${name}: paska nie ma, hero 32 px pod menu`);
    await ctx.close();
  }

  await b.close();
  console.log(fails.length ? `\nZLE: ${fails.length}` : '\nWSZYSTKO OK');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });

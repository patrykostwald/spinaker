// przeszłość.today (14.10.2026): pasek liczb "Co jest w bazie" pod wyszukiwarką - pięć równych komórek, liczba i podpis
// wycentrowane w każdej (uwaga właściciela: "wycentruj jednak te wszystkie elementy w boksach"), separator 1 px między komórkami,
// wspólna linia bazowa liczb i podpisów w rzędzie, liczby w jednej linii, podpisy do 2 linii; na tablecie 3 + 2 (druga para
// szersza, bez sieroty), na telefonie 2 + 2 + 1 (ostatnia na całą szerokość). Sweep 320-1480: bez ucięć, łamań i przewijania.
// Wymaga `next dev` (PT_URL, domyślnie http://localhost:3011/przeszlosc); API strony głównej podstawiane z fikstury.
// Uruchomienie: node tests/128-pasek-liczb.browser.cjs
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const URL_ = process.env.PT_URL || 'http://localhost:3011/przeszlosc';
const EXE = 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe';
const START = { counts: { people: 775, organisations: 800, records: 1408901, posts: 9415, diagnoses: 1204, articles: 527835 }, topics_enabled: false, auto_topics: [], latest: [], scheduled: [] };
const fails = [];
const bad = (m) => { fails.push(m); console.log('ZLE  ' + m); };
const ok = (m) => console.log('ok   ' + m);

async function open(b, w, counts = START.counts) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, reducedMotion: 'reduce' });
  await ctx.addInitScript(() => { try { localStorage.setItem('spin-theme', 'dark'); } catch (e) {} });
  const p = await ctx.newPage();
  await p.route('**/api/**', r => { const u = r.request().url();
    if (/\/api\/przeszlosc\/start\//.test(u)) return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...START, counts }) });
    return r.fulfill({ status: /temat/.test(u) ? 404 : 500, contentType: 'application/json', body: '{}' }); });
  await p.goto(URL_ + '?__bez_uwag=1', { waitUntil: 'domcontentloaded', timeout: 180000 });
  await p.waitForFunction(() => /\d/.test(document.querySelector('.px-proof b')?.textContent || ''), null, { timeout: 120000 });
  await p.waitForTimeout(200);
  return { p, ctx };
}
const M = () => {
  const proof = document.querySelector('.px-proof'); const cells = [...proof.children];
  // sonda na początku elementu = linia bazowa PIERWSZEJ linii (podpis może mieć 1 albo 2 linie; wspólna ma być pierwsza)
  const probe = (el) => { const s = document.createElement('span'); s.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline;'; el.prepend(s); const y = s.getBoundingClientRect().top; s.remove(); return Math.round(y * 10) / 10; };
  const rows = {}; cells.forEach(c => { const t = Math.round(c.getBoundingClientRect().top); (rows[t] ??= []).push(c); });
  const info = (c) => { const b = c.querySelector('b'), s = c.querySelector('span'); const cr = c.getBoundingClientRect(), br = b.getBoundingClientRect(), sr = s.getBoundingClientRect();
    return { w: Math.round(cr.width), align: getComputedStyle(c).textAlign, numOff: Math.round((br.left + br.right) / 2 - (cr.left + cr.right) / 2), capOff: Math.round((sr.left + sr.right) / 2 - (cr.left + cr.right) / 2), numBase: probe(b), capBase: probe(s), numFont: getComputedStyle(b).fontSize,
      numOver: b.scrollWidth > b.clientWidth + 1, capLines: Math.round(sr.height / parseFloat(getComputedStyle(s).lineHeight)), border: getComputedStyle(c).borderLeftWidth }; };
  return { rows: Object.values(rows).map(r => r.map(info)), scrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1, n: cells.length };
};

(async () => {
  const b = await chromium.launch({ headless: true, executablePath: EXE, args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  for (const [w, rowsExpected] of [[1440, [5]], [1024, [3, 2]], [768, [3, 2]], [390, [2, 2, 1]]]) {
    const { p, ctx } = await open(b, w);
    const m = await p.evaluate(M);
    const shape = m.rows.map(r => r.length);
    JSON.stringify(shape) === JSON.stringify(rowsExpected) ? ok(`${w}: układ ${shape.join('+')}`) : bad(`${w}: układ ${shape.join('+')}, oczekiwano ${rowsExpected.join('+')}`);
    const all = m.rows.flat();
    all.every(c => c.align === 'center' && Math.abs(c.numOff) <= 1 && Math.abs(c.capOff) <= 1) ? ok(`${w}: liczby i podpisy wycentrowane w komórkach`) : bad(`${w}: nie wycentrowane: ${all.map(c => `${c.align}/${c.numOff}/${c.capOff}`).join(' ')}`);
    m.rows.every(r => new Set(r.map(c => c.numBase)).size === 1 && new Set(r.map(c => c.capBase)).size === 1) ? ok(`${w}: wspólna linia bazowa liczb i podpisów w każdym rzędzie`) : bad(`${w}: linie bazowe różne: ${m.rows.map(r => r.map(c => `${c.numBase}/${c.capBase}`).join(' ')).join(' | ')}`);
    new Set(all.map(c => c.numFont)).size === 1 ? ok(`${w}: jeden rozmiar liczb (${all[0].numFont})`) : bad(`${w}: różne rozmiary liczb: ${[...new Set(all.map(c => c.numFont))].join(' ')}`);
    // border 1 px bywa w computed style 0,909 px (skalowanie na węższych ekranach) - liczy się "jest / nie ma"
    const sep = (c) => parseFloat(c.border) > 0.5;
    m.rows.every(r => !sep(r[0]) && r.slice(1).every(sep)) ? ok(`${w}: separatory 1 px między komórkami, bez linii na brzegu`) : bad(`${w}: separatory: ${m.rows.map(r => r.map(c => c.border).join(',')).join(' | ')}`);
    all.every(c => !c.numOver && c.capLines <= 2) && !m.scrollX ? ok(`${w}: liczby w jednej linii, podpisy do 2 linii, bez przewijania`) : bad(`${w}: ucięcia/łamania: ${all.map(c => `${c.numOver}/${c.capLines}`).join(' ')} scrollX=${m.scrollX}`);
    await ctx.close();
  }
  // sweep 320-1480 co 40 px, także z długą liczbą (123 456 789)
  for (const counts of [START.counts, { ...START.counts, records: 123456789 }]) {
    const problems = [];
    for (let w = 320; w <= 1480; w += 40) {
      const { p, ctx } = await open(b, w, counts); const m = await p.evaluate(M); const all = m.rows.flat();
      if (m.scrollX || all.some(c => c.numOver || c.capLines > 2 || c.align !== 'center') || new Set(all.map(c => c.numFont)).size !== 1 || m.rows.some(r => new Set(r.map(c => c.numBase)).size !== 1)) problems.push(w);
      await ctx.close();
    }
    problems.length ? bad(`sweep (${counts.records}): problemy na ${problems.join(', ')}`) : ok(`sweep 320-1480 (${counts.records.toLocaleString('pl-PL')}): bez ucięć, łamań i przewijania, jeden rozmiar, wspólna linia bazowa`);
  }
  await b.close();
  console.log(fails.length ? `\n${fails.length} ZLE` : '\nwszystko ok');
  process.exit(fails.length ? 1 : 0);
})();

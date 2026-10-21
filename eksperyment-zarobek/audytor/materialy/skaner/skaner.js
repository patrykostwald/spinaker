// Skaner dostępności iapply - prototyp (wersja robocza Audytora, runda 1).
// Użycie: node skaner.js <adres> [limit_podstron=20]
// Skanuje tylko stronę, której właściciel zamówił przegląd albo o niego poprosił. Szanuje robots.txt, 1 strona na sekundę.
// Wynik: raport-<host>.json i raport-<host>.html (ciemny motyw), lista podstron do ręcznego testu.
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

function loadPlaywright() {
  for (const base of [__filename, '/opt/node-tools/node_modules/', path.join(require('os').homedir(), 'node-tools/node_modules/')]) {
    try { return createRequire(base)('playwright'); } catch (e) { /* następna ścieżka */ }
  }
  throw new Error('Brak playwright: npm i playwright');
}
const { chromium } = loadPlaywright();
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const AXE_PL = fs.readFileSync(path.join(path.dirname(require.resolve('axe-core/axe.min.js')), 'locales/pl.json'), 'utf8');

const VIEWPORTS = [{ name: '1440', width: 1440, height: 900 }, { name: '390', width: 390, height: 844 }];
const WAGA = { critical: 'krytyczny', serious: 'poważny', moderate: 'średni', minor: 'drobny' };
const KOLEJNOSC = { critical: 0, serious: 1, moderate: 2, minor: 3 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// wcag111 -> 1.1.1; wcag1410 -> 1.4.10
function kryteria(tags) {
  return tags.filter((t) => /^wcag\d{3,}$/.test(t)).map((t) => {
    const d = t.slice(4);
    return `${d[0]}.${d[1]}.${d.slice(2)}`;
  });
}
const poziom = (tags) => (tags.includes('wcag2aa') || tags.includes('wcag21aa') || tags.includes('wcag22aa') ? 'AA'
  : tags.includes('wcag2a') || tags.includes('wcag21a') ? 'A' : 'dobra praktyka');

async function robotsDisallow(page, origin) {
  if (origin.startsWith('file:')) return [];
  try {
    const res = await page.request.get(origin + '/robots.txt', { timeout: 10000 });
    if (!res.ok()) return [];
    const rules = []; let star = false;
    for (const line of (await res.text()).split(/\r?\n/)) {
      const [k, ...v] = line.split(':'); const val = v.join(':').trim();
      if (/^user-agent$/i.test(k.trim())) star = val === '*';
      else if (star && /^disallow$/i.test(k.trim()) && val) rules.push(val);
    }
    return rules;
  } catch (e) { return []; }
}

async function main() {
  const start = process.argv[2];
  const limit = parseInt(process.argv[3] || '20', 10);
  if (!start) { console.error('Użycie: node skaner.js <adres> [limit]'); process.exit(1); }
  const startUrl = new URL(start);
  const origin = startUrl.origin === 'null' ? 'file:' : startUrl.origin;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ userAgent: 'iapply-skaner-dostepnosci/0.1 (przeglad na zamowienie)' });
  const robotsPage = await ctx.newPage();
  const disallow = await robotsDisallow(robotsPage, origin);
  await robotsPage.close();
  const queue = [startUrl.href]; const seen = new Set(queue); const pages = []; const nieudane = [];

  while (queue.length && pages.length < limit) {
    const url = queue.shift();
    const wynik = { url, tytul: '', bledy: [], linki: 0, formularze: 0, obrazy: 0 };
    const page = await ctx.newPage(); // nowa karta na podstronę: błąd jednej nie psuje następnej
    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      let res;
      try { res = await page.goto(url, { waitUntil: 'load', timeout: 30000 }); } catch (e) { wynik.blad = String(e.message).slice(0, 200); break; }
      if (res && !res.ok()) { wynik.blad = `HTTP ${res.status()}`; break; }
      await page.addScriptTag({ content: AXE });
      const r = await page.evaluate(async (pl) => { window.axe.configure({ locale: JSON.parse(pl) }); return window.axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } }); }, AXE_PL);
      for (const v of r.violations) {
        const old = wynik.bledy.find((b) => b.id === v.id);
        const miejsca = v.nodes.map((n) => n.target.join(' ')).slice(0, 5);
        if (old) { old.widoki.push(vp.name); old.liczba = Math.max(old.liczba, v.nodes.length); continue; }
        wynik.bledy.push({ id: v.id, waga: v.impact, opis: v.help, pomoc: v.helpUrl, kryteria: kryteria(v.tags),
          poziom: poziom(v.tags), liczba: v.nodes.length, miejsca, widoki: [vp.name] });
      }
      if (vp.name === '1440') {
        Object.assign(wynik, await page.evaluate(() => ({ tytul: document.title, linki: document.links.length,
          formularze: document.forms.length, obrazy: document.images.length,
          hrefs: [...document.links].map((a) => a.href) })));
      }
    }
    for (const h of wynik.hrefs || []) {
      try {
        const u = new URL(h); u.hash = '';
        const same = origin === 'file:' ? u.protocol === 'file:' : u.origin === origin;
        if (!same || seen.has(u.href) || /\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?)$/i.test(u.pathname)) continue;
        if (disallow.some((d) => u.pathname.startsWith(d))) continue;
        seen.add(u.href); queue.push(u.href);
      } catch (e) { /* zły link */ }
    }
    delete wynik.hrefs;
    await page.close();
    if (wynik.blad) { console.log(`pominięta: ${url} (${wynik.blad})`); nieudane.push({ url, blad: wynik.blad }); continue; }
    wynik.bledy.sort((a, b) => KOLEJNOSC[a.waga] - KOLEJNOSC[b.waga]);
    pages.push(wynik);
    console.log(`${pages.length}. ${url} - błędów: ${wynik.bledy.length}`);
    await sleep(1000);
  }
  await browser.close();

  // Zbiorczo: każdy rodzaj błędu raz, z liczbą podstron. Do ręcznego testu: główna, formularze, najwięcej błędów.
  const zbior = {};
  for (const p of pages) for (const b of p.bledy) {
    const z = zbior[b.id] || (zbior[b.id] = { ...b, podstrony: 0, wystapienia: 0 });
    z.podstrony += 1; z.wystapienia += b.liczba;
  }
  const lista = Object.values(zbior).sort((a, b) => KOLEJNOSC[a.waga] - KOLEJNOSC[b.waga] || b.podstrony - a.podstrony);
  const reczne = [pages[0], ...pages.filter((p) => p.formularze > 0),
    ...[...pages].sort((a, b) => b.bledy.length - a.bledy.length)].filter((p, i, arr) => p && arr.indexOf(p) === i).slice(0, 10);
  const raport = { adres: start, data: new Date().toISOString(), podstron: pages.length, rodzajow_bledow: lista.length,
    zbiorczo: lista, do_recznego_testu: reczne.map((p) => p.url), nieudane, podstrony: pages };
  const host = (startUrl.hostname || 'lokalny').replace(/[^a-z0-9.-]/gi, '_');
  fs.writeFileSync(`raport-${host}.json`, JSON.stringify(raport, null, 2));
  fs.writeFileSync(`raport-${host}.html`, html(raport));
  console.log(`Raport: raport-${host}.html (${lista.length} rodzajów błędów na ${pages.length} podstronach)`);
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function html(r) {
  const wiersze = r.zbiorczo.map((b) => `<tr><td data-k="Waga"><span class="w ${b.waga}">${WAGA[b.waga] || b.waga}</span></td>
    <td data-k="Błąd">${esc(b.opis)}<div class="m">${b.miejsca.map(esc).join('<br>')}</div></td>
    <td data-k="Kryterium">${b.kryteria.join(', ') || '-'} (${b.poziom})</td>
    <td data-k="Podstron">${b.podstrony}</td><td data-k="Wystąpień">${b.wystapienia}</td><td data-k="Widok">${b.widoki.join(', ')}</td></tr>`).join('');
  return `<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Przegląd dostępności</title><style>
:root{--bg:#0f1115;--fg:#e8e9ec;--mut:#9aa0aa;--line:#262a33;--card:#161922}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:32px 16px}
main{max-width:1100px;margin:0 auto}h1{font-size:24px;margin:0 0 4px}.mut{color:var(--mut)}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}
.k div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}.k b{display:block;font-size:22px}
table{width:100%;border-collapse:collapse;background:var(--card)}th,td{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.m{color:var(--mut);font:12px monospace;margin-top:4px;word-break:break-all}.w{font-size:12px;padding:2px 6px;border-radius:4px}
.critical{background:#7f1d1d}.serious{background:#7c2d12}.moderate{background:#713f12}.minor{background:#334155}
.tab{overflow-x:auto}.w{white-space:nowrap}.mut,li{overflow-wrap:anywhere}
@media(max-width:640px){body{padding:24px 16px}table,tbody,tr,td{display:block}tr:first-child{display:none}
tr{border:1px solid var(--line);border-radius:8px;margin-bottom:12px;padding:4px 0}td{border:0;padding:4px 12px}
td:not([data-k="Błąd"]):not([data-k="Waga"])::before{content:attr(data-k) ": ";color:var(--mut)}table{background:none}tr{background:var(--card)}}</style><main>
<h1>Przegląd dostępności - wersja automatyczna</h1><p class="mut">${esc(r.adres)} · ${r.data.slice(0, 10)} · WCAG 2.1/2.2 AA, axe-core, widoki 1440 i 390 px</p>
<div class="k"><div><b>${r.podstron}</b>podstron</div><div><b>${r.rodzajow_bledow}</b>rodzajów błędów</div>
<div><b>${r.zbiorczo.filter((b) => b.waga === 'critical' || b.waga === 'serious').length}</b>krytyczne i poważne</div></div>
<div class="tab"><table><tr><th>Waga</th><th>Błąd i przykładowe miejsca</th><th>Kryterium</th><th>Podstron</th><th>Wystąpień</th><th>Widok</th></tr>${wiersze}</table></div>
<h2>Do ręcznego testu</h2><ol>${r.do_recznego_testu.map((u) => `<li>${esc(u)}</li>`).join('')}</ol>
<p class="mut">Test automatyczny wykrywa ok. 30-40% problemów [szacunek]. To audyt techniczny, nie opinia prawna ani certyfikat.</p></main></html>`;
}

main().catch((e) => { console.error(e); process.exit(1); });

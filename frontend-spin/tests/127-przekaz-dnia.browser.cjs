// spin.clinic (14.10.2026): karta "Przekaz dnia" na stronie głównej ma stałą wysokość i stałe strefy (nagłówek, kolumna lewa,
// kolumna prawa, stopka) niezależnie od zakładki (Rządzący / Opozycja), dnia, długości tezy, liczby wpisów i wątków (0-N),
// stanu pustego, ładowania i błędu. Wymaga działającego `next dev` (SC_URL, domyślnie http://localhost:3011/); API jest
// podstawiane (route) fikstura z najdłuższym i najkrótszym przypadkiem. Różnica wysokości karty i każdej strefy: 0 px na 1440,
// 1024 i 390 (na telefonie wysokość inna niż na komputerze, ale stała między zakładkami). Dodatkowo: wątki dzielą równo wysokość
// kolumny, "Tematy" i nota o wpisach na jednej dolnej krawędzi, skrót tylko po całym słowie i z title. Dane syntetyczne.
// Uruchomienie: node tests/127-przekaz-dnia.browser.cjs   (Playwright z npx cache, Chromium poza ekranem, headless)
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const URL_ = process.env.SC_URL || 'http://localhost:3011/';
const EXE = 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe';

const post = (i, author, handle, text) => ({ url: `https://x.com/${handle}/status/10${i}`, text, published_at: `2026-10-13T${String(6 + i).padStart(2, '0')}:00:00Z`, author, handle, available: true });
const LONG = { day: '2026-10-13', camp: 'government', model: 'fixture', message: 'Fikcyjny przekaz testowy do pomiaru układu karty.',
  thesis: 'Fikcyjna teza testowa, celowo bardzo długa, żeby sprawdzić budżet trzech linii karty przekazu dnia przy szerokości komputera, tabletu i telefonu bez zmiany wysokości boksu.',
  themes: ['energia', 'podatki', 'infrastruktura', 'samorząd', 'edukacja', 'zdrowie', 'transport'], posts_count: 48,
  stats: { version: 1, posts: 48, authors: 19, noise: 3, concrete_count: 31, concrete_pct: 65, coherence_authors: 12, coherence_pct: 63, tone: null, tone_classified: 48 },
  scope: { date_from: '2026-10-13T06:00:00Z', date_to: '2026-10-13T20:00:00Z', timezone: 'Europe/Warsaw' }, spin_strength: { value: 58, n: 7, method: 'median' },
  posts: [post(1, 'Konto Testowe Pierwsze', 't1', 'Syntetyczny wpis testowy numer jeden, celowo rozwlekły, żeby cytat zajął więcej niż dwie linie i został przycięty przez budżet linii karty, a nie zmienił jej wysokości. https://t.co/abc'),
    post(2, 'Konto Testowe Drugie o Długiej Nazwie', 't2', 'Drugi syntetyczny wpis testowy, również długi, z liczbą 12 345 i odnośnikiem https://t.co/def oraz dalszym ciągiem zdania po odnośniku, które nie powinno niczego rozpychać.'),
    post(3, 'Konto Testowe Trzecie', 't3', 'Krótki wpis.')],
  points: [{ title: 'Pierwszy wątek testowy o długim tytule, który nie mieści się w jednej linii kolumny', summary: 'Opis pierwszego wątku, celowo długi: trzy zdania o niczym, żeby sprawdzić budżet linii opisu wątku w prawej kolumnie karty przekazu dnia. Zdanie trzecie, dodatkowe, już poza budżetem.', post_ids: ['1', '2', '3', '4', '5', '6'], authors: ['Konto Testowe Pierwsze', 'Konto Testowe Drugie o Długiej Nazwie', 'Konto Trzecie', 'Konto Czwarte'] },
    { title: 'Drugi wątek', summary: 'Krótki opis.', post_ids: ['7'], authors: ['Konto Testowe Pierwsze'] },
    { title: 'Trzeci wątek testowy ze średnim tytułem', summary: 'Opis trzeciego wątku w dwóch zdaniach. Drugie zdanie dopełnia dwie linie na komputerze.', post_ids: ['8', '9', '10'], authors: ['Konto Drugie', 'Konto Trzecie'] },
    { title: 'Czwarty wątek testowy', summary: 'Opis czwartego wątku, jedno zdanie o umiarkowanej długości.', post_ids: ['11', '12'], authors: ['Konto Czwarte', 'Konto Piąte', 'Konto Szóste'] }] };
const SHORT = { day: '2026-10-13', camp: 'opposition', model: 'fixture', message: 'Krótki fikcyjny przekaz testowy.', thesis: 'Krótka teza testowa.', themes: ['energia'], posts_count: 5,
  posts: [post(4, 'Konto Opozycyjne Testowe', 'o1', 'Jeden krótki wpis testowy.')], points: [{ title: 'Jedyny wątek', summary: 'Jedno zdanie.', post_ids: ['21'], authors: ['Konto Opozycyjne Testowe'] }] };
const older = (day, camp, n) => ({ day, camp, model: 'fixture', message: `Starszy przekaz testowy ${day}.`, thesis: `Starsza teza testowa z dnia ${day} (${n} wątków).`, themes: ['archiwum'], posts_count: 7,
  points: Array.from({ length: n }, (_, i) => ({ title: `Wątek ${i + 1} z ${day}`, summary: 'Opis wątku z historii, dwa krótkie zdania. Drugie zdanie.', post_ids: ['1', '2'], authors: ['Konto A', 'Konto B'] })) });
// dni: 12.10 (5 i 1 wątków), 11.10 (brak wątków u rządzących, 6 u opozycji), 10.10 (bez przekazu opozycji = stan pusty), 09.10
const DAYS = ['2026-10-12', '2026-10-11', '2026-10-10', '2026-10-09'];
const history = { government: DAYS.map((d, i) => older(d, 'government', [5, 0, 2, 3][i])), opposition: DAYS.filter(d => d !== '2026-10-10').map((d, i) => older(d, 'opposition', [1, 6, 3][i])) };
const PAGE = { generated_at: '2026-10-13T20:00:00Z', since: '2026-10-01', notice: 'Fixture', accounts_count: 12, messages: { government: LONG, opposition: SHORT }, message_history: history,
  columns: { government: [], opposition: [] }, interview: null, spin_of_day: null, latest_spin: null, scale: { window_days: 7, min_sample: 3, enough_data: false, government: {}, opposition: {} } };
const messageDay = (day) => ({ day, government: history.government.find(m => m.day === day) ? { ...history.government.find(m => m.day === day), posts: [post(5, 'Konto Historyczne', 'h', 'Wpis z historii dnia.')] } : null,
  opposition: history.opposition.find(m => m.day === day) ? { ...history.opposition.find(m => m.day === day), posts: [post(6, 'Konto Historyczne Opozycji', 'h2', 'Wpis z historii dnia.')] } : null });

const fails = [];
const bad = (m) => { fails.push(m); console.log('ZLE  ' + m); };
const ok = (m) => console.log('ok   ' + m);

async function page(b, w, o = {}) {
  const ctx = await b.newContext({ viewport: { width: w, height: 1000 }, reducedMotion: 'reduce' });
  await ctx.addInitScript(() => { try { localStorage.setItem('spin-theme', 'dark'); } catch (e) {} });
  const p = await ctx.newPage();
  let release; const gate = new Promise(r => { release = r; });
  await p.route('**/api/**', async r => {
    const u = new URL(r.request().url());
    if (u.pathname === '/api/clinic/') return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PAGE) });
    const md = u.pathname.match(/^\/api\/clinic\/messages\/(\d{4}-\d{2}-\d{2})\/?$/);
    if (md) { if (o.hold) await gate; if (o.detail === 'error') return r.fulfill({ status: 500, contentType: 'application/json', body: '{}' }); return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(messageDay(md[1])) }); }
    return r.fulfill({ status: 200, contentType: 'application/json', body: '{"results":[],"count":0,"next_page":null}' });
  });
  await p.goto(URL_ + (URL_.includes('?') ? '&' : '?') + '__bez_uwag=1', { waitUntil: 'domcontentloaded', timeout: 180000 });
  await p.waitForSelector('.sc-v3-pd .sc-v3-seg button', { timeout: 120000 });
  await p.waitForTimeout(500);
  return { p, ctx, release };
}
const M = () => {
  const q = (s) => document.querySelector(s);
  const rect = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { top: Math.round((r.top + scrollY) * 10) / 10, bottom: Math.round((r.bottom + scrollY) * 10) / 10, h: Math.round(r.height * 10) / 10 }; };
  const pts = [...document.querySelectorAll('.sc-v3-pd__pts > li')];
  const cutOk = [...document.querySelectorAll('.sc-v3-pd [data-cut]')].every(e => { const vis = e.querySelector('[aria-hidden]')?.textContent || ''; const full = e.getAttribute('title') || ''; const base = vis.replace(/…$/, ''); return full.startsWith(base) && (base.length === full.length || /[\s,;:.\-]/.test(full[base.length])); });
  return { card: rect(q('.sc-v3-pd')), h: rect(q('.sc-v3-pd__h')), body: rect(q('.sc-v3-pd__b') || q('.sc-v3-pd__empty')), l: rect(q('.sc-v3-pd__l')), r: rect(q('.sc-v3-pd__r')), f: rect(q('.sc-v3-pd__f')),
    side: q('.sc-v3-pd')?.dataset.side, day: q('.sc-v3-pd__k time')?.getAttribute('dateTime'), empty: Boolean(q('.sc-v3-pd__empty')),
    ptsH: pts.map(li => Math.round(li.getBoundingClientRect().height)), ptsOverflow: pts.filter(li => li.scrollHeight > li.clientHeight + 1).length,
    rfBottom: rect(q('.sc-v3-pd__rf'))?.bottom ?? null, qnoteBottom: rect(q('.sc-v3-pd__qnote'))?.bottom ?? null, cutOk, overflowCols: ['.sc-v3-pd__l', '.sc-v3-pd__r'].filter(s => { const e = q(s); return e && e.scrollHeight > e.clientHeight + 1; }).length };
};

(async () => {
  const b = await chromium.launch({ headless: true, executablePath: EXE, args: ['--window-position=-32000,-32000', '--window-size=1,1'] });
  for (const w of [1440, 1024, 390]) {
    const { p, ctx } = await page(b, w);
    const runs = [];
    const days = await p.$$('.sc-v3-days button');
    for (let d = 0; d < days.length; d++) {
      const visible = await days[d].isVisible(); if (!visible) continue;
      await days[d].click(); await p.waitForTimeout(600);
      for (let t = 0; t < 2; t++) { const tabs = await p.$$('.sc-v3-pd .sc-v3-seg button'); await tabs[t].click(); await p.waitForTimeout(400); runs.push({ d, t, ...(await p.evaluate(M)) }); }
    }
    // tolerancja 0,5 px: zaokrąglenia subpikselowe (stan pusty z min-height w px vs. suma stref w em)
    const uniq = (f) => [...new Set(runs.map(f))];
    const spread = (vals) => Math.max(...vals) - Math.min(...vals);
    const cardH = uniq(r => r.card.h);
    spread(cardH) <= 0.5 ? ok(`${w}: wysokość karty stała (${cardH[0]} px, rozrzut ${spread(cardH).toFixed(1)} px) w ${runs.length} stanach (dni x zakładki, w tym stan pusty: ${runs.some(r => r.empty)})`) : bad(`${w}: wysokość karty zmienia się: ${cardH.join(' / ')}`);
    for (const z of ['h', 'body', 'f']) { const tops = runs.map(r => r[z]?.top ?? NaN), bots = runs.map(r => r[z]?.bottom ?? NaN); spread(tops) <= 0.5 && spread(bots) <= 0.5 ? ok(`${w}: strefa ${z} stała ${tops[0]}-${bots[0]}`) : bad(`${w}: strefa ${z} skacze: ${uniq(r => r[z] ? `${r[z].top}-${r[z].bottom}` : 'brak').join(' | ')}`); }
    for (const z of ['l', 'r']) { const rs = runs.filter(r => r[z]); const tops = rs.map(r => r[z].top), bots = rs.map(r => r[z].bottom); spread(tops) <= 0.5 && spread(bots) <= 0.5 ? ok(`${w}: kolumna ${z} stała ${tops[0]}-${bots[0]}`) : bad(`${w}: kolumna ${z} skacze: ${uniq(r => r[z] ? `${r[z].top}-${r[z].bottom}` : null).filter(Boolean).join(' | ')}`); }
    const withPts = runs.filter(r => r.ptsH.length > 1);
    withPts.every(r => Math.max(...r.ptsH) - Math.min(...r.ptsH) <= 1) ? ok(`${w}: wątki dzielą równo wysokość kolumny (np. ${withPts[0]?.ptsH.join('/')})`) : bad(`${w}: wątki nierówne: ${withPts.map(r => r.ptsH.join('/')).join(' | ')}`);
    runs.every(r => !r.ptsOverflow && !r.overflowCols) ? ok(`${w}: nic nie wylewa się z wątków ani kolumn`) : bad(`${w}: wylewanie: ${runs.filter(r => r.ptsOverflow || r.overflowCols).map(r => `${r.day}/${r.side}`).join(', ')}`);
    runs.every(r => r.cutOk) ? ok(`${w}: skróty tylko po całym słowie, z title`) : bad(`${w}: skrót w pół słowa`);
    if (w >= 1101) { const same = runs.filter(r => r.rfBottom && r.qnoteBottom).every(r => Math.abs(r.rfBottom - r.qnoteBottom) <= 1); same ? ok(`${w}: "Tematy" i nota o wpisach na jednej dolnej krawędzi`) : bad(`${w}: dolne krawędzie kolumn różne: ${runs.map(r => `${r.rfBottom}/${r.qnoteBottom}`).join(' ')}`); }
    await ctx.close();

    // stan ładowania (wpisy starszego dnia) i błąd dociągania: ta sama wysokość
    const base = runs[0].card.h;
    for (const mode of [{ hold: true }, { detail: 'error' }]) {
      const { p: p2, ctx: c2 } = await page(b, w, mode);
      const d2 = await p2.$$('.sc-v3-days button'); if (d2[1]) { await d2[1].click(); await p2.waitForTimeout(700); }
      const m = await p2.evaluate(M);
      Math.abs(m.card.h - base) <= 0.5 ? ok(`${w}: ${mode.hold ? 'ładowanie' : 'błąd'} wpisów: karta ${m.card.h} px = ${base}`) : bad(`${w}: ${mode.hold ? 'ładowanie' : 'błąd'} wpisów zmienia wysokość: ${m.card.h} vs ${base}`);
      await c2.close();
    }
  }
  await b.close();
  console.log(fails.length ? `\n${fails.length} ZLE` : '\nwszystko ok');
  process.exit(fails.length ? 1 : 0);
})();

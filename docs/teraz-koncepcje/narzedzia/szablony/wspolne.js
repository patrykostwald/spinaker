/* Wspólne dla prototypów A i B: dane próbne, okres, legenda, oś czasu, lista zdarzeń, panel źródeł, tryby.
   Wszystko tu jest PRÓBNE: zdarzenia są losowane z ziarnem, żeby obraz był powtarzalny. */
'use strict';
const T = (() => {
  const D = JSON.parse(document.getElementById('dane').textContent);
  const Q = D.q;
  const rozkoduj = a => { const r = []; let x = 0, y = 0; for (let i = 0; i < a.length; i += 2) { x += a[i]; y += a[i + 1]; r.push([x / Q, y / Q]); } return r; };
  const powiaty = D.powiaty.map((p, i) => ({ i, kod: p.k, nazwa: p.n, miasto: p.m, woj: p.w, lp: p.p, rings: p.r.map(rozkoduj) }));
  const kraj = D.kraj.map(rozkoduj);
  const wojLinie = D.woj.map(rozkoduj);
  const WOJ = Object.fromEntries(D.wojewodztwa.map(w => [w.kod, w.nazwa]));
  const poKodzie = new Map(powiaty.map(p => [p.kod, p]));
  const kodPo = (nazwa, woj) => powiaty.find(p => p.nazwa === nazwa && p.woj === woj)?.kod;
  const nazwaPow = p => (p.miasto ? `${p.nazwa} (miasto na prawach powiatu)` : `powiat ${p.nazwa}`);

  // płaszczyzna w km (przybliżenie równoodległościowe, wystarczające dla Polski)
  const KX = 111.32 * Math.cos(52 * Math.PI / 180), KY = 111.32;
  const xy = (lon, lat) => [(lon - 19.15) * KX, (lat - 52.05) * KY];

  // ---------- losowanie z ziarnem ----------
  function rng(ziarno) { let a = ziarno >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  // ---------- czas ----------
  const DNI = 30, DZIS = 29;
  const TERAZ = '20.11.2026, 11:40';
  const dzien = i => { const d = new Date(Date.UTC(2026, 10, 20 - (DZIS - i))); return `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`; };
  const dzienPelny = i => `${dzien(i)}.2026`;

  // ---------- źródła i łącza ----------
  const LACZA = ['X', 'API', 'MCI', 'RSS', 'scraping', 'WebSocket', 'plik', 'ręcznie'];
  const ZRODLA = [
    { id: 'rcb', nazwa: 'Alerty RCB', lacze: 'API', zakres: 'cała Polska, zasięg z treści alertu', zdrowie: 'dziala', ostatnio: '11:38' },
    { id: 'imgw-meteo', nazwa: 'IMGW: ostrzeżenia meteorologiczne', lacze: 'API', zakres: 'powiaty, kody TERYT', zdrowie: 'dziala', ostatnio: '11:35' },
    { id: 'imgw-hydro', nazwa: 'IMGW: ostrzeżenia hydrologiczne', lacze: 'API', zakres: 'zlewnie, zasięg przybliżony', zdrowie: 'opoznione', ostatnio: '11:12', opis: 'opóźnione o 28 min' },
    { id: 'gios', nazwa: 'GIOŚ: jakość powietrza', lacze: 'API', zakres: 'stacje pomiarowe', zdrowie: 'dziala', ostatnio: '11:30' },
    { id: 'emsc', nazwa: 'EMSC: wstrząsy sejsmiczne', lacze: 'WebSocket', zakres: 'punkty, położenie przybliżone', zdrowie: 'dziala', ostatnio: 'na żywo' },
    { id: 'firms', nazwa: 'NASA FIRMS: ogniska pożarów', lacze: 'plik', zakres: 'punkty z satelity, co 3 h', zdrowie: 'dziala', ostatnio: '09:00' },
    { id: 'cert', nazwa: 'CERT Polska: ostrzeżenia', lacze: 'RSS', zakres: 'bez położenia', zdrowie: 'dziala', ostatnio: '11:20' },
    { id: 'pse', nazwa: 'PSE: komunikaty operatora', lacze: 'RSS', zakres: 'bez położenia', zdrowie: 'dziala', ostatnio: '10:55' },
    { id: 'wczk', nazwa: 'WCZK lubuskie: komunikaty', lacze: 'scraping', zakres: 'województwo lubuskie', zdrowie: 'blad', ostatnio: '17.11, 21:40', opis: 'nie odpowiada od 17.11, 21:40' },
    { id: 'x-rcb', nazwa: 'Konto RCB na X', lacze: 'X', zakres: 'powtórzenia alertów', zdrowie: 'wstrzymane', ostatnio: '15.11', opis: 'wstrzymane od 15.11 (limit)' },
    { id: 'mci', nazwa: 'Serwer MCI (próbny)', lacze: 'MCI', zakres: 'test łącza', zdrowie: 'dziala', ostatnio: '11:31' },
    { id: 'redakcja', nazwa: 'Korekty redakcji', lacze: 'ręcznie', zakres: 'poprawki zasięgu i statusu', zdrowie: 'dziala', ostatnio: '19.11' },
  ];
  const ZR = Object.fromEntries(ZRODLA.map(z => [z.id, z]));
  const ZDROWIE = { dziala: ['●', 'działa'], opoznione: ['◐', 'opóźnione'], blad: ['✕', 'nie odpowiada'], wstrzymane: ['‖', 'wstrzymane'] };

  // ---------- brak w naszych danych ----------
  // Źródło dla lubuskiego nie odpowiada od 17.11 wieczorem: od 18.11 (dzień 27) nie mamy danych dla powiatów woj. 08.
  const BRAK = { woj: '08', odDnia: 27, zrodlo: 'WCZK lubuskie (scraping)', opis: 'źródło nie odpowiada od 17.11.2026, 21:40' };
  const jestBrak = (p, d) => p.woj === BRAK.woj && d >= BRAK.odDnia;

  // ---------- zasięgi przybliżone ----------
  function plama(lon, lat, rx, ry, ziarno) {
    const r = rng(ziarno), pkt = [];
    for (let k = 0; k < 28; k++) { const a = k / 28 * Math.PI * 2, f = 0.82 + r() * 0.3; pkt.push([lon + Math.cos(a) * rx * f, lat + Math.sin(a) * ry * f]); }
    return pkt;
  }
  const PRZYBLIZONE = {
    sola: { temat: 'stany wody', nazwa: 'zlewnia Soły i Skawy', opis: 'źródło opisuje obszar zlewnią, bez listy powiatów', ring: plama(19.42, 49.7, 0.36, 0.2, 7) },
    knyszyn: { temat: 'oblodzenie', nazwa: 'rejon Puszczy Knyszyńskiej', opis: '„rejon Puszczy Knyszyńskiej” nie jest jednostką TERYT', ring: plama(23.38, 53.27, 0.33, 0.15, 11) },
  };

  // ---------- zdania RCB (przykłady) ----------
  const wojCale = kody => powiaty.filter(p => kody.includes(p.woj)).map(p => p.kod);
  const RCB = [
    { id: 'r1', dzien: 28, czas: '17:02', tytul: 'Alert RCB: silny wiatr',
      zdanie: 'Silny wiatr, w porywach do 90 km/h. Dotyczy województw: małopolskiego, śląskiego, podkarpackiego i świętokrzyskiego.',
      wlaczone: wojCale(['12', '24', '18', '26']), wylaczone: [], przyblizone: null,
      odczyt: [['objęte', '4 województwa w całości'], ['wyłączenia', 'brak'], ['nierozpoznane', 'brak']] },
    { id: 'r2', dzien: 29, czas: '06:15', tytul: 'Alert RCB: opady śniegu',
      zdanie: 'Intensywne opady śniegu. Dotyczy województwa małopolskiego z wyłączeniem powiatów: miechowskiego, proszowickiego oraz miasta Tarnowa.',
      wylaczone: [kodPo('miechowski', '12'), kodPo('proszowicki', '12'), kodPo('Tarnów', '12')], przyblizone: null,
      odczyt: [['objęte', 'województwo małopolskie'], ['wyłączenia', '3 jednostki, wzór kropkowany'], ['nierozpoznane', 'brak']] },
    { id: 'r3', dzien: 29, czas: '09:40', tytul: 'Alert RCB: oblodzenie dróg',
      zdanie: 'Oblodzenie dróg. Dotyczy powiatów: suwalskiego, sejneńskiego, augustowskiego (podlaskie) i gołdapskiego (warmińsko-mazurskie) oraz rejonu Puszczy Knyszyńskiej.',
      wlaczone: [kodPo('suwalski', '20'), kodPo('sejneński', '20'), kodPo('augustowski', '20'), kodPo('gołdapski', '28')], wylaczone: [], przyblizone: 'knyszyn',
      odczyt: [['objęte', '4 powiaty, 2 województwa'], ['wyłączenia', 'brak'], ['nierozpoznane', '1: zasięg przybliżony']] },
  ];
  RCB[1].wlaczone = wojCale(['12']).filter(k => !RCB[1].wylaczone.includes(k));

  // ---------- zdarzenia próbne ----------
  const SCEN = [
    { zr: 'imgw-meteo', tyt: 'Ostrzeżenie meteo: silny wiatr', dni: [6, 11], woj: ['22', '32', '28'], waga: 9 },
    { zr: 'imgw-meteo', tyt: 'Ostrzeżenie meteo: intensywne opady śniegu', dni: [23, 29], woj: ['12', '24', '18'], waga: 9 },
    { zr: 'imgw-hydro', tyt: 'Ostrzeżenie hydro: wzrost stanów wody', dni: [24, 29], woj: ['12', '18'], waga: 5 },
    { zr: 'gios', tyt: 'GIOŚ: przekroczony poziom informowania, PM10', dni: [13, 21], woj: ['24', '12', '10'], waga: 6 },
    { zr: 'firms', tyt: 'Ognisko pożaru wykryte z satelity', dni: [0, 29], woj: ['06', '14', '20', '04'], waga: 3 },
    { zr: 'emsc', tyt: 'Wstrząs sejsmiczny, magnituda 2,6', dni: [0, 29], kody: ['0211', '0216', '0203'], waga: 0.6 },
    { zr: 'wczk', tyt: 'Komunikat wojewódzki: utrudnienia na drogach', dni: [0, 26], woj: ['08'], waga: 1.5 },
    { zr: 'mci', tyt: 'Komunikat próbny z serwera MCI', dni: [0, 29], woj: null, waga: 1 },
    { zr: 'imgw-meteo', tyt: 'Ostrzeżenie meteo: gęsta mgła', dni: [0, 29], woj: null, waga: 3 },
    { zr: 'cert', tyt: 'CERT Polska: kampania wyłudzeń SMS', dni: [0, 29], krajowe: true, waga: 0.7 },
    { zr: 'pse', tyt: 'PSE: komunikat o pracy systemu', dni: [0, 29], krajowe: true, waga: 0.4 },
    { zr: 'x-rcb', tyt: 'Wpis RCB na X: przypomnienie o alercie', dni: [0, 24], krajowe: true, waga: 0.4 },
  ];
  const zdarzenia = [];
  (() => {
    const r = rng(2026);
    const wagaPow = p => (p.miasto ? 1.4 : 1);
    for (let d = 0; d < DNI; d++) {
      const akt = SCEN.filter(s => d >= s.dni[0] && d <= s.dni[1]);
      const suma = akt.reduce((a, s) => a + s.waga, 0);
      const n = 20 + Math.floor(r() * 14);
      for (let k = 0; k < n; k++) {
        let x = r() * suma, s = akt[0];
        for (const a of akt) { x -= a.waga; if (x <= 0) { s = a; break; } }
        const czas = `${String(Math.floor(r() * 24)).padStart(2, '0')}:${String(Math.floor(r() * 60)).padStart(2, '0')}`;
        if (d === DZIS && czas > '11:40') continue;
        const st = r(), status = st < 0.84 ? 'potwierdzone' : st < 0.95 ? 'zgłoszone, w ocenie' : 'odwołane';
        if (s.krajowe) { zdarzenia.push({ dzien: d, czas, zr: s.zr, tytul: s.tyt, miejsce: 'cała Polska, bez położenia', kody: [], punkt: null, status }); continue; }
        const pula = s.kody ? s.kody.map(k2 => poKodzie.get(k2)) : powiaty.filter(p => !s.woj || s.woj.includes(p.woj));
        const sumaP = pula.reduce((a, p) => a + wagaPow(p), 0);
        let y = r() * sumaP, p = pula[0];
        for (const q of pula) { y -= wagaPow(q); if (y <= 0) { p = q; break; } }
        if (jestBrak(p, d)) continue; // tych dni nie mamy w danych
        const punkt = [p.lp[0] + (r() - 0.5) * 0.08, p.lp[1] + (r() - 0.5) * 0.05];
        zdarzenia.push({ dzien: d, czas, zr: s.zr, tytul: s.tyt, miejsce: `${nazwaPow(p)}, ${WOJ[p.woj]}`, kody: [p.kod], punkt, status });
      }
    }
    zdarzenia.push({ dzien: 28, czas: '08:20', zr: 'imgw-hydro', tytul: 'Ostrzeżenie hydro: zlewnia Soły i Skawy', miejsce: 'zasięg przybliżony: zlewnia Soły i Skawy',
      kody: [], punkt: null, przyblizone: 'sola', status: 'potwierdzone' });
    for (const a of RCB) zdarzenia.push({ dzien: a.dzien, czas: a.czas, zr: 'rcb', tytul: a.tytul, rcb: a.id,
      miejsce: a.id === 'r1' ? '4 województwa' : a.id === 'r2' ? 'województwo małopolskie; komunikat zawiera wyłączenia' : '4 powiaty w 2 województwach i zasięg przybliżony',
      kody: a.wlaczone.filter(k => !jestBrak(poKodzie.get(k), a.dzien)), punkt: null, przyblizone: a.przyblizone, status: 'potwierdzone' });
    zdarzenia.sort((a, b) => b.dzien - a.dzien || (b.czas > a.czas ? 1 : -1));
  })();

  // ---------- stan i okres ----------
  const ruchSystem = window.matchMedia('(prefers-reduced-motion: reduce)');
  const zapisanyRuch = (() => { try { return localStorage.getItem('teraz-animacje'); } catch { return null; } })();
  const stan = { koniec: DZIS, dlugosc: 7, prosty: false, ruch: zapisanyRuch === null ? !ruchSystem.matches : zapisanyRuch === '1', rcb: null, ileListy: 6 };
  const sluchacze = [];
  const zmien = zm => { Object.assign(stan, zm); pamiec = null; sluchacze.forEach(f => f(stan)); };
  const okres = () => [stan.koniec - stan.dlugosc + 1, stan.koniec];
  const opisOkresu = () => { const [a, b] = okres(); return a === b ? dzienPelny(b) : `${dzien(a)}–${dzienPelny(b)}`; };
  let pamiec = null;
  /** Liczba komunikatów na powiat w okresie; null = brak w naszych danych (nigdy zero). */
  function liczby() {
    if (pamiec) return pamiec;
    const [a, b] = okres();
    const wynik = powiaty.map(p => { for (let d = a; d <= b; d++) if (jestBrak(p, d)) return null; return 0; });
    const wOkresie = zdarzenia.filter(z => z.dzien >= a && z.dzien <= b);
    for (const z of wOkresie) for (const k of z.kody) { const p = poKodzie.get(k); if (wynik[p.i] !== null) wynik[p.i]++; }
    pamiec = { naPowiat: wynik, zdarzenia: wOkresie };
    return pamiec;
  }
  const opisBraku = () => `Brak w naszych danych. Źródło: ${BRAK.zrodlo}, ${BRAK.opis}. Okres: ${opisOkresu()}. Stan na ${TERAZ}.`;

  // skala: tylko liczba komunikatów, jedna barwa (bursztyn), bez znaczenia wagi
  const PROGI = [1, 2, 4, 7];
  const ETYK = ['1', '2–3', '4–6', '7+'];
  const ALFA = [0.38, 0.56, 0.75, 0.95];
  const klasa = n => { let k = -1; PROGI.forEach((p, i) => { if (n >= p) k = i; }); return k; };
  const kolor = n => { const k = klasa(n); return k < 0 ? null : `rgba(255,194,122,${ALFA[k]})`; };

  function wzorBraku(ctx, skala = 1) {
    const c = document.createElement('canvas'), s = Math.round(8 * skala);
    c.width = c.height = s;
    const x = c.getContext('2d');
    x.fillStyle = '#1a1d1b'; x.fillRect(0, 0, s, s);
    x.strokeStyle = 'rgba(237,240,232,0.42)'; x.lineWidth = 1 * skala;
    x.beginPath(); x.moveTo(-1, s + 1); x.lineTo(s + 1, -1); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(s - 1, s + 1); x.lineTo(s + 1, s - 1); x.stroke();
    return ctx.createPattern(c, 'repeat');
  }
  function wzorWylaczenia(ctx, skala = 1) {
    const c = document.createElement('canvas'), s = Math.round(6 * skala);
    c.width = c.height = s;
    const x = c.getContext('2d');
    x.fillStyle = '#0e100f'; x.fillRect(0, 0, s, s);
    x.fillStyle = 'rgb(237,240,232)'; x.beginPath(); x.arc(s / 2, s / 2, 1.4 * skala, 0, 7); x.fill();
    return ctx.createPattern(c, 'repeat');
  }

  // ---------- pomocnicze DOM ----------
  const $ = s => document.querySelector(s);
  const el = (tag, at = {}, ...dzieci) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(at)) { if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); } for (const d of dzieci) if (d != null) e.append(d); return e; };
  const etykietaLacza = l => el('span', { class: 'etykieta zdarzenie__lacze', title: `łącze: ${l}` }, l);

  // ---------- legenda ----------
  const SVG_WZORY = `<svg width="0" height="0" style="position:absolute"><defs>
    <pattern id="w-brak" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#1a1d1b"/><line x1="0" y1="0" x2="0" y2="6" stroke="rgba(237,240,232,.5)" stroke-width="1.2"/></pattern>
    <pattern id="w-wyl" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="5" height="5" fill="#0e100f"/><circle cx="2.5" cy="2.5" r=".9" fill="rgba(237,240,232,.6)"/></pattern></defs></svg>`;
  function legenda(dodatki = [], uwaga = 'Barwa i ruch') {
    const b = $('#legenda');
    const skala = el('div', { class: 'legenda__skala', role: 'img', 'aria-label': `Skala, od najciemniejszej: ${ETYK.join(', ')} komunikatów` });
    const progi = el('div', { class: 'legenda__progi', 'aria-hidden': 'true' });
    ALFA.forEach((a, i) => { skala.append(el('span', { style: `background:rgba(255,194,122,${a})` })); progi.append(el('span', {}, ETYK[i])); });
    const wiersz = (svg, tekst) => { const w = el('div', { class: 'legenda__wiersz' }); w.innerHTML = `<svg viewBox="0 0 34 22" aria-hidden="true">${svg}</svg>`; w.append(el('span', {}, tekst)); return w; };
    b.innerHTML = SVG_WZORY;
    b.append(
      el('p', { class: 'boks__opis' }, 'Liczba komunikatów w okresie, na powiat:'), skala, progi,
      wiersz('<rect x="1" y="3" width="32" height="16" rx="2" fill="#151816" stroke="rgba(237,240,232,.35)"/>', '0: mamy dane, w okresie bez komunikatów'),
      wiersz('<rect x="1" y="3" width="32" height="16" rx="2" fill="url(#w-brak)" stroke="rgba(237,240,232,.5)"/>', 'brak w naszych danych: źródło nie działa, nie wiemy, co tam jest. To nie znaczy, że jest spokojnie.'),
      wiersz('<path d="M3 17 C 8 3, 26 3, 31 15" fill="rgba(255,194,122,.07)" stroke="rgb(255,194,122)" stroke-width="1.4" stroke-dasharray="4 3"/>', 'zasięg przybliżony: obszar opisany słowami, granice orientacyjne; nie wliczamy go do liczb'),
      wiersz('<rect x="1" y="3" width="32" height="16" rx="2" fill="url(#w-wyl)" stroke="rgba(237,240,232,.6)" stroke-dasharray="1.5 2.5"/>', 'wyłączone w treści komunikatu (sprawdź oryginał)'),
      ...dodatki.map(([svg, t]) => wiersz(svg, t)),
      el('p', { class: 'legenda__uwaga' }, `${uwaga} pokazują tylko liczbę komunikatów albo ich świeżość. Nie oznaczają wagi ani stopnia zagrożenia: ten podaje źródło w treści komunikatu.`),
    );
  }

  // ---------- oś czasu ----------
  function osCzasu() {
    const wykres = $('#os-wykres'), suwak = $('#os-suwak');
    const dzienne = Array.from({ length: DNI }, (_, d) => zdarzenia.filter(z => z.dzien === d).length);
    const maks = Math.max(...dzienne);
    const rysuj = () => {
      const [a, b] = okres();
      const w = 1000, h = 64, sz = w / DNI;
      let s = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">`;
      s += `<rect x="${a * sz}" y="0" width="${(b - a + 1) * sz}" height="${h}" fill="rgba(255,194,122,.08)"/>`;
      dzienne.forEach((n, d) => {
        const bh = Math.max(2, (n / maks) * (h - 10)), w0 = d >= a && d <= b;
        s += `<rect x="${d * sz + 2}" y="${h - bh}" width="${sz - 4}" height="${bh}" fill="${w0 ? 'rgb(255,194,122)' : 'rgba(154,163,154,.38)'}"/>`;
        if (jestBrakDzien(d)) s += `<rect x="${d * sz + 2}" y="${h - bh}" width="${sz - 4}" height="${bh}" fill="url(#w-brak)" opacity=".75"/>`;
      });
      s += `<line x1="${(b + 1) * sz}" x2="${(b + 1) * sz}" y1="-4" y2="${h}" stroke="rgb(255,194,122)" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
      s += `<line x1="${w}" x2="${w}" y1="-4" y2="${h}" stroke="rgb(229,53,43)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
      wykres.querySelector('svg')?.remove();
      wykres.insertAdjacentHTML('afterbegin', s);
      $('#os-okres').innerHTML = `Okres: <b>${opisOkresu()}</b>`;
      $('#os-uchwyt').style.left = `${((b + 1) / DNI) * 100}%`;
      suwak.min = stan.dlugosc - 1; suwak.value = stan.koniec;
      suwak.disabled = stan.dlugosc === DNI;
      suwak.setAttribute('aria-valuetext', `okres ${opisOkresu()}`);
      document.querySelectorAll('#os-dlugosc button').forEach(bt => bt.setAttribute('aria-pressed', String(Number(bt.dataset.dni) === stan.dlugosc)));
    };
    const jestBrakDzien = d => d >= BRAK.odDnia;
    wykres.append(el('span', { class: 'os__uchwyt', id: 'os-uchwyt', 'aria-hidden': 'true' }));
    wykres.append(el('ul', { class: 'sr' }, ...dzienne.map((n, d) => el('li', {}, `${dzienPelny(d)}: ${n} komunikatów${jestBrakDzien(d) ? ', bez danych dla województwa lubuskiego' : ''}`))));
    $('#os-brak').textContent = `Kreskowane dni: brak w naszych danych dla woj. ${WOJ[BRAK.woj]} od ${dzien(BRAK.odDnia)}.`;
    $('#os-daty').innerHTML = `<span>${dzien(0)}</span><span>${dzien(10)}</span><span>${dzien(20)}</span><span>dziś ${dzien(DZIS)}</span>`;
    suwak.max = DZIS;
    suwak.addEventListener('input', () => zmien({ koniec: Number(suwak.value), ileListy: 6 }));
    document.querySelectorAll('#os-dlugosc button').forEach(bt => bt.addEventListener('click', () => {
      const dl = Number(bt.dataset.dni); zmien({ dlugosc: dl, koniec: Math.max(stan.koniec, dl - 1), ileListy: 6 });
    }));
    $('#os-dzis').addEventListener('click', () => zmien({ koniec: DZIS, ileListy: 6 }));
    sluchacze.push(rysuj); rysuj();
  }

  // ---------- lista zdarzeń ----------
  function lista() {
    const ol = $('#lista'), stopka = $('#lista-stopka');
    const rysuj = () => {
      const { zdarzenia: z } = liczby();
      ol.innerHTML = '';
      const ile = Math.max(stan.ileListy, dopelnij);
      for (const e of z.slice(0, ile)) {
        const zr = ZR[e.zr];
        const wyjatek = e.status !== 'potwierdzone' ? el('span', { class: `etykieta zdarzenie__status${e.status === 'odwołane' ? ' zdarzenie__status--odwolane' : ''}` }, e.status) : null;
        ol.append(el('li', { class: 'zdarzenie', tabindex: '-1' },
          el('span', { class: 'zdarzenie__czas' }, `${dzien(e.dzien)} ${e.czas}`),
          etykietaLacza(zr.lacze),
          el('span', { class: 'zdarzenie__tresc' }, el('span', { class: 'zdarzenie__tytul' }, el('span', { class: 'zdarzenie__tekst' }, e.tytul), wyjatek), el('span', { class: 'zdarzenie__miejsce' }, `${e.miejsce} · ${zr.nazwa}`))));
      }
      pokazane = Math.min(ile, z.length);
      stopka.querySelector('span').textContent = `Pokazano ${pokazane} z ${z.length} komunikatów w okresie, od najnowszych.`;
      stopka.querySelector('button').hidden = pokazane >= z.length;
    };
    // na szerokim ekranie lista wypełnia kolumnę do wysokości panelu obok (bez pustych pasów)
    let dopelnij = 0, pokazane = 0;
    const wyrownaj = () => {
      if (window.innerWidth <= 900) { if (dopelnij) { dopelnij = 0; rysuj(); } return; }
      const lewa = ol.closest('.kolumna'), prawa = document.querySelector('aside.kolumna');
      const wys = k => { const w = [...k.children].filter(c => c.offsetParent); return w.reduce((s, c) => s + c.offsetHeight, 0) + (w.length - 1) * 24; };
      // mierzymy naturalne wysokości: bez rozciągania ostatnich boksów
      const ost = [lewa.lastElementChild, prawa.lastElementChild];
      ost.forEach(e => { e.style.flex = 'none'; });
      const roznica = wys(prawa) - wys(lewa);
      ost.forEach(e => { e.style.flex = ''; });
      const wiersz = ol.firstElementChild?.offsetHeight || 56;
      if (roznica >= 0 && roznica < wiersz) return; // kolumny równe z dokładnością do jednego wiersza
      const nowe = Math.max(6, pokazane + Math.floor(roznica / wiersz));
      if (nowe !== pokazane) { dopelnij = nowe; rysuj(); }
    };
    sluchacze.push(() => requestAnimationFrame(wyrownaj));
    requestAnimationFrame(() => requestAnimationFrame(wyrownaj));
    window.addEventListener('resize', () => requestAnimationFrame(wyrownaj));
    stopka.querySelector('button').addEventListener('click', () => {
      const bylo = pokazane;
      zmien({ ileListy: Math.max(stan.ileListy, dopelnij) + 6 });
      (ol.children[bylo] || ol.lastElementChild)?.focus();
    });
    sluchacze.push(rysuj); rysuj();
  }

  // ---------- źródła ----------
  function zrodla() {
    const lacza = $('#lacza');
    LACZA.forEach(l => lacza.append(el('span', { class: 'etykieta' }, l)));
    const ol = $('#zrodla');
    for (const z of ZRODLA) {
      const [znak, slowo] = ZDROWIE[z.zdrowie];
      ol.append(el('li', { class: 'zrodlo' },
        el('span', { class: 'zrodlo__wiersz' }, el('span', { class: 'zrodlo__nazwa' }, z.nazwa), el('span', { class: 'etykieta' }, z.lacze)),
        el('span', { class: 'zrodlo__wiersz' }, el('span', { class: 'zrodlo__zakres' }, z.zakres),
          el('span', { class: `zrodlo__zdrowie zdrowie--${z.zdrowie}` }, el('span', { class: 'zdrowie-znak', 'aria-hidden': 'true' }, znak), z.opis || `${slowo} · ${z.ostatnio}`))));
    }
    const ile = k => ZRODLA.filter(z => z.zdrowie === k).length;
    $('#zrodla').after(el('p', { class: 'zrodla__stopka' }, `Działa ${ile('dziala')} z ${ZRODLA.length} · opóźnione ${ile('opoznione')} · nie odpowiada ${ile('blad')} · wstrzymane ${ile('wstrzymane')}. Sprawdzono ${TERAZ}.`));
  }

  // ---------- nagłówek sceny i tryb prosty ----------
  function naglowek() {
    const rysuj = () => {
      const { naPowiat, zdarzenia: z } = liczby();
      $('#tytul-okresu').innerHTML = `<span class="dlugi">Komunikaty w okresie</span><span class="krotki">Okres</span> ${opisOkresu()}`;
      $('#suma').firstChild.textContent = String(z.length);
      const brak = naPowiat.filter(n => n === null).length;
      $('#opis-okresu').textContent = `Liczba komunikatów na powiat, nie poziom zagrożenia.${brak ? ` ${brak} powiatów: brak w naszych danych.` : ''}`;
      const top = powiaty.filter(p => naPowiat[p.i]).sort((a, b) => naPowiat[b.i] - naPowiat[a.i]).slice(0, 8);
      const tb = $('#najwiecej');
      if (tb) tb.innerHTML = top.map(p => `<li><span>${nazwaPow(p)}, ${WOJ[p.woj]}</span><b>${naPowiat[p.i]}</b></li>`).join('') +
        (brak ? `<li class="brak-wiersz"><span>${brak} powiatów woj. ${WOJ[BRAK.woj]}: brak w naszych danych</span><b>nie wiemy</b></li>` : '');
      const rcb = stan.rcb ? RCB.find(r => r.id === stan.rcb) : null;
      const tab = $('#tabela-powiatow tbody');
      if (tab) tab.innerHTML = [...powiaty].sort((a, b) => (naPowiat[b.i] ?? -1) - (naPowiat[a.i] ?? -1) || a.nazwa.localeCompare(b.nazwa, 'pl')).map(p => {
        const zas = !rcb ? '' : rcb.wylaczone.includes(p.kod) ? 'wyłączony w treści' : rcb.wlaczone.includes(p.kod) ? 'wymieniony' : '';
        return `<tr><td>${nazwaPow(p)}</td><td>${WOJ[p.woj]}</td><td>${naPowiat[p.i] === null ? 'brak w naszych danych' : naPowiat[p.i]}</td>${rcb ? `<td>${zas}</td>` : ''}</tr>`;
      }).join('');
      const th = $('#tabela-powiatow thead tr');
      if (th) th.innerHTML = `<th scope="col">Powiat</th><th scope="col">Województwo</th><th scope="col">Komunikaty</th>${rcb ? '<th scope="col">Wybrany alert RCB</th>' : ''}`;
      const cv = $('#plotno');
      if (cv) cv.setAttribute('aria-label', `${cv.dataset.opis} Okres ${opisOkresu()}: ${z.length} komunikatów. Najwięcej: ${top.slice(0, 3).map(p => `${nazwaPow(p)} (${naPowiat[p.i]})`).join(', ')}.${brak ? ` ${brak} powiatów woj. ${WOJ[BRAK.woj]}: brak w naszych danych.` : ''} Pełna tabela powiatów obok mapy.`);
    };
    sluchacze.push(rysuj); rysuj();
  }
  function przelaczniki() {
    const bP = $('#przel-prosty'), bR = $('#przel-ruch');
    const odswiez = () => {
      bP.setAttribute('aria-pressed', String(stan.prosty)); bR.setAttribute('aria-pressed', String(stan.ruch && !stan.prosty));
      bR.setAttribute('aria-disabled', String(stan.prosty)); document.body.classList.toggle('prosty', stan.prosty);
    };
    bP.addEventListener('click', () => zmien({ prosty: !stan.prosty }));
    bR.addEventListener('click', () => {
      if (stan.prosty) return;
      try { localStorage.setItem('teraz-animacje', stan.ruch ? '0' : '1'); } catch { /* bez pamięci przeglądarki */ }
      zmien({ ruch: !stan.ruch });
    });
    // ustawienie systemu działa tylko, gdy użytkownik nie wybrał sam
    ruchSystem.addEventListener('change', () => { let w = null; try { w = localStorage.getItem('teraz-animacje'); } catch { /* */ } if (w === null) zmien({ ruch: !ruchSystem.matches }); });
    sluchacze.push(odswiez); odswiez();
  }

  // ---------- dymek ----------
  const dymek = {
    pokaz(x, y, html) { const d = $('#dymek'); d.innerHTML = html; d.style.display = 'block'; const sc = d.parentElement.getBoundingClientRect(); const w = d.offsetWidth, h = d.offsetHeight; d.style.left = `${Math.min(sc.width - w - 8, x + 14)}px`; d.style.top = `${Math.max(8, Math.min(sc.height - h - 8, y + 14))}px`; },
    ukryj() { $('#dymek').style.display = 'none'; },
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') dymek.ukryj(); });
  const oglos = t => { const o = $('#ogloszenie'); if (o) { o.textContent = ''; setTimeout(() => { o.textContent = t; }, 50); } };
  function opisPowiatu(p) {
    const n = liczby().naPowiat[p.i];
    let h = `<b>${nazwaPow(p)}</b><span class="male">woj. ${WOJ[p.woj]} · TERYT ${p.kod}</span><br>`;
    h += n === null ? `<span class="brak">${opisBraku()}</span>` : `<span class="liczba">${n}</span> komunikatów w okresie ${opisOkresu()}`;
    if (stan.rcb) {
      const a = RCB.find(r => r.id === stan.rcb);
      if (a.wylaczone.includes(p.kod)) h += '<br><span class="male">Alert RCB: wyłączony w treści komunikatu. Sprawdź oryginał.</span>';
      else if (a.wlaczone.includes(p.kod)) h += '<br><span class="male">Alert RCB: wymieniony w treści komunikatu.</span>';
    }
    return h;
  }

  /** Podpisy na scenie: [punkt, [linia1, linia2], 'prawo'|'lewo'|'gora']; bez nachodzenia, z odbiciem przy krawędzi. */
  function podpisy(x, lista, W, H) {
    const zajete = [];
    if (W < 600) { let g = 0; lista = lista.filter(l => l[2] !== 'gora' || g++ < 1); } // telefon: jeden podpis szczytu
    const wolne = b => b[0] >= 4 && b[1] >= 4 && b[2] <= W - 4 && b[3] <= H - 26 && !zajete.some(z => b[0] < z[2] && b[2] > z[0] && b[1] < z[3] && b[3] > z[1]);
    const plyta = b => { x.fillStyle = 'rgba(11,13,12,0.8)'; x.beginPath(); x.roundRect(b[0] - 3, b[1], b[2] - b[0] + 6, b[3] - b[1], 4); x.fill(); };
    const tekst = (t, ax, ay, font, kolor) => { x.font = font; x.lineWidth = 3; x.strokeStyle = 'rgba(11,13,12,0.92)'; x.strokeText(t, ax, ay); x.fillStyle = kolor; x.fillText(t, ax, ay); };
    const szer = (t, font) => { x.font = font; return x.measureText(t).width; };
    const F1 = '600 12px system-ui, sans-serif', F2 = '11.5px system-ui, sans-serif', FN = '600 13px ui-monospace, Menlo, monospace';
    for (const [[px, py], [l1, l2], strona0] of lista) {
      if (strona0 === 'gora') {
        const tw = Math.max(szer(l1, FN), szer(l2, F2));
        for (const dy of [0, -18, -36]) {
          const b = [px - tw / 2 - 3, py - 33 + dy, px + tw / 2 + 3, py - 1 + dy];
          if (!wolne(b)) continue;
          zajete.push(b); plyta(b); x.textAlign = 'center';
          if (dy) { x.strokeStyle = 'rgba(237,240,232,0.45)'; x.lineWidth = 1; x.beginPath(); x.moveTo(px, py - 2); x.lineTo(px, py + dy - 2); x.stroke(); }
          tekst(l1, px, py - 19 + dy, FN, 'rgb(255,194,122)'); tekst(l2, px, py - 5 + dy, F2, 'rgb(237,240,232)');
          break;
        }
        continue;
      }
      const tw = Math.max(szer(l1, F1), szer(l2, F2));
      let gotowe = false;
      for (const strona of [strona0, strona0 === 'prawo' ? 'lewo' : 'prawo']) {
        for (const [dx, dy] of [[34, -30], [50, -48], [34, 30]]) {
          const pr = strona === 'prawo', tx = px + (pr ? dx : -dx), ty = py + dy, ax = tx + (pr ? 4 : -4);
          const b = pr ? [ax - 2, ty - 15, ax + tw + 2, ty + 16] : [ax - tw - 2, ty - 15, ax + 2, ty + 16];
          if (!wolne(b)) continue;
          zajete.push(b);
          plyta(b);
          x.strokeStyle = 'rgba(237,240,232,0.6)'; x.lineWidth = 1; x.beginPath(); x.moveTo(px, py); x.lineTo(tx, ty); x.stroke();
          x.textAlign = pr ? 'left' : 'right';
          tekst(l1, ax, ty - 2, F1, 'rgb(237,240,232)'); tekst(l2, ax, ty + 12, F2, 'rgb(154,163,154)');
          gotowe = true; break;
        }
        if (gotowe) break;
      }
    }
  }

  function init({ legendaDodatki = [], uwaga } = {}) {
    legenda(legendaDodatki, uwaga); osCzasu(); lista(); zrodla(); naglowek(); przelaczniki();
  }
  const subskrybuj = f => sluchacze.push(f);

  // punkt w wielokącie (pierścienie, parzysto-nieparzyście)
  function wWielokacie(x, y, rings) {
    let w = false;
    for (const r of rings) for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) w = !w;
    }
    return w;
  }

  return { D, powiaty, kraj, wojLinie, WOJ, poKodzie, xy, rng, stan, zmien, okres, opisOkresu, liczby, kolor, klasa, wzorBraku, wzorWylaczenia,
    PRZYBLIZONE, RCB, ZR, BRAK, DZIS, dzien, init, podpisy, oglos, subskrybuj, dymek, opisPowiatu, opisBraku, nazwaPow, wWielokacie, el, $ };
})();

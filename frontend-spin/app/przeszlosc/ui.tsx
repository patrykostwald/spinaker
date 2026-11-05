"use client";
import { useEffect, useRef, useState } from 'react';
import { useFeature } from '@spin-clinic/ui';
import './przeszlosc.css';
import './pasek-menu.css';
import { NARRATIVE_CAPTION, NARRATIVE_LABEL, useNarrativeLayer } from './narracja';
export { NARRATIVE_CAPTION, NARRATIVE_LABEL, stripDiagnoses, useNarrativeLayer } from './narracja';

/** Wspólne elementy przeszłość.today (temat, profil osoby, alerty): ikony, typografia, nagłówek i stopka. */

/** Polska typografia (zasada właściciela): jednoliterowe słowa nie zostają na końcu wiersza. */
export const nb = (text: string) => text.replace(/(^|[\s(])([aiouwzAIOUWZ])\s+/g, '$1$2 ');
export const plural = (n: number, one: string, few: string, many: string) => n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
export const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
export const short = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }) : '';
export const spinColor = (v = 0) => v >= 70 ? 'var(--sc-spin-hi)' : v >= 40 ? 'var(--sc-spin-mid)' : 'var(--sc-spin-lo)';
/** Tekst do wyświetlenia z wartości z API: nigdy „[object Object]” (właściciel 7.10). Obiekt -> name / short / label / title. */
export const text = (v: unknown): string => {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  if (v && typeof v === 'object') { const o = v as Record<string, unknown>; for (const k of ['name', 'short', 'label', 'title']) if (typeof o[k] === 'string' && o[k]) return o[k] as string; }
  return '';
};
/** Domena źródła do śladu przy fakcie (np. x.com, sejm.gov.pl); pusty tekst, gdy adres jest niepoprawny. */
export const host = (u?: string | null) => { try { return u ? new URL(u).hostname.replace(/^www\./, '') : ''; } catch { return ''; } };
export type Access = { beta: boolean; label: string; locked: string[] };
export const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// skróty kont instytucji pełną nazwą (panel designu 5.10: „ME” nic nie mówi czytelnikowi); NAZWISKA wielkimi literami jak zwykłe
const INSTITUTIONS: Record<string, string> = { ME: 'Ministerstwo Energii', MF: 'Ministerstwo Finansów', MON: 'Ministerstwo Obrony Narodowej', MZ: 'Ministerstwo Zdrowia',
  MSZ: 'Ministerstwo Spraw Zagranicznych', MSWiA: 'Ministerstwo Spraw Wewnętrznych i Administracji', KPRM: 'Kancelaria Prezesa Rady Ministrów', MEN: 'Ministerstwo Edukacji Narodowej' };
export const nice = (name: string) => INSTITUTIONS[name.trim()] ?? name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase()
  ? w[0] + w.slice(1).toLowerCase() : w).join('');

/** Skrócone linki t.co (X) nie niosą informacji: pokazujemy "link w X" (recenzja Fable 13.10); adres w polu url zostaje bez zmian (źródło). */
export const tidyLinks = (value: string) => value.replace(/https?:\/\/t\.co\/\w+/g, '[link w X]');

/** Adres profilu osoby z węzła tematu („figure:12”) albo z danych profilu. */
export const personHref = (p: { id: string | number | null; slug?: string | null }) =>
  p.slug ? `/przeszlosc/osoba/${p.slug}` : `/przeszlosc/osoba/${String(p.id ?? '').replace(/^figure:/, '')}`;

/* Ikony rodzajów (jedna linia 1,7 px, ten sam styl wszędzie) */
const ICON: Record<string, string> = {
  person: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM5 20a7 7 0 0 1 14 0',
  institution: 'M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18',
  statement: 'M4 5h16v11H9l-5 4V5Z',
  record: 'M7 3h7l4 4v14H7V3Zm7 0v4h4M10 12h5M10 16h5',
  media: 'M4 5h13v14H6a2 2 0 0 1-2-2V5Zm13 4h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5',
  diagnosis: 'M3 12h4l2-5 4 10 2-5h6',
  organisation: 'M4 21V8l8-5 8 5v13M9 21v-5h6v5M9 11h.01M15 11h.01',
  vote: 'M5 12l4 4 10-10',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 5 5',
  rss: 'M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14M6 19h.01',
  down: 'M12 4v12m-5-5 5 5 5-5M5 20h14',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4l2-2Zm4 4h4',
  people: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM3 20a6 6 0 0 1 12 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14a6 6 0 0 1 3 6',
};
export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return <svg className="px-ic" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={1.7}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICON[name] ?? ICON.statement} /></svg>;
}

/** Osobna strona (przeszlosc.today): bez pasków i menu spin.clinic. */
export function useStandalone() {
  useEffect(() => {
    document.documentElement.dataset.standalone = '1';
    return () => { delete document.documentElement.dataset.standalone; };
  }, []);
}

/** Etykieta bety z serwera (PRZESZLOSC_BETA_ALL_FEATURES): jedna prośba na stronę, pamiętana między komponentami. */
let accessPromise: Promise<Access | null> | null = null;
export function useAccess(enabled = true) {
  const [access, setAccess] = useState<Access | null>(null);
  useEffect(() => {
    if (!enabled) return;
    accessPromise ??= fetch('/api/przeszlosc/funkcje/').then(r => r.ok ? r.json() : null).catch(() => null);
    let live = true; void accessPromise.then(a => { if (live) setAccess(a); }); return () => { live = false; };
  }, [enabled]);
  return access;
}

/** Cichy przełącznik warstwy „Wpływ na narrację”: stałe miejsce na końcu paska menu, cel min. 44 px, nic nie skacze. */
export function NarrativeToggle() {
  const [on, set] = useNarrativeLayer();
  return <button type="button" className="px-layer-toggle" aria-pressed={on} onClick={() => set(!on)} title={NARRATIVE_CAPTION}>
    <i aria-hidden="true" /><span className="px-layer-toggle__full">{NARRATIVE_LABEL}</span><span className="px-layer-toggle__short" aria-hidden="true">Narracja</span></button>;
}
/** Podpis włączonej warstwy: mały, w linii nad tytułem (etykieta stanu, nie zmienia wysokości). */
export function LayerCaption() {
  const [on] = useNarrativeLayer();
  return on ? <span className="px-layer"> · {NARRATIVE_CAPTION}</span> : null;
}

/** Znak przeszłość.today (logo właściciela, LOGA): szeryfowe „przeszłość”, czerwona kropka, „today” w Montserrat. Wektor z tekstem
 *  (kroje strony), wysokość jednym tokenem --pt-logo-h (port v3, 13.10: znak większy o ok. 27%, uwaga właściciela „logo za małe”). */
export function Logo() {
  return <svg className="pt-logo" viewBox="0 0 216 42" role="img" aria-label="przeszłość.today">
    <text x="0" y="31" className="pt-logo__t" fill="currentColor">przeszłość<tspan className="pt-logo__d" dx="1">.</tspan><tspan className="pt-logo__m" dx="4" fill="currentColor">today</tspan></text></svg>;
}

const MENU_LINKS: [string, string][] = [['/przeszlosc/funkcje', 'Funkcje'], ['/przeszlosc?tryb=osoba', 'Osoby'], ['/przeszlosc/odstepstwa', 'Odstępstwa'], ['/przeszlosc/glosowania', 'Głosowania'], ['/przeszlosc/jak-to-dziala', 'Jak to działa']];
/** Aplikacja (PWA seria 2): pozycja tylko przy włączonej fladze APP; w menu telefonu i w stopce (w pasku ukryta: pasek-menu.css). */
const APP_LINK: [string, string] = ['/przeszlosc/aplikacja', 'Aplikacja'];

/** Pasek (port v3): znak z „beta” jak indeks górny, pole zapytania (skrót „/”), menu w wersalikach z konwencją terminala;
 *  poniżej 1000 px menu zwija się do przycisku „Menu”. Aktywna pozycja: aria-current (tekst akcentu, „>” i migające „_”). */
export function Bar({ index, quiet = false }: { index?: React.ReactNode; quiet?: boolean } = {}) {
  // quiet: strona statyczna (np. "Jak to działa") bez wywołań API; etykieta bety wraca do domyślnej "wersja beta"
  const access = useAccess(!quiet);
  const appOn = useFeature('APP_ENABLED');
  const links = appOn ? [...MENU_LINKS, APP_LINK] : MENU_LINKS;
  const [here, setHere] = useState('');
  const [open, setOpen] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const menuBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const p = window.location.pathname, q = new URLSearchParams(window.location.search);
    setHere(/\/jak-to-dziala/.test(p) ? '/przeszlosc/jak-to-dziala' : /\/aplikacja/.test(p) ? '/przeszlosc/aplikacja' : p.startsWith('/przeszlosc/funkcje') ? '/przeszlosc/funkcje' : p.startsWith('/przeszlosc/odstepstwa') ? '/przeszlosc/odstepstwa' : p.startsWith('/przeszlosc/glosowania') ? '/przeszlosc/glosowania'
      : p.startsWith('/przeszlosc/osoba') || q.get('tryb') === 'osoba' ? '/przeszlosc?tryb=osoba' : '');
    const key = (e: KeyboardEvent) => {
      if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test((document.activeElement as HTMLElement | null)?.tagName ?? '') && field.current?.offsetParent) { e.preventDefault(); field.current.focus(); }
      if (e.key === 'Escape') setOpen(o => { if (o) menuBtn.current?.focus(); return false; });
    };
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, []);
  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const v = (field.current?.value ?? '').trim();
    if (!v) { field.current?.focus(); return; }
    const krs = v.replace(/^krs\s*/i, '').replace(/\s/g, '');
    window.location.href = /^\d{10}$/.test(krs) ? `/przeszlosc/spolka/${krs}` : `/przeszlosc?q=${encodeURIComponent(v)}`;
  };
  const label = access?.beta && access.label ? access.label : 'wersja beta';
  const nav = <nav className="px-bar pt-top" aria-label="Menu">
    <span className="px-bar__brand"><a href="/przeszlosc" className="px-mark pt-brand" aria-label={`przeszłość.today, ${label}`} title={label}>
      <Logo /><span className="pt-beta" aria-hidden="true">beta</span></a></span>
    <form className="pt-q" role="search" onSubmit={submit}>
      <Icon name="search" />
      <input ref={field} type="search" enterKeyHint="search" autoComplete="off" placeholder="Temat, osoba, KRS" aria-label="Szukaj tematu, osoby albo numeru KRS" />
      <kbd aria-hidden="true">/</kbd>
    </form>
    <span className="px-bar__links">{links.map(([href, text]) => <a key={href} href={href} className={href === APP_LINK[0] ? 'pt-link-app' : undefined} aria-current={here === href ? 'page' : undefined}>{text}</a>)}
      <NarrativeToggle /></span>
    <button ref={menuBtn} type="button" className="pt-menu-btn" aria-expanded={open} aria-controls="pt-mmenu" onClick={() => setOpen(!open)}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" aria-hidden="true"><path d={open ? 'M6 6l12 12M18 6 6 18' : 'M4 7h16M4 12h16M4 17h16'} /></svg>
      <span>Menu</span></button>
    <div className="pt-mmenu" id="pt-mmenu" hidden={!open}>
      {links.map(([href, text]) => <a key={href} href={href} aria-current={here === href ? 'page' : undefined} onClick={() => setOpen(false)}>{text}</a>)}
      <NarrativeToggle />
    </div>
  </nav>;
  // indeks akt jako drugi wiersz tego samego paska (jedna strefa, bez odstępu sekcji między wierszami)
  return index ? <div className="pt-topwrap">{nav}{index}</div> : nav;
}

/** Indeks akt (port v3): drugi wiersz paska na profilu, numerowane pozycje 01-0N, aktywna sekcja z przewijania (konwencja terminala).
 *  Na telefonie jeden wiersz bez widocznego paska przewijania (scrollbar-width: none, wygaszone krawędzie) - jedyny wyjątek od zawijania. */
export function PageIndex({ items }: { items: [string, string][] }) {
  const [act, setAct] = useState(items[0]?.[0] ?? '');
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(en => en.forEach(e => { if (e.isIntersecting) setAct(e.target.id); }), { rootMargin: '-25% 0px -65% 0px' });
    items.forEach(([id]) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [items]);
  useEffect(() => {
    const a = list.current?.querySelector<HTMLElement>(`a[href="#${CSS.escape(act)}"]`);
    if (a && list.current && list.current.scrollWidth > list.current.clientWidth) list.current.scrollTo({ left: a.offsetLeft - 16, behavior: reduced() ? 'auto' : 'smooth' });
  }, [act]);
  return <nav className="pt-idx" aria-label="Indeks akt"><ol ref={list}>{items.map(([id, text], i) =>
    <li key={id}><a href={`#${id}`} aria-current={act === id ? 'location' : undefined}><b>{String(i + 1).padStart(2, '0')}</b>{text}</a></li>)}</ol></nav>;
}

/** Stopka: operator, odnośniki i aplikacja (port v3: PWA przeszłość.today, gdy włączona flaga APP). W zainstalowanej aplikacji
 *  (display-mode: standalone) odnośnik nie zachęca do instalacji, tylko prowadzi do opisu aplikacji. */
export function Foot() {
  const app = useFeature('APP_ENABLED');
  const [installed, setInstalled] = useState(false);
  useEffect(() => {
    setInstalled(window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
  }, []);
  return <footer className="px-foot"><span>przeszłość.today prowadzi iapply sp. z&nbsp;o.o. · <a href="https://spin.clinic" target="_blank" rel="noopener noreferrer">dane wspólne ze spin.clinic</a></span>
    <span><a href="/przeszlosc/jak-to-dziala">Jak to działa</a> · <a href="/przeszlosc/poprawki">Poprawki</a> · <a href="/przeszlosc/dane">Stan danych</a> · <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a>{app && <> · <a href="/przeszlosc/aplikacja">{installed ? 'Aplikacja' : 'Zainstaluj aplikację'}</a></>}</span></footer>;
}

/** Obserwuj temat albo osobę (sprint 1): e-mail, zgoda, podwójne potwierdzenie; jeden list dziennie o 7:00. */
export function Follow({ kind, target, label, rss, primary = false }: { kind: 'topic' | 'person'; target: string; label: string; rss?: string; primary?: boolean }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [trap, setTrap] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [narr] = useNarrativeLayer();
  const close = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    close.current?.focus();
    const back = document.activeElement as HTMLElement | null;
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
      if (e.key === 'Tab' && box.current) { const f = [...box.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input')].filter(x => x.offsetParent);
        if (!f.length) return; const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } }
    };
    window.addEventListener('keydown', key);
    return () => { window.removeEventListener('keydown', key); if (back?.isConnected) back.focus({ preventScroll: true }); };
  }, [open]);
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!consent) { setState('error'); setMessage('Zaznacz zgodę na codzienny list.'); return; }
    setState('sending');
    try {
      const r = await fetch('/api/przeszlosc/alerty/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, consent, kind, website: trap, ...(kind === 'topic' ? { q: target } : { figure: target }) }) });
      const data = await r.json().catch(() => ({}));
      if (r.status === 429) { setState('error'); setMessage('Za dużo prób. Spróbuj za godzinę.'); return; }
      if (!r.ok) { setState('error'); setMessage(data.detail ?? 'Nie udało się zapisać. Spróbuj ponownie.'); return; }
      setState('done'); setMessage(data.detail ?? 'Sprawdź skrzynkę.');
    } catch { setState('error'); setMessage('Brak połączenia. Spróbuj ponownie.'); }
  }
  return <>
    <button type="button" className={primary ? 'px-tool pt-pri' : 'px-tool'} onClick={() => { setOpen(true); setState('idle'); setMessage(''); }} aria-haspopup="dialog">
      <Icon name="bell" />{kind === 'topic' ? 'Obserwuj temat' : 'Obserwuj osobę'}</button>
    {open && <div className="px-follow" role="dialog" aria-modal="true" aria-labelledby="px-follow-h">
      <button type="button" className="px-panel__scrim" aria-label="Zamknij" tabIndex={-1} onClick={() => setOpen(false)} />
      <div className="px-follow__box" ref={box}>
        <header className="px-follow__head"><h2 id="px-follow-h">Obserwuj: {label}</h2>
          <button ref={close} type="button" className="px-panel__x" onClick={() => setOpen(false)} aria-label="Zamknij">×</button></header>
        {state === 'done' ? <div className="px-follow__done" role="status"><p>{message}</p>
          <p className="px-note">{nb('Link jest ważny, dopóki nie zapiszesz się ponownie. Nie widzisz listu? Sprawdź folder z ofertami i spamem.')}</p>
          <button type="button" className="px-more" onClick={() => setOpen(false)}>Gotowe</button></div>
          : <form className="px-follow__form" onSubmit={send} noValidate>
            <p className="px-follow__lead">{nb(kind === 'topic'
              ? `Codziennie o 7:00 jeden list z nowymi wpisami, ${narr ? 'diagnozami, ' : ''}dokumentami Sejmu i artykułami w tym temacie. Gdy nic nowego nie ma, nie piszemy.`
              : `Codziennie o 7:00 jeden list z nowymi wpisami tej osoby, ${narr ? 'diagnozami Dr. Spina, ' : ''}interpelacjami, głosowaniami i zmianami w KRS. Gdy nic nowego nie ma, nie piszemy.`)}</p>
            <label className="px-follow__field"><span>Adres e-mail</span>
              <input type="email" required autoComplete="email" inputMode="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="redakcja@przyklad.pl" /></label>
            <input className="px-sr" tabIndex={-1} autoComplete="off" aria-hidden="true" value={trap} onChange={e => setTrap(e.target.value)} name="website" />
            <label className="px-follow__check"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
              <span>{nb('Zgadzam się na codzienny list od przeszłość.today (iapply sp. z o.o.). Wypiszę się jednym kliknięciem. Nie śledzimy otwarć ani kliknięć.')}</span></label>
            {state === 'error' && <p className="px-follow__err" role="alert">{message}</p>}
            <div className="px-follow__act"><button type="submit" className="px-btn" disabled={state === 'sending'}>{state === 'sending' ? 'Zapisuję…' : 'Wyślij link potwierdzający'}</button>
              {rss && <a className="px-quiet" href={rss} target="_blank" rel="noopener noreferrer"><Icon name="rss" />albo kanał RSS</a>}</div>
          </form>}
      </div>
    </div>}
  </>;
}

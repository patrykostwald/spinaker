"use client";
import { useEffect, useRef, useState } from 'react';
import './przeszlosc.css';

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
export type Access = { beta: boolean; label: string; locked: string[] };
export const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// skróty kont instytucji pełną nazwą (panel designu 5.10: „ME” nic nie mówi czytelnikowi); NAZWISKA wielkimi literami jak zwykłe
const INSTITUTIONS: Record<string, string> = { ME: 'Ministerstwo Energii', MF: 'Ministerstwo Finansów', MON: 'Ministerstwo Obrony Narodowej', MZ: 'Ministerstwo Zdrowia',
  MSZ: 'Ministerstwo Spraw Zagranicznych', MSWiA: 'Ministerstwo Spraw Wewnętrznych i Administracji', KPRM: 'Kancelaria Prezesa Rady Ministrów', MEN: 'Ministerstwo Edukacji Narodowej' };
export const nice = (name: string) => INSTITUTIONS[name.trim()] ?? name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase()
  ? w[0] + w.slice(1).toLowerCase() : w).join('');

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
export function useAccess() {
  const [access, setAccess] = useState<Access | null>(null);
  useEffect(() => {
    accessPromise ??= fetch('/api/przeszlosc/funkcje/').then(r => r.ok ? r.json() : null).catch(() => null);
    let live = true; void accessPromise.then(a => { if (live) setAccess(a); }); return () => { live = false; };
  }, []);
  return access;
}

export function Bar() {
  const access = useAccess();
  return <nav className="px-bar" aria-label="Menu">
    <span className="px-bar__brand"><a href="/przeszlosc" className="px-mark">przeszłość<i>.</i>today</a>
      {access?.beta && access.label && <span className="px-beta" title={access.label}>
        <span className="px-beta__full">{access.label}</span><span className="px-beta__short">Beta</span></span>}</span>
    <span className="px-bar__links"><a href="/przeszlosc/funkcje">Funkcje</a><a href="/przeszlosc?tryb=osoba">Szukaj osoby</a><a href="/przeszlosc#jak">Jak to działa</a>
      <a href="https://spin.clinic" target="_blank" rel="noopener noreferrer">spin.clinic ↗</a></span>
  </nav>;
}

export function Foot() {
  return <footer className="px-foot"><span>przeszłość.today prowadzi iapply sp. z&nbsp;o.o. · dane wspólne ze spin.clinic</span>
    <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a></footer>;
}

/** Obserwuj temat albo osobę (sprint 1): e-mail, zgoda, podwójne potwierdzenie; jeden list dziennie o 7:00. */
export function Follow({ kind, target, label, rss }: { kind: 'topic' | 'person'; target: string; label: string; rss?: string }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [trap, setTrap] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');
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
    <button type="button" className="px-tool" onClick={() => { setOpen(true); setState('idle'); setMessage(''); }} aria-haspopup="dialog">
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
            <p className="px-follow__lead">{nb(kind === 'topic' ? 'Codziennie o 7:00 jeden list z nowymi wpisami, diagnozami, dokumentami Sejmu i artykułami w tym temacie. Gdy nic nowego nie ma, nie piszemy.'
              : 'Codziennie o 7:00 jeden list z nowymi wpisami tej osoby, diagnozami Dr. Spina, interpelacjami, głosowaniami i zmianami w KRS. Gdy nic nowego nie ma, nie piszemy.')}</p>
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
